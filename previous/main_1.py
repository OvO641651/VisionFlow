from PySide6.QtWidgets import QApplication
from PySide6.QtUiTools import QUiLoader # 导入ui
from PySide6.QtGui import QIcon # 设置图标
from PySide6.QtCore import QTimer # 图像显示需要设置线程

import cv2

uiloader = QUiLoader()

'''
打开ui界面
'''

class Main_Window:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('SetCameraID.ui')

        # 设置按钮
        #self.main_window.open_button.clicked.connect(self.print_test) # 开启摄像头按钮
        #self.main_window.close_button.clicked.connect(self.print_test) # 关闭摄像头按钮

    def print_test(self):
        print(111)


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))#主窗口添加图标
    main_window = Main_Window()
    main_window.main_window.show()
    app.exec()

if __name__ == '__main__':
    main()