import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout  # 新增 QVBoxLayout 用于布局
)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QIcon, QImage, QPixmap
from PySide2.QtCore import QTimer, Qt, QPointF  # 新增 QPointF

import cv2
from Detector import DetectorShape
from Flow import FlowchartCanvas  # 引入流程图纯净画布组件

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
        self.main_window.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.detection_mode = None

        # ================= [ 新增：流程图整合 ] =================
        # 将 UI 里的 graphicsView 替换为纯画布 FlowchartCanvas
        old_view = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        if old_view:
            parent = old_view.parent()  # 获取所在的 tab 页面
            geometry = old_view.geometry()  # 获取原有位置和大小
            old_view.deleteLater()  # 移除原有的空画布

            # 创建流程图画布，并传入自身（self）以便它能访问左侧树控件
            self.flow_canvas = FlowchartCanvas(parent, main_window=self)
            self.flow_canvas.setGeometry(geometry)

            # 确保父页面有布局，以便画布能随窗口自动缩放
            layout = parent.layout()
            if not layout:
                layout = QVBoxLayout(parent)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(self.flow_canvas)
            else:
                layout.addWidget(self.flow_canvas)

        # 启用左侧树控件的拖拽和双击功能
        self.main_window.tree.setDragEnabled(True)
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction)
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)
        # ========================================================

    # ----- [ 新增：流程图交互与方法转发 ] -----
    def add_flow_node(self, name, pos):
        """转发给画布的添加节点方法"""
        if hasattr(self, 'flow_canvas'):
            return self.flow_canvas.add_flow_node(name, pos)

    def delete_flow_node(self, node_to_delete):
        """转发给画布的删除节点方法"""
        if hasattr(self, 'flow_canvas'):
            self.flow_canvas.delete_flow_node(node_to_delete)

    def _on_tree_double_click(self, item, column):
        """双击左侧树节点创建方框"""
        # 【核心修复】：千万不要用信号传过来的 item！因为极易被底层提前销毁。
        # 直接通过 self.tree.currentItem() 实时获取控件当前选中的对象，永远安全。
        current = self.tree.currentItem()

        # 如果获取失败，或者点击的是根节点（一级标题），则直接返回，不创建方框
        if current is None or current.parent() is None:
            return

        name = current.text(0)
        nodes = self.flow_canvas.flow_nodes if hasattr(self, 'flow_canvas') else []
        if nodes:
            last_node = nodes[-1]
            # 依次向下排列（Y轴+180）
            new_x = last_node.pos().x()
            new_y = last_node.pos().y() + 180
        else:
            new_x, new_y = 20, 20
        self.add_flow_node(name, QPointF(new_x, new_y))

    # ------------------------------------------

    # ----- [ 原有摄像头方法和检测逻辑，稍作修改以判断流程图 ] -----
    def open_camera(self):
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
        # 修改点：检测流程图画布是否包含节点
        if hasattr(self, 'flow_canvas') and self.flow_canvas.flow_nodes:
            frame, data = self._run_flow_pipeline(frame)  # 执行流水线检测
        else:
            frame, data = self.process_frame(frame)  # 执行单模式检测

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
        for node in self.flow_canvas.flow_nodes:
            if node.name == "直线":
                img, d = self.detector.line_detector(img)
                data.extend(d)
            elif node.name == "圆":
                img, d = self.detector.circle_detector(img)
                data.extend(d)
            # 后续可加入人脸、颜色等
        return img, data

    # ----- [ 原有未修改的方法保留 ] -----
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
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    app.exec_()


if __name__ == '__main__':
    main()