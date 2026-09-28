import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QGraphicsView
)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QIcon, QImage, QPixmap
from PySide2.QtCore import QTimer, Qt, QPointF

import cv2

from Detector import DetectorShape
# ========== 关键导入：直接从 FlowChart.py 引入核心类 ==========
from FlowChart import NodeItem, EdgeItem, FlowchartView
# ============================================================

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

        # 通过 findChild 找到被 tab 包裹的 video 控件
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")

        # 设置按钮
        self.main_window.open_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)
        self.main_window.closeEvent = self.close_event
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 获取左侧的树控件
        self.tree = self.main_window.tree
        #self.main_window.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.detection_mode = None

        # ================= [ 流程图初始化 ] =================
        # 1. 初始化节点和连线列表
        self.flow_nodes = []  # 存放所有方块
        self.flow_edges = []  # 存放所有连线

        # 2. 启用左侧树控件的拖拽功能
        self.main_window.tree.setDragEnabled(True)
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction)

        # 3. 获取 UI 中的 graphicsView，替换为 FlowchartView
        old_view = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        if old_view:
            parent = old_view.parent()
            geometry = old_view.geometry()
            old_view.deleteLater()

            # 实例化 FlowchartView，把主窗口 self 传进去
            self.main_window.graphicsView = FlowchartView(parent, main_window=self)
            self.main_window.graphicsView.setGeometry(geometry)
            self.main_window.graphicsView.show()
            self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  # 每次刷新时全屏更新，防止有拖尾残影

        # 4. 绑定双击事件 (使用 `self.tree.currentItem()` 防止崩溃)
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)
        # ====================================================

    # ----- [ 流程图核心逻辑（从 TestWindow 搬过来的）] -----
    def add_flow_node(self, name, pos):
        """外部调用的添加节点方法"""
        node = NodeItem(name, pos)
        self.main_window.graphicsView.scene.addItem(node)

        # 绑上连线刷新信号，移动时自动更新
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
        """外部调用的删除节点方法"""
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
        """手动触发全画面连线刷新"""
        for i, edge in enumerate(self.flow_edges):
            start_node = self.flow_nodes[i]
            end_node = self.flow_nodes[i + 1]
            new_start = start_node.get_output_pos()
            new_end = end_node.get_input_pos()
            edge.update_positions(new_start, new_end)

    def _on_tree_double_click(self, item, column):
        """双击左侧树节点创建方框"""
        # 核心修复：防止 PySide2 中信号传入的 item 被底层提前销毁导致崩溃
        current = self.tree.currentItem()
        if current is None or current.parent() is None:
            return

        name = current.text(0)
        nodes = self.flow_nodes
        if nodes:
            last_node = nodes[-1]
            # 依次向下排列（Y轴+180）
            new_x = last_node.pos().x()
            new_y = last_node.pos().y() + 180
        else:
            new_x, new_y = 20, 20
        self.add_flow_node(name, QPointF(new_x, new_y))
    # -----------------------------------------------------

    # ----- [ 原有摄像头和检测逻辑 ] -----
    def open_camera(self):
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
        self.videoLabel.clear()
        self.videoLabel.setText("video")
        self.videoLabel.setStyleSheet("background-color: black; color: white; font-size: 24px; font-weight: bold;")

    def update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            self.close_camera()
            QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
            return

        data = []
        # 优先执行流程图中的多个检测，否则执行单模式检测
        if self.flow_nodes:
            frame, data = self._run_flow_pipeline(frame)
        else:
            pass
            #frame, data = self.process_frame(frame)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.videoLabel.size(), Qt.KeepAspectRatio)
        self.videoLabel.setPixmap(scaled)
        self.videoLabel.setStyleSheet("")

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
            # 后续可加入人脸、颜色等
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

'''
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
'''

def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()