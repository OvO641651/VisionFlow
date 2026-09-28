import numpy as np
import traceback
import sys

from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog
)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QIcon, QImage, QPixmap
from PySide2.QtCore import QTimer, Qt

import cv2
from Detector import DetectorShape

'''
参数树状图表修成两列
'''


# ---------- 全局异常捕获 ----------
def _excepthook(etype, value, tb):
    lines = traceback.format_exception(etype, value, tb)
    err = ''.join(lines)
    print(err, file=sys.stderr)
    if QApplication.instance() is not None:
        QMessageBox.critical(None, "未捕获的异常", err)
    sys.exit(1)

sys.excepthook = _excepthook


class MainWindow:
    def __init__(self):
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头
        self.cap = None
        self.timer = None
        self.camera_id = 0

        # 按钮
        self.main_window.open_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)
        self.main_window.closeEvent = self.close_event
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 左侧检测类型树
        self.tree = self.main_window.tree
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.detection_mode = None

        # 右侧参数树（两列：参数名 / 参数值）
        self.treeWidget = self.main_window.treeWidget
        self.treeWidget.itemChanged.connect(self.on_param_item_changed)
        # 设置列标题
        self.treeWidget.setHeaderLabels(["参数", "值"])

        # 输出文本框
        self.plainTextEdit = self.main_window.plainTextEdit

        # 默认参数
        self.line_params = {
            'rho': 1.0,
            'theta': np.pi / 180,
            'threshold': 100,
            'minLineLength': 100.0,
            'maxLineGap': 10.0,
            'canny_low': 50,
            'canny_high': 150,
            'aperture': 3
        }
        self.circle_params = {
            'method': cv2.HOUGH_GRADIENT,
            'dp': 1.0,
            'minDist': 10.0,
            'param1': 100.0,
            'param2': 50.0,
            'minRadius': 0,
            'maxRadius': 0
        }

        self._frame_bytes = None
        self.treeWidget.clear()

    # ========== 摄像头控制 ==========
    def open_camera(self):
        if self.cap is not None and self.cap.isOpened():
            return
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
        except Exception as e:
            QMessageBox.warning(self.main_window, "错误", f"打开摄像头失败：{e}")
            return
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
        try:
            if self.cap is None or not self.cap.isOpened():
                return
            ret, frame = self.cap.read()
            if not ret:
                self.close_camera()
                QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
                return

            processed = self.process_frame(frame)

            rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            rgb = np.ascontiguousarray(rgb)
            self._frame_bytes = rgb.tobytes()
            bytes_per_line = w * ch
            qt_img = QImage(self._frame_bytes, w, h, bytes_per_line, QImage.Format_RGB888)

            pixmap = QPixmap.fromImage(qt_img)
            scaled = pixmap.scaled(self.main_window.video.size(), Qt.KeepAspectRatio)
            self.main_window.video.setPixmap(scaled)
            self.main_window.video.setStyleSheet("")
        except Exception:
            traceback.print_exc()

    def close_event(self, event):
        self.close_camera()
        event.accept()

    # ========== 设置摄像头ID ==========
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

    # ========== 左侧树状图 ==========
    def on_tree_item_clicked(self, item, _column):
        self.treeWidget.blockSignals(True)
        self.plainTextEdit.clear()
        self.treeWidget.clear()
        self.detection_mode = None

        path = self._find_item_path(item)
        if path is None:
            self.treeWidget.blockSignals(False)
            return

        if path == (0, 0):
            self.detection_mode = 'line'
            self._fill_params_tree('line')
        elif path == (0, 1):
            self.detection_mode = 'circle'
            self._fill_params_tree('circle')
        else:
            self.plainTextEdit.appendPlainText("未选择检测模式")

        self.treeWidget.blockSignals(False)

    def _find_item_path(self, target):
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            top = root.child(i)
            if top == target:
                return (i,)
            for j in range(top.childCount()):
                if top.child(j) == target:
                    return (i, j)
        return None

    # ========== 右侧参数树填充（两列） ==========
    def _fill_params_tree(self, mode):
        self.treeWidget.clear()
        if mode == 'line':
            params = self.line_params
        elif mode == 'circle':
            params = self.circle_params
        else:
            return

        for key, val in params.items():
            if key == 'method':   # method 不显示
                continue
            # 第一列：参数名，第二列：值
            item = QtWidgets.QTreeWidgetItem([key, str(val)])
            # 使用 UserRole 存储参数名，防止第一列被篡改
            item.setData(0, Qt.UserRole, key)
            # 整个 item 设为可编辑（但后边会限制第一列）
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.treeWidget.addTopLevelItem(item)

    # ========== 参数编辑处理（两列版本） ==========
    def on_param_item_changed(self, item, column):
        if self.detection_mode is None:
            return

        # 如果修改的是第一列（参数名），则恢复原始名称
        if column == 0:
            original_key = item.data(0, Qt.UserRole)
            if original_key is not None:
                self.treeWidget.blockSignals(True)
                item.setText(0, original_key)
                self.treeWidget.blockSignals(False)
            return

        # 只处理第二列的编辑（参数值）
        params = self.line_params if self.detection_mode == 'line' else self.circle_params
        key = item.data(0, Qt.UserRole)          # 获取存储的真实参数名
        if key is None or key not in params:
            # 异常情况，恢复显示
            self._restore_item(item, key, None)
            return

        value_str = item.text(1).strip()
        orig = params[key]
        try:
            new_val = self._cast(value_str, orig)
        except (ValueError, TypeError):
            QMessageBox.warning(self.main_window, "参数错误",
                                f"'{value_str}' 不能转换为 {type(orig).__name__}")
            self._restore_item(item, key, orig)
            return

        params[key] = new_val

    def _restore_item(self, item, key, val):
        """恢复参数项的第二列显示"""
        self.treeWidget.blockSignals(True)
        if key is not None:
            item.setText(0, key)               # 确保第一列也正确
        if val is not None:
            item.setText(1, str(val))
        self.treeWidget.blockSignals(False)

    @staticmethod
    def _cast(s, orig):
        if isinstance(orig, bool):
            return s.lower() in ('true', '1', 'yes')
        return type(orig)(s)

    # ========== 视频帧检测处理 ==========
    def process_frame(self, frame):
        try:
            if self.detection_mode == 'line':
                ret = self.detector.line_detector(frame, **self.line_params)
                if isinstance(ret, tuple):
                    img, lines = ret
                else:
                    img = ret
                    lines = []
                self._show_lines(lines)
                return img
            elif self.detection_mode == 'circle':
                ret = self.detector.circle_detector(frame, **self.circle_params)
                if isinstance(ret, tuple):
                    img, circles = ret
                else:
                    img = ret
                    circles = []
                self._show_circles(circles)
                return img
        except Exception:
            traceback.print_exc()
        return frame

    # ========== 结果输出 ==========
    def _show_lines(self, lines):
        self.plainTextEdit.clear()
        if not lines:
            self.plainTextEdit.appendPlainText("未检测到直线")
            return
        self.plainTextEdit.appendPlainText(f"检测到 {len(lines)} 条直线：")
        for i, (x1, y1, x2, y2) in enumerate(lines, 1):
            length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            self.plainTextEdit.appendPlainText(
                f"直线{i}: ({x1},{y1})→({x2},{y2}) 长度={length:.1f}px")

    def _show_circles(self, circles):
        self.plainTextEdit.clear()
        if not circles:
            self.plainTextEdit.appendPlainText("未检测到圆")
            return
        self.plainTextEdit.appendPlainText(f"检测到 {len(circles)} 个圆：")
        for i, (x, y, r) in enumerate(circles, 1):
            self.plainTextEdit.appendPlainText(f"圆{i}: 圆心({x},{y}) 半径={r}px")


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()