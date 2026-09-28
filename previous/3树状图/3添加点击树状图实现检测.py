import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication,QMessageBox,QDialog,QVBoxLayout
)
# 打开主窗口，显示小窗口，模体ui窗口，设置layout
from PySide2.QtUiTools import QUiLoader # 导入ui
from PySide2.QtGui import QIcon, QImage, QPixmap  # 设置图标，显示图像
from PySide2.QtCore import QTimer, Qt # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2
from Detector import DetectorShape

uiloader = QUiLoader()

'''
添加点击树状图实现检测
'''

class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头相关参数
        self.cap = None # 视频捕获对象
        self.timer = None # 刷新定时器
        self.camera_id = 0  # 默认摄像头ID，可通过设置菜单修改

        # 设置按钮
        self.main_window.open_button.clicked.connect(self.open_camera) # 开启摄像头按钮
        self.main_window.close_button.clicked.connect(self.close_camera) # 关闭摄像头按钮

        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后 弹出 新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # ---------- 新增：树状图初始化 ----------
        self.tree = self.main_window.tree
        # 连接树状图点击信号
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        # 当前检测模式：None 表示无，'line' 表示直线检测，'circle' 表示圆检测
        self.detection_mode = None
        # -------------------------------------

    def open_camera(self):
        """打开摄像头并启动视频刷新"""
        if self.cap is not None and self.cap.isOpened():
            return

        self.cap = cv2.VideoCapture(self.camera_id)
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

        # ---------- 新增：根据检测模式处理帧 ----------
        data = []
        frame, data= self.process_frame(frame)
        # -----------------------------------------

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

    def set_camera_id(self):
        """设置摄像头ID(数字)"""
        loader = QUiLoader()
        widget = loader.load('SetCameraID.ui')
        '''
        # 直接使用widget打开窗口，这样显示的窗口是非模态的，同时可以操作main_window
        widget.show()
        widget.exec()
        '''
        if widget is None:
            return

        dialog = QDialog(self.main_window)
        # 使用QDialog相对于新创了一个新窗口，不是设计的ui窗口，所以窗口名Title需要重新设置，大小可以继承widget
        dialog.setWindowTitle("设置摄像头ID")
        dialog.setModal(True)  # 模态，SetCameraID窗口显示后main窗口不能使用
        dialog.setAttribute(Qt.WA_DeleteOnClose)  # 关闭后自动销毁

        # 将 widget 嵌入 dialog，不使用布局；相对于继承SetCameraID的布局，move()表示新窗口在原窗口的位置
        widget.setParent(dialog)
        widget.move(0, 0)

        # 禁止用户缩放对话框（保持固定大小）
        dialog.setFixedSize(widget.size())

        # 获取输入框和确定按钮
        line_edit = widget.findChild(QtWidgets.QLineEdit, "ID")
        ok_button = widget.findChild(QtWidgets.QPushButton, "SetID")
        if line_edit and ok_button:
            # 预填当前摄像头ID
            line_edit.setText(str(self.camera_id))

            def on_ok():
                """确定按钮槽函数：验证并保存摄像头ID"""
                id_str = line_edit.text().strip()
                if not id_str:
                    QMessageBox.warning(dialog, "输入错误", "摄像头ID不能为空")
                    return
                try:
                    new_id = int(id_str)
                    if new_id < 0:
                        raise ValueError
                    self.camera_id = new_id
                    dialog.accept()  # 关闭对话框
                except ValueError:
                    QMessageBox.warning(dialog, "输入错误", "请输入一个有效的非负整数")

            ok_button.clicked.connect(on_ok)
        else:
            # 如果UI中找不到对应控件，给出提示
            QMessageBox.warning(dialog, "界面错误", "未找到输入框或确定按钮，请检查SetCameraID.ui")

        # 模态显示，直到用户关闭
        dialog.exec_()



    # ---------- 新增函数 ----------
    def on_tree_item_clicked(self, item, column):
        """树状图项目点击事件：根据点击的项切换检测模式"""
        text = item.text(0)
        if text == "直线":
            self.detection_mode = 'line'
        elif text == "圆":
            self.detection_mode = 'circle'
        else:
            self.detection_mode = None   # 点击其他项（如“检测”、“识别”等）则停止检测

    def process_frame(self, frame):
        """根据当前检测模式，对视频帧进行处理并返回结果"""
        if self.detection_mode == 'line':
            return self.detector.line_detector(frame)
        elif self.detection_mode == 'circle':
            return self.detector.circle_detector(frame)
        else:
            return frame  # 无检测模式时直接返回原帧


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))#主窗口添加图标
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()