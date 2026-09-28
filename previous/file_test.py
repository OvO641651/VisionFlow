import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QGraphicsView,
    QFileDialog  # 新增：导入文件选择框
)
# 打开主窗口，显示小窗口，模体ui窗口，设置layout， 设置流程图画布
from PySide2.QtUiTools import QUiLoader  # 导入ui
from PySide2.QtGui import QIcon, QImage, QPixmap  # 设置图标，显示图像
from PySide2.QtCore import QTimer, Qt, QPointF  # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2

from Detector import DetectorShape
from FlowChart import NodeItem, EdgeItem, FlowchartView

'''
添加"打开"按钮
'''

uiloader = QUiLoader()


class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头相关参数
        self.cap = None  # 视频捕获对象
        self.timer = None  # 刷新定时器
        self.camera_id = 0  # 默认摄像头ID，可通过设置菜单修改
        self._is_video_file = False  # 新增：标记当前打开的是否为视频文件

        # 通过 findChild 找到被 tab 包裹的 video 和 graphicsView 控件
        # 将下面的所有 main_window.video 改成 videoLabel
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")

        # 设置按钮
        self.main_window.camera_button.clicked.connect(self.open_camera)  # 开启摄像头按钮
        self.main_window.close_button.clicked.connect(self.close_camera)  # 关闭摄像头按钮
        # 修改：绑定 open_button 到 open_file 函数
        self.main_window.open_button.clicked.connect(self.open_file)

        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后 弹出 新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 创建树控件
        self.tree = self.main_window.tree
        # 树状图点击事件
        self.main_window.tree.itemClicked.connect(self.on_tree_item_clicked)
        # 当前检测模式
        self.detection_mode = None

        # 流程图初始化，按照 FlowChart 中的 TestWindow 类的内容进行初始化和编写具体内容
        # 初始化节点和连线列表
        self.flow_nodes = []  # 存放所有方框
        self.flow_edges = []  # 存放所有连线
        # 启用左侧树控件的拖拽功能
        self.main_window.tree.setDragEnabled(True)  # 拖动使能，可以拖动里面树枝控件
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction)  # 拖拽时的行为是“复制”，而不是“剪切”
        # 获取 UI 中的 graphicsView，替换为 FlowchartView，相对于在用来的基础上创建一个新的 graphicsView，这个新的可以实现拖拽等功能
        # 通过 findChild 找到被 tab 包裹的 video 和 graphicsView 控件
        view = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        if view:
            parent = view.parent()  # 获取这个空画布的父容器
            geometry = view.geometry()  # 获取这个画布当前所在的位置和大小
            view.deleteLater()  # 把原先那个只是用来占位、没有任何交互功能的空画布彻底销毁，释放内存。
            # 实例化 FlowchartView，把主窗口 self 传进去
            self.main_window.graphicsView = FlowchartView(parent, main_window=self)
            self.main_window.graphicsView.setGeometry(geometry)  # 覆盖原来的 graphicsView 的位置和大小
            self.main_window.graphicsView.show()  # 显示
            # 每次刷新时全屏更新，防止有拖尾残影
            self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # 树控件 tree 绑定双击事件，双击实现在画布view中创建方框流程图
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)

    # ===================== 新增：打开文件（图片/视频）函数 =====================
    def open_file(self):
        """弹出选择框，导入图片或视频"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "选择图片或视频",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;视频文件 (*.mp4 *.avi *.mkv)"
        )
        if not file_path:
            return

        # 无论当前是播放摄像头还是视频，先关闭释放资源
        self.close_camera()

        ext = file_path.lower()
        if ext.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            # ---------- 处理单张图片 ----------
            frame = cv2.imread(file_path)
            if frame is None:
                QMessageBox.warning(self.main_window, "错误", "无法读取图片文件")
                return
            # 单张图片不需要循环，直接处理并显示
            self._process_and_display_frame(frame)

        elif ext.endswith(('.mp4', '.avi', '.mkv')):
            # ---------- 处理视频文件 ----------
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                QMessageBox.warning(self.main_window, "错误", "无法打开视频文件")
                return
            self.cap = cap
            self._is_video_file = True

            # 启动定时器循环读取视频帧
            if self.timer is not None:
                self.timer.stop()
                self.timer = None
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_frame)
            self.timer.start(30)
        else:
            QMessageBox.warning(self.main_window, "错误", "不支持的文件格式")

    # ===================== 新增：通用的“处理并显示”方法 =====================
    def _process_and_display_frame(self, frame):
        """
        按流程图或树状图模式处理一帧图像，并渲染到 videoLabel
        """
        # 1. 根据 流程图 或 树状图点击模式 处理帧
        if self.flow_nodes:
            frame, data = self._run_flow_pipeline(frame)
        else:
            frame, data = self.process_frame(frame)

        # 2. OpenCV BGR -> RGB 转换
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888)

        # 3. 缩放并显示
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.videoLabel.size(), Qt.KeepAspectRatio)
        self.videoLabel.setPixmap(scaled)
        self.videoLabel.setStyleSheet("")  # 清除文字样式

    # ===================== 修改：打开摄像头 =====================
    def open_camera(self):
        """打开摄像头并启动视频刷新"""
        # 如果当前正在播放视频，强制关闭视频，避免冲突
        if self.cap is not None and self.cap.isOpened() and self._is_video_file:
            self.close_camera()

        if self.cap is not None and self.cap.isOpened():
            return

        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            QMessageBox.warning(self.main_window, "错误", "无法打开摄像头，请检查设备连接")
            self.cap = None
            return

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    # ===================== 修改：关闭摄像头 / 视频流 =====================
    def close_camera(self):
        """关闭摄像头/视频，停止定时器，清空显示区域"""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        # 重置视频标记
        self._is_video_file = False

        self.videoLabel.clear()
        self.videoLabel.setText("video")
        self.videoLabel.setStyleSheet(
            "background-color: black; color: white; font-size: 24px; font-weight: bold;")

    # ===================== 修改：视频帧轮询函数 =====================
    def update_frame(self):
        """定时器槽函数：读取摄像头/视频帧并显示到 video 标签"""
        if self.cap is None or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if not ret:
            # 区分是摄像头出错还是视频播放结束
            if self._is_video_file:
                # 视频播放结束，停止定时器，释放资源（不弹警告，不清除最后一帧画面）
                if self.timer is not None:
                    self.timer.stop()
                    self.timer = None
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                self._is_video_file = False
                return
            else:
                # 摄像头读取失败
                self.close_camera()
                QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
                return

        # 调用通用处理与显示函数
        self._process_and_display_frame(frame)

    # ===================== 以下为原文件保留的函数 =====================
    def close_event(self, event):
        self.close_camera()
        event.accept()

    def set_camera_id(self):
        loader = QUiLoader()
        widget = loader.load('SetCameraID.ui')
        if widget is None:
            return

        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("设置摄像头ID")
        dialog.setModal(True)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        widget.setParent(dialog)
        widget.move(0, 0)
        dialog.setFixedSize(widget.size())

        line_edit = widget.findChild(QtWidgets.QLineEdit, "ID")
        ok_button = widget.findChild(QtWidgets.QPushButton, "SetID")
        if line_edit and ok_button:
            line_edit.setText(str(self.camera_id))

            def on_ok():
                id_str = line_edit.text().strip()
                if not id_str:
                    QMessageBox.warning(dialog, "输入错误", "摄像头ID不能为空")
                    return
                try:
                    new_id = int(id_str)
                    if new_id < 0:
                        raise ValueError
                    self.camera_id = new_id
                    dialog.accept()
                except ValueError:
                    QMessageBox.warning(dialog, "输入错误", "请输入一个有效的非负整数")

            ok_button.clicked.connect(on_ok)
        else:
            QMessageBox.warning(dialog, "界面错误", "未找到输入框或确定按钮，请检查SetCameraID.ui")

        dialog.exec_()

    def on_tree_item_clicked(self, item, column):
        index = self.tree.currentIndex()
        if not index.isValid():
            self.detection_mode = None
            return

        path = []
        while index.isValid():
            path.insert(0, index.row())
            index = index.parent()
        path_tuple = tuple(path)

        if path_tuple == (0, 0):
            self.detection_mode = 'line'
        elif path_tuple == (0, 1):
            self.detection_mode = 'circle'
        elif path_tuple == (1, 0):
            print(11)
        else:
            self.detection_mode = None

    def process_frame(self, frame):
        if self.detection_mode == 'line':
            return self.detector.line_detector(frame)
        elif self.detection_mode == 'circle':
            return self.detector.circle_detector(frame)
        else:
            return frame, []

    def _run_flow_pipeline(self, frame):
        img = frame
        data = []
        for node in self.flow_nodes:
            if node.name == "直线":
                img, d = self.detector.line_detector(img)
                data.extend(d)
            elif node.name == "圆":
                img, d = self.detector.circle_detector(img)
        return img, data

    def add_flow_node(self, name, pos):
        node = NodeItem(name, pos)
        self.main_window.graphicsView.scene.addItem(node)
        node.positionChanged.connect(self.update_all_edges)

        if self.flow_nodes:
            prev_node = self.flow_nodes[-1]
            edge = EdgeItem(prev_node.get_output_pos(), node.get_input_pos())
            self.main_window.graphicsView.scene.addItem(edge)
            self.flow_edges.append(edge)

        self.flow_nodes.append(node)
        QTimer.singleShot(0, self.update_all_edges)
        return node

    def delete_flow_node(self, node_to_delete):
        if node_to_delete not in self.flow_nodes:
            return

        idx = self.flow_nodes.index(node_to_delete)
        n = len(self.flow_nodes)
        self.main_window.graphicsView.scene.removeItem(node_to_delete)

        if n == 1:
            self.flow_nodes.clear()
            for e in self.flow_edges:
                self.main_window.graphicsView.scene.removeItem(e)
            self.flow_edges.clear()

        elif idx == 0:
            self.flow_nodes.pop(0)
            e = self.flow_edges.pop(0)
            self.main_window.graphicsView.scene.removeItem(e)

        elif idx == n - 1:
            self.flow_nodes.pop()
            e = self.flow_edges.pop()
            self.main_window.graphicsView.scene.removeItem(e)

        else:
            self.flow_nodes.pop(idx)
            e1 = self.flow_edges.pop(idx - 1)
            e2 = self.flow_edges.pop(idx - 1)
            self.main_window.graphicsView.scene.removeItem(e1)
            self.main_window.graphicsView.scene.removeItem(e2)

            prev_node = self.flow_nodes[idx - 1]
            next_node = self.flow_nodes[idx]
            new_edge = EdgeItem(prev_node.get_output_pos(), next_node.get_input_pos())
            self.main_window.graphicsView.scene.addItem(new_edge)
            self.flow_edges.insert(idx - 1, new_edge)

        self.update_all_edges()

    def update_all_edges(self):
        for i, edge in enumerate(self.flow_edges):
            start_node = self.flow_nodes[i]
            end_node = self.flow_nodes[i + 1]
            new_start = start_node.get_output_pos()
            new_end = end_node.get_input_pos()
            edge.update_positions(new_start, new_end)

    def _on_tree_double_click(self, item, column):
        index = self.tree.currentIndex()
        if not index.isValid():
            return

        parent = index.parent()
        if not parent.isValid():
            return

        node_name = index.data(0)
        if not node_name:
            return

        QTimer.singleShot(1, lambda: self._create_node_from_name(node_name))

    def _create_node_from_name(self, name):
        if self.flow_nodes:
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x()
            new_y = last_node.pos().y() + 180
        else:
            new_x, new_y = 20, 20
        self.add_flow_node(name, QPointF(new_x, new_y))


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    app.exec_()


if __name__ == '__main__':
    main()