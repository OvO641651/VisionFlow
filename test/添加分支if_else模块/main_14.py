import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QGraphicsView, QFileDialog
)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QIcon, QImage, QPixmap
from PySide2.QtCore import QTimer, Qt, QPointF
from collections import deque

import cv2

from Detector import DetectorShape
from FlowChart_1 import NodeItem, EdgeItem, FlowchartView


uiloader = QUiLoader()

class MainWindow:
    def __init__(self):
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        self.cap = None
        self.timer = None
        self.camera_id = 0
        self._is_video_file = False

        self.current_static_image = None
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")

        self.main_window.camera_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)
        self.main_window.open_button.clicked.connect(self.open_file)
        self.main_window.closeEvent = self.close_event
        self.main_window.action.triggered.connect(self.set_camera_id)

        self.tree = self.main_window.tree

        self.flow_nodes = []
        self.flow_edges = []
        self.main_window.tree.setDragEnabled(True)
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction)

        view = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        if view:
            parent = view.parent()
            geometry = view.geometry()
            view.deleteLater()
            self.main_window.graphicsView = FlowchartView(parent, main_window=self)
            self.main_window.graphicsView.setGeometry(geometry)
            self.main_window.graphicsView.show()
            self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)

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
            self.timer.timeout.connect(self.update_frame)
            self.timer.start(30)
        else:
            QMessageBox.warning(self.main_window, "错误", "不支持的文件格式")

    def _process_and_display_frame(self, frame):
        work_frame = frame.copy()
        if self.flow_nodes:
            work_frame, data = self._run_flow_pipeline(work_frame)
        else:
            work_frame, data = work_frame, []

        rgb_frame = cv2.cvtColor(work_frame, cv2.COLOR_BGR2RGB)
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
        self.current_static_image = None
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

    # ================= 【核心逻辑：路由和拓扑检测】 =================

    def _run_flow_pipeline(self, frame):
        """按拓扑序执行检测，支持条件分支（If...Else）"""
        img = frame
        data = []
        if not self.flow_nodes:
            return img, data

        # ====== 【核心修复】 ======
        # 如果画布上有节点，但没有任何连线，说明还没有构成流程图，直接返回原图
        if not self.flow_edges:
            return img, data
        # ========================

        # 1. 建立图结构和入度统计
        in_degree = {node: 0 for node in self.flow_nodes}
        graph = {node: [] for node in self.flow_nodes}
        for edge in self.flow_edges:
            if edge.end_node not in graph[edge.start_node]:
                graph[edge.start_node].append(edge)
            in_degree[edge.end_node] += 1

        # 2. 寻找起始节点（入度为0的节点）
        queue = deque([node for node in self.flow_nodes if in_degree[node] == 0])
        executed = set()

        while queue:
            node = queue.popleft()
            if node in executed:
                continue
            executed.add(node)

            # 执行节点对应算法
            if node.name == "直线":
                img, d = self.detector.line_detector(img)
                data.extend(d)
            elif node.name == "圆":
                img, d = self.detector.circle_detector(img)
                data.extend(d)
            elif node.name == "灰度":
                img, _ = self.detector.gray(img)

            # 【关键扩展】：处理条件分支
            elif node.name == "条件分支":
                # 示例条件：检测到的数据长度大于 5 时走右侧蓝点(端口1)，否则走左侧蓝点(端口0)
                # 实际使用时，这里可以根据用户界面设定的参数或上一阶段的数据进行判断
                branch_choice = 1 if len(data) > 5 else 0

                # 寻找符合条件的连线
                next_node = None
                for edge in graph[node]:
                    if edge.from_port_index == branch_choice:
                        next_node = edge.end_node
                        break

                if next_node is not None and next_node not in executed:
                    queue.append(next_node)
                continue  # 条件分支已处理完路由，跳过常规的后续节点遍历

            # 3. 普通模块：将所有的后继节点加入队列
            for edge in graph[node]:
                if edge.end_node not in executed:
                    queue.append(edge.end_node)

        return img, data
    # ============================================================

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

    def add_edge(self, start_node, end_node, from_port_index=0):
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                return
        edge = EdgeItem(start_node, end_node, from_port_index)
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