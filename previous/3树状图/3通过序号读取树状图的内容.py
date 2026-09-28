import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout
)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QIcon, QImage, QPixmap
from PySide2.QtCore import QTimer, Qt

import cv2

uiloader = QUiLoader()

'''
通过序号读取树状图的内容
'''

class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')

        # 摄像头相关参数
        self.cap = None
        self.timer = None
        self.camera_id = 0

        # 设置按钮
        self.main_window.open_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)

        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后弹出新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # ---------- 树状图初始化 ----------
        self.tree = self.main_window.tree
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.detection_mode = None  # 当前检测模式：'line'/'circle'/None
        # -------------------------------------

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
        self.main_window.video.clear()
        self.main_window.video.setText("video")
        self.main_window.video.setStyleSheet(
            "background-color: black; color: white; font-size: 24px; font-weight: bold;")

    def update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            self.close_camera()
            QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
            return

        # 根据检测模式处理帧
        frame = self.process_frame(frame)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.main_window.video.size(), Qt.KeepAspectRatio)
        self.main_window.video.setPixmap(scaled)
        self.main_window.video.setStyleSheet("")

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

    # ---------- 树状图点击处理（使用索引路径，不依赖文本）----------
    def on_tree_item_clicked(self, item, column):
        """
        根据点击项的层级索引来切换检测模式。
        索引路径：
            (0, 0) -> 检测 -> 直线
            (0, 1) -> 检测 -> 圆
        其他任意项 -> 取消检测
        """
        # 构造索引路径
        if item.parent() is None:
            # 顶层节点，路径长度为1
            top_idx = self.tree.indexOfTopLevelItem(item)
            path = (top_idx,)
        else:
            # 有父节点，父节点是顶层
            parent = item.parent()
            top_idx = self.tree.indexOfTopLevelItem(parent)
            child_idx = parent.indexOfChild(item)
            path = (top_idx, child_idx)

        # 根据路径设置检测模式
        if path == (0, 0):
            self.detection_mode = 'line'
        elif path == (0, 1):
            self.detection_mode = 'circle'
        else:
            self.detection_mode = None

    def process_frame(self, frame):
        """根据检测模式对帧进行处理"""
        if self.detection_mode == 'line':
            return self.line_detect(frame)
        elif self.detection_mode == 'circle':
            return self.circle_detect(frame)
        else:
            return frame




    def line_detect(self, frame):
        img = frame.copy()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=50, maxLineGap=10)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        return img

    def circle_detect(self, frame):
        img = frame.copy()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
                                   param1=100, param2=30, minRadius=10, maxRadius=200)
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                cv2.circle(img, (i[0], i[1]), i[2], (0, 255, 0), 2)
                cv2.circle(img, (i[0], i[1]), 2, (0, 0, 255), 3)
        return img




def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()