import numpy as np
from PySide2.QtWidgets import QApplication,QMessageBox
from PySide2.QtUiTools import QUiLoader # 导入ui
from PySide2.QtGui import QIcon, QImage, QPixmap, Qt  # 设置图标，显示图像
from PySide2.QtCore import QTimer # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2

uiloader = QUiLoader()

'''
添加打开和关闭摄像头
'''

class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')

        # 摄像头相关参数
        self.cap = None # 视频捕获对象
        self.timer = None # 刷新定时器

        # 设置按钮
        self.main_window.open_button.clicked.connect(self.open_camera) # 开启摄像头按钮
        self.main_window.close_button.clicked.connect(self.close_camera) # 关闭摄像头按钮

        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

    def open_camera(self):
        """打开摄像头并启动视频刷新"""
        if self.cap is not None and self.cap.isOpened():
            return

        self.cap = cv2.VideoCapture(1)
        if not self.cap.isOpened():
            # 如果识别不到摄像头标签，则弹出警告的小窗口
            QMessageBox.warning(self.main_window, "错误", "无法打开摄像头，请检查设备连接")
            self.cap = None
            return

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame) # type: ignore
        self.timer.start(30)

    def close_camera(self):
        """关闭摄像头，停止定时器，清空显示区域"""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.main_window.video.clear() # 关闭摄像头
        self.main_window.video.setText("video") # 设置label里面的文本为video
        # 设置video背景为黑色，虽然在stylesheet里面设置，但是关闭摄像头时会情况，所以需要在代码中修改
        self.main_window.video.setStyleSheet(
            "background-color: black; color: white; font-size: 24px; font-weight: bold;")

    def update_frame(self):
        """定时器槽函数：读取摄像头帧并显示到 video 标签"""
        if self.cap is None or not self.cap.isOpened():
            # 识别不到摄像头时或者打开摄像头失败时执行返回，不读取视频帧
            return

        ret, frame = self.cap.read()
        if not ret:
            self.close_camera()
            QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
            return

        # OpenCV BGR -> RGB ; qt和opencv使用的颜色通道顺序不同，所以需要转换
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888) # type: ignore

        # 缩放并显示，保持宽高比（使用 Qt.KeepAspectRatio）
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.main_window.video.size(), Qt.KeepAspectRatio)
        self.main_window.video.setPixmap(scaled)
        self.main_window.video.setStyleSheet("")  # 清除文字样式


    def close_event(self,event):
        """窗口关闭时释放摄像头"""
        self.close_camera()
        event.accept() # 允许窗口关闭


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))#主窗口添加图标
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()