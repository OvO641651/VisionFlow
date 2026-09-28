import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QGraphicsView, QFileDialog
)
# 打开主窗口，显示小窗口，模体ui窗口，设置layout，设置流程图画布，导入文件
from PySide2.QtUiTools import QUiLoader # 导入ui
from PySide2.QtGui import QIcon, QImage, QPixmap  # 设置图标，显示图像
from PySide2.QtCore import QTimer, Qt, QPointF # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2

from Detector import DetectorShape
from FlowChart import NodeItem, EdgeItem, FlowchartView

"""
将一个方框可以引出多个曲线分支给功能从FlowChart.py中移植到main.py中
"""


uiloader = QUiLoader()

class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头相关参数
        self.cap = None
        self.timer = None
        self.camera_id = 0
        self._is_video_file = False

        # 通过 findChild 找到被 tab 包裹的 video 和 graphicsView 控件
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")

        # 设置按钮
        self.main_window.camera_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)
        self.main_window.open_button.clicked.connect(self.open_file)

        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后 弹出 新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 创建树控件
        self.tree = self.main_window.tree
        self.main_window.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.detection_mode = None

        # 流程图初始化
        self.flow_nodes = []  # 存放所有方框
        self.flow_edges = []  # 存放所有连线
        self.main_window.tree.setDragEnabled(True)
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction)

        # 替换 graphicsView 为 FlowchartView
        view = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        if view:
            parent = view.parent()
            geometry = view.geometry()
            view.deleteLater()
            self.main_window.graphicsView = FlowchartView(parent, main_window=self)
            self.main_window.graphicsView.setGeometry(geometry)
            self.main_window.graphicsView.show()
            self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # 树控件绑定双击事件
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)


    # ================= 【新增/修改的核心方法】 =================

    def add_flow_node(self, name, pos):
        """【修改】创建方框，不再自动连线，只做记录和信号绑定"""
        node = NodeItem(name, pos)
        self.main_window.graphicsView.scene.addItem(node)
        # 绑定移动刷新信号
        node.positionChanged.connect(self.update_all_edges)
        self.flow_nodes.append(node)
        return node

    def add_edge(self, start_node, end_node):
        """【新增】从蓝点手动拖拽到红点触发的连线生成"""
        # 防止重复连线
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                return
        edge = EdgeItem(start_node, end_node)
        self.main_window.graphicsView.scene.addItem(edge)
        self.flow_edges.append(edge)
        self.update_all_edges()

    def delete_flow_node(self, node_to_delete):
        """【修改】删除节点，并断开所有与之相连的线（不自动重连）"""
        if node_to_delete not in self.flow_nodes:
            return
        # 找出与该节点相连的所有线
        edges_to_remove = []
        for edge in self.flow_edges:
            if edge.start_node == node_to_delete or edge.end_node == node_to_delete:
                edges_to_remove.append(edge)
        # 从画布和列表中移除这些线
        for edge in edges_to_remove:
            self.main_window.graphicsView.scene.removeItem(edge)
            self.flow_edges.remove(edge)
        # 移除节点本身
        self.main_window.graphicsView.scene.removeItem(node_to_delete)
        self.flow_nodes.remove(node_to_delete)
        self.update_all_edges()

    def update_all_edges(self):
        """【修改】遍历所有连线，让连线自身去获取端点坐标并刷新"""
        for edge in self.flow_edges:
            edge.update_positions()

    def _on_tree_double_click(self, item, column):
        """【修改】安全提取双击的节点名称，直接创建方框"""
        index = self.tree.currentIndex()
        if not index.isValid():
            return
        parent = index.parent()
        if not parent.isValid():
            return
        name = index.data(0)
        if not name:
            return

        if self.flow_nodes:
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x()
            new_y = last_node.pos().y() + 180
        else:
            new_x, new_y = 20, 20
        self.add_flow_node(name, QPointF(new_x, new_y))

    # ============================================================

    # ================= 【保留原有的摄像头和检测方法】 =================

    def print_aaa(self):
        print(111)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "选择图片或视频",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;视频文件 (*.mp4 *.avi *.mkv);;所有文件(*.*)"
        )
        if not file_path:
            return
        self.close_camera()
        ext = file_path.lower()
        if ext.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            frame = cv2.imread(file_path)
            if frame is None:
                QMessageBox.warning(self.main_window, "错误", "无法读取图片文件")
                return
            self._process_and_display_frame(frame)
        elif ext.endswith(('.mp4', '.avi', '.mkv')):
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                QMessageBox.warning(self.main_window, "错误", "无法打开视频文件")
                return
            self.cap = cap
            self._is_video_file = True
            if self.timer is not None:
                self.timer.stop()
                self.timer = None
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_frame)
            self.timer.start(30)
        else:
            QMessageBox.warning(self.main_window, "错误", "不支持的文件格式")

    def _process_and_display_frame(self, frame):
        if self.flow_nodes:
            frame, data = self._run_flow_pipeline(frame)
        else:
            frame, data = self.process_frame(frame)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.videoLabel.size(), Qt.KeepAspectRatio)
        self.videoLabel.setPixmap(scaled)
        self.videoLabel.setStyleSheet("")

    def open_camera(self):
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

    def close_camera(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self._is_video_file = False
        self.videoLabel.clear()
        self.videoLabel.setText("video")
        self.videoLabel.setStyleSheet("background-color: black; color: white; font-size: 24px; font-weight: bold;")

    def update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            if self._is_video_file:
                if self.timer is not None:
                    self.timer.stop()
                    self.timer = None
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                self._is_video_file = False
                return
            else:
                self.close_camera()
                QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
                return
        self._process_and_display_frame(frame)

    def _run_flow_pipeline(self, frame):
        img = frame
        data = []
        for node in self.flow_nodes:
            if node.name == "直线":
                img, d = self.detector.line_detector(img)
                data.extend(d)
            elif node.name == "圆":
                img, d = self.detector.circle_detector(img)
                data.extend(d)
        return img, data

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

def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))#主窗口添加图标
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()