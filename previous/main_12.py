import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QGraphicsView, QFileDialog
)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QIcon, QImage, QPixmap
from PySide2.QtCore import QTimer, Qt, QPointF

import cv2

from Detector import DetectorShape
from FlowChart import NodeItem, EdgeItem, FlowchartView

"""
相较于main_11.py，清除了一些注释，简化代码
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

        # 存储当前加载的静态图片，用于删除方框后恢复原图
        self.current_static_image = None

        # 通过 findChild 找到被 tab 包裹的 video 控件
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")

        # 设置按钮
        self.main_window.camera_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)
        self.main_window.open_button.clicked.connect(self.open_file)

        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后 弹出 新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 创建树控件（仅用于双击创建方框）
        self.tree = self.main_window.tree

        # 流程图初始化
        self.flow_nodes = []
        self.flow_edges = []
        self.main_window.tree.setDragEnabled(True)
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction)

        # 获取 UI 中的 graphicsView，替换为 FlowchartView
        view = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        if view:
            parent = view.parent()
            geometry = view.geometry()
            view.deleteLater()
            self.main_window.graphicsView = FlowchartView(parent, main_window=self)
            self.main_window.graphicsView.setGeometry(geometry)
            self.main_window.graphicsView.show()
            # 每次刷新时全屏更新，防止有拖尾残影
            self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # 树控件 tree 绑定双击事件
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)


    def print_aaa(self):
        print(111)

    def open_file(self):
        """点击打开按钮后弹出文件选择框，可以选择图片或者视频进行导入"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "选择图片或视频",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;视频文件 (*.mp4 *.avi *.mkv);;所有文件(*.*)"
        )
        if not file_path:
            return

        # 无论当前是播放摄像头还是视频，先关闭释放资源
        self.close_camera()

        ext = file_path.lower()
        if ext.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            frame = cv2.imread(file_path)
            if frame is None:
                QMessageBox.warning(self.main_window, "错误", "无法读取图片文件")
                return

            self.current_static_image = frame
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
            self.timer.timeout.connect(self.update_frame) # type:ignore
            self.timer.start(30)
        else:
            QMessageBox.warning(self.main_window, "错误", "不支持的文件格式")

    def _process_and_display_frame(self, frame):
        """按流程图模式处理一帧图像，并渲染到 videoLabel"""
        # 拷贝一份图像，避免直接修改原始缓存
        work_frame = frame.copy()

        if self.flow_nodes:
            work_frame, data = self._run_flow_pipeline(work_frame)
        else:
            # 流程图没有方框时，直接返回原图
            work_frame, data = work_frame, []

        # OpenCV BGR -> RGB
        rgb_frame = cv2.cvtColor(work_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888) # type:ignore

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
        self.timer.timeout.connect(self.update_frame) # type:ignore
        self.timer.start(30)

    def close_camera(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self._is_video_file = False
        self.current_static_image = None

        self.videoLabel.clear()
        self.videoLabel.setText("video")
        self.videoLabel.setStyleSheet(
            "background-color: black; color: white; font-size: 24px; font-weight: bold;")

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
        """按流程图节点顺序执行检测"""
        img = frame
        data = []
        for node in self.flow_nodes:
            if node.name == "直线":
                img, d = self.detector.line_detector(img)
                data.extend(d)
            elif node.name == "圆":
                img, d = self.detector.circle_detector(img)
                data.extend(d)
            elif node.name == "灰度":
                img, _ = self.detector.gray(img)
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

    def add_flow_node(self, name, pos):
        node = NodeItem(name, pos)
        self.main_window.graphicsView.scene.addItem(node)
        node.positionChanged.connect(self.update_all_edges)
        self.flow_nodes.append(node)

        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

        return node

    def add_edge(self, start_node, end_node):
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                return
        edge = EdgeItem(start_node, end_node)
        self.main_window.graphicsView.scene.addItem(edge)
        self.flow_edges.append(edge)
        self.update_all_edges()

        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def delete_flow_node(self, node_to_delete):
        if node_to_delete not in self.flow_nodes:
            return

        edges_to_remove = []
        for edge in self.flow_edges:
            if edge.start_node == node_to_delete or edge.end_node == node_to_delete:
                edges_to_remove.append(edge)

        for edge in edges_to_remove:
            self.main_window.graphicsView.scene.removeItem(edge)
            self.flow_edges.remove(edge)

        self.main_window.graphicsView.scene.removeItem(node_to_delete)
        self.flow_nodes.remove(node_to_delete)
        self.update_all_edges()

        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def update_all_edges(self):
        for edge in self.flow_edges:
            edge.update_positions()

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

    def delete_edge(self, edge_to_delete):
        if edge_to_delete not in self.flow_edges:
            return
        self.main_window.graphicsView.scene.removeItem(edge_to_delete)
        self.flow_edges.remove(edge_to_delete)
        self.update_all_edges()

        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()