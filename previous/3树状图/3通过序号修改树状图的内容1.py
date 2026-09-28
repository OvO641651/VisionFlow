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
通过序号修改树状图的内容
'''

class MainWindow:
    def __init__(self):
        self.main_window = QUiLoader().load('main.ui')

        self.cap = None
        self.timer = None
        self.camera_id = 0

        # 新增变量：用来存储当前选中的检测模式
        self.current_detection_mode = None  # 'line', 'circle', 'face', 'color', None(预览)

        self.main_window.open_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)

        # 绑定树形控件的点击信号
        self.main_window.tree.itemClicked.connect(self.on_tree_item_clicked)

        self.main_window.closeEvent = self.close_event
        self.main_window.action.triggered.connect(self.set_camera_id)

    # ===================== 新增：直线检测函数 =====================
    def detect_line(self, frame):
        """输入帧，返回绘制了直线的帧"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
        return frame

    # ===================== 新增：圆形检测函数 =====================
    def detect_circle(self, frame):
        """输入帧，返回绘制了圆形的帧"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=100, param1=50, param2=30, minRadius=10,
                                   maxRadius=0)
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                center = (i[0], i[1])
                radius = i[2]
                cv2.circle(frame, center, radius, (0, 255, 0), 2)
                cv2.circle(frame, center, 2, (0, 0, 255), 3)
        return frame

    # ===================== 修改：树形控件点击事件（使用索引判断） =====================
    def on_tree_item_clicked(self, item, column):
        parent = item.parent()
        if parent is None:
            # 点击的是根节点（如“检测”、“识别”等）→ 清空模式
            self.current_detection_mode = None
            self.main_window.setWindowTitle("Visual System")
            return

        # 获取当前点击的是父节点下的第几个子节点（索引）
        index = parent.indexOfChild(item)

        # ===== 新增：获取父节点在整个树形控件中的顶层索引 =====
        parent_index = self.main_window.tree.indexOfTopLevelItem(parent)

        # 根据父节点的顶层索引判断属于哪个组（完全避免文字比较）
        if parent_index == 0:  # 顶层第1个：“检测”
            if index == 0:  # “直线”
                self.current_detection_mode = "line"
            elif index == 1:  # “圆”
                self.current_detection_mode = "circle"
        elif parent_index == 1:  # 顶层第2个：“识别”
            if index == 0:  # “人脸”
                self.current_detection_mode = "face"
            elif index == 1:  # “颜色”
                self.current_detection_mode = "color"
        else:
            self.current_detection_mode = None

        # 更新窗口标题，显示当前模式
        mode_names = {
            "line": "直线检测",
            "circle": "圆形检测",
            "face": "人脸检测",
            "color": "颜色检测"
        }
        mode_str = mode_names.get(self.current_detection_mode, "普通预览")
        self.main_window.setWindowTitle(f"Visual System - 当前模式: {mode_str}")



    # ===================== 原始函数：完全不动 =====================
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

    # ===================== update_frame：只修改内部调用点 =====================
    def update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if not ret:
            self.close_camera()
            QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
            return

        # ======= 根据当前模式调用对应的检测函数（不直接写检测代码） =======
        processed_frame = frame.copy()

        if self.current_detection_mode == "line":
            processed_frame = self.detect_line(processed_frame)
        elif self.current_detection_mode == "circle":
            processed_frame = self.detect_circle(processed_frame)
        # =============================================================

        # BGR -> RGB 并显示（保留原始代码）
        rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
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
                    QMessageBox.warning(dialog, "输入错误", "请输入有效的非负整数")

            ok_button.clicked.connect(on_ok)
        else:
            QMessageBox.warning(dialog, "界面错误", "未找到输入框或确定按钮，请检查SetCameraID.ui")

        dialog.exec_()


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    app.exec_()


if __name__ == '__main__':
    main()