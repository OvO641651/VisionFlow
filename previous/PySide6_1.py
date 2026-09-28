import sys
import cv2
import numpy as np
from PIL import Image, ImageTk
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMenu, QDialog, QLineEdit,
    QMessageBox, QFrame, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtGui import QPixmap, QImage, QAction
from PySide6.QtCore import Qt, QTimer

import hand_tracking_particles
import Color_Detector
import Face_Detector


class VisualSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visual System")
        self.resize(800, 600)

        # 变量
        self.camera_id = "0"
        self.running = False
        self.cap = None
        self.tracker = None
        self.color_detector = None
        self.face_detector = None
        self.mode = None          # 'hand', 'color', 'face', 'preview', 'shape'
        self.shape_type = None    # 'line', 'circle'

        # 定时器
        self.timer = QTimer()
        self.timer.setInterval(20)  # ~50 FPS
        self.timer.timeout.connect(self.process_frame)

        # --- 菜单栏 ---
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("设置")
        cam_action = QAction("摄像头设置...", self)
        cam_action.triggered.connect(self.open_camera_settings)
        settings_menu.addAction(cam_action)

        # --- 主布局 ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- 左侧面板 ---
        left_panel = QFrame()
        left_panel.setFixedWidth(200)
        left_panel.setStyleSheet("background-color: #f0f0f0; border-radius: 5px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # 打开摄像头（预览）
        self.cam_preview_btn = QPushButton("打开摄像头")
        self.cam_preview_btn.setFixedHeight(40)
        self.cam_preview_btn.setStyleSheet(self._get_button_style("#9C27B0"))
        self.cam_preview_btn.clicked.connect(self.start_camera_preview)
        self._bind_button_feedback(self.cam_preview_btn, "#9C27B0")
        left_layout.addWidget(self.cam_preview_btn)

        # 手部追踪
        self.start_btn = QPushButton("启动手部追踪")
        self.start_btn.setFixedHeight(40)
        self.start_btn.setStyleSheet(self._get_button_style("#4CAF50"))
        self.start_btn.clicked.connect(self.start_tracking)
        self._bind_button_feedback(self.start_btn, "#4CAF50")
        left_layout.addWidget(self.start_btn)

        # 颜色检测
        self.color_btn = QPushButton("启动颜色检测")
        self.color_btn.setFixedHeight(40)
        self.color_btn.setStyleSheet(self._get_button_style("#2196F3"))
        self.color_btn.clicked.connect(self.start_color_detection)
        self._bind_button_feedback(self.color_btn, "#2196F3")
        left_layout.addWidget(self.color_btn)

        # 人脸检测
        self.face_btn = QPushButton("启动人脸检测")
        self.face_btn.setFixedHeight(40)
        self.face_btn.setStyleSheet(self._get_button_style("#FF9800"))
        self.face_btn.clicked.connect(self.start_face_detection)
        self._bind_button_feedback(self.face_btn, "#FF9800")
        left_layout.addWidget(self.face_btn)

        # 共用停止按钮
        self.stop_btn = QPushButton("停止当前功能")
        self.stop_btn.setFixedHeight(40)
        self.stop_btn.setStyleSheet(self._get_button_style("#f44336"))
        self.stop_btn.clicked.connect(self.stop_current_function)
        self.stop_btn.setEnabled(False)
        self._bind_button_feedback(self.stop_btn, "#f44336")
        left_layout.addWidget(self.stop_btn)

        # ==================== 树状菜单（形状检测） ====================
        self.detection_tree = QTreeWidget()
        self.detection_tree.setHeaderHidden(True)
        self.detection_tree.setStyleSheet("""
            QTreeWidget {
                font-size: 14px;
                padding: 10px;
            }
            QTreeWidget::item {
                height: 30px;
                padding-left: 5px;
            }
            QTreeWidget::item:hover {
                background-color: #f0f0f0;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
        """)

        # 根节点：形状检测
        shape_item = QTreeWidgetItem(self.detection_tree)
        shape_item.setText(0, "形状检测")
        shape_item.setExpanded(True)

        # 子节点：直线检测
        line_item = QTreeWidgetItem(shape_item)
        line_item.setText(0, "直线检测")

        # 子节点：圆形检测
        circle_item = QTreeWidgetItem(shape_item)
        circle_item.setText(0, "圆形检测")

        # 连接点击信号
        self.detection_tree.itemClicked.connect(self._on_tree_item_clicked)

        left_layout.addWidget(self.detection_tree)
        # ============================================================

        # 状态标签
        self.status_label = QLabel(f"状态：等待启动 | 摄像头 ID: {self.camera_id}")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 10px; color: #333;")
        left_layout.addWidget(self.status_label)

        main_layout.addWidget(left_panel)

        # --- 右侧面板 ---
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: black; border-radius: 5px;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.display_label = QLabel("请启动识别功能")
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        right_layout.addWidget(self.display_label)

        main_layout.addWidget(right_panel, 1)

        # ESC 退出
        self.shortcut_exit = QAction("Exit", self)
        self.shortcut_exit.setShortcut("Esc")
        self.shortcut_exit.triggered.connect(self.close)
        self.addAction(self.shortcut_exit)

        self.showMaximized()

    # ==================== 树状菜单点击处理 ====================
    def _on_tree_item_clicked(self, item, column):
        text = item.text(0)
        parent = item.parent()

        # 根节点点击只切换展开状态
        if parent is None:
            return

        # 子节点点击，启动对应功能
        if text == "直线检测":
            self.start_shape_detection('line')
        elif text == "圆形检测":
            self.start_shape_detection('circle')

    # ==================== 辅助方法：按钮反馈 ====================
    def _get_button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 3px;
            }}
        """

    def _get_pressed_button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {self._darken_color(color)};
                color: white;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 3px;
            }}
        """

    def _darken_color(self, hex_color):
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = max(0, int(r * 0.7))
        g = max(0, int(g * 0.7))
        b = max(0, int(b * 0.7))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _bind_button_feedback(self, button, color):
        button.pressed.connect(lambda: button.setStyleSheet(self._get_pressed_button_style(color)))
        button.released.connect(lambda: button.setStyleSheet(self._get_button_style(color)))

    # ==================== 摄像头设置对话框 ====================
    def open_camera_settings(self):
        if self.running:
            QMessageBox.warning(self, "提示", "请先停止当前运行的功能，再修改摄像头设置")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("摄像头设置")
        dialog.setFixedSize(300, 150)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        label = QLabel("请输入摄像头 ID (数字):")
        layout.addWidget(label)
        entry = QLineEdit()
        entry.setText(self.camera_id)
        layout.addWidget(entry)

        def on_confirm():
            new_id = entry.text().strip()
            if not new_id.isdigit():
                QMessageBox.critical(self, "错误", "请输入有效的数字 ID")
                return
            self.camera_id = new_id
            self.status_label.setText(f"状态：等待启动 | 摄像头 ID: {self.camera_id}")
            dialog.accept()

        btn = QPushButton("确定")
        btn.clicked.connect(on_confirm)
        layout.addWidget(btn)

        dialog.exec()

    # ==================== 通用摄像头工具 ====================
    def _safe_get_cap(self):
        try:
            cam_id = int(self.camera_id)
        except ValueError:
            QMessageBox.critical(self, "错误", "请输入有效的数字摄像头 ID")
            return None, 0, 0

        cap = cv2.VideoCapture(cam_id)
        if not cap.isOpened():
            QMessageBox.critical(self, "错误", f"无法打开摄像头 ID {cam_id}")
            return None, 0, 0

        ret, frame = cap.read()
        if not ret:
            QMessageBox.critical(self, "错误", "摄像头读取失败")
            cap.release()
            return None, 0, 0

        h, w = frame.shape[:2]
        return cap, h, w

    def _update_display(self, frame):
        if frame is None:
            return

        h, w = frame.shape[:2]
        label_w = self.display_label.width()
        label_h = self.display_label.height()
        if label_w <= 1 or label_h <= 1:
            label_w, label_h = 800, 600

        scale = min(label_w / w, label_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(frame, (new_w, new_h))

        rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qimage = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)

        self.display_label.setPixmap(pixmap)
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _cleanup_resources(self):
        self.running = False
        self.mode = None
        self.shape_type = None
        self.timer.stop()

        if self.cap:
            self.cap.release()
            self.cap = None

        self.tracker = None
        self.color_detector = None
        self.face_detector = None

        self.display_label.setPixmap(QPixmap())
        self.display_label.setText("请启动识别功能")
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _update_ui_state(self, mode, running):
        self.start_btn.setEnabled(not running)
        self.color_btn.setEnabled(not running)
        self.face_btn.setEnabled(not running)
        self.cam_preview_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.detection_tree.setEnabled(not running)

        if running:
            cam_id = self.camera_id
            mode_names = {
                'hand': '手部追踪',
                'color': '颜色检测',
                'face': '人脸检测',
                'preview': '摄像头预览',
                'shape': f'{self.shape_type}检测'
            }
            self.status_label.setText(f"状态：{mode_names.get(mode, mode)}运行中 (摄像头 ID {cam_id})")
        else:
            self.status_label.setText(f"状态：已停止 | 摄像头 ID: {self.camera_id}")

    # ==================== 手部追踪 ====================
    def start_tracking(self):
        if self.running: return
        cap, h, w = self._safe_get_cap()
        if cap is None: return
        self.cap = cap
        self.tracker = hand_tracking_particles.HandTrackingParticles(width=w, height=h)
        self.running = True
        self.mode = 'hand'
        self._update_ui_state('hand', True)
        self.timer.start()

    # ==================== 颜色检测 ====================
    def start_color_detection(self):
        if self.running: return
        cap, h, w = self._safe_get_cap()
        if cap is None: return
        self.cap = cap
        GREEN_LOWER = np.array([35, 43, 46])
        GREEN_UPPER = np.array([85, 255, 255])
        self.color_detector = Color_Detector.ColorDetector(GREEN_LOWER, GREEN_UPPER, min_area=500)
        self.running = True
        self.mode = 'color'
        self._update_ui_state('color', True)
        self.timer.start()

    # ==================== 人脸检测 ====================
    def start_face_detection(self):
        if self.running: return
        cap, h, w = self._safe_get_cap()
        if cap is None: return
        self.cap = cap
        try:
            self.face_detector = Face_Detector.FaceDetector()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"初始化人脸检测器失败: {e}")
            cap.release()
            return
        self.running = True
        self.mode = 'face'
        self._update_ui_state('face', True)
        self.timer.start()

    # ==================== 摄像头预览 ====================
    def start_camera_preview(self):
        if self.running: return
        cap, h, w = self._safe_get_cap()
        if cap is None: return
        self.cap = cap
        self.running = True
        self.mode = 'preview'
        self._update_ui_state('preview', True)
        self.timer.start()

    # ==================== 形状检测（新增） ====================
    def start_shape_detection(self, shape_type):
        if self.running:
            QMessageBox.warning(self, "提示", "请先停止当前运行的功能，再启动形状检测")
            return
        cap, h, w = self._safe_get_cap()
        if cap is None: return
        self.cap = cap
        self.shape_type = shape_type
        self.running = True
        self.mode = 'shape'
        self._update_ui_state('shape', True)
        self.timer.start()

    # ==================== 共用帧处理 ====================
    def process_frame(self):
        if not self.running: return

        ret, frame = self.cap.read()
        if not ret:
            self.stop_current_function()
            QMessageBox.critical(self, "错误", "摄像头帧读取失败，自动停止")
            return

        display_frame = frame.copy()

        if self.mode == 'hand':
            display_frame = self.tracker.process_frame(frame)
        elif self.mode == 'color':
            _, _, display_frame = self.color_detector.detect(frame)
        elif self.mode == 'face':
            faces = self.face_detector.detect(frame)
            for (x, y, w, h) in faces:
                cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
        elif self.mode == 'shape':
            if self.shape_type == 'line':
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                edges = cv2.Canny(gray, 50, 150, apertureSize=3)
                lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
                if lines is not None:
                    for line in lines:
                        x1, y1, x2, y2 = line[0]
                        cv2.line(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            elif self.shape_type == 'circle':
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.medianBlur(gray, 5)
                circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=200, param1=120, param2=80, minRadius=10, maxRadius=0)
                if circles is not None:
                    circles = np.uint16(np.around(circles))
                    for i in circles[0, :]:
                        center = (i[0], i[1])
                        radius = i[2]
                        cv2.circle(display_frame, center, radius, (0, 255, 0), 2)
                        cv2.circle(display_frame, center, 2, (0, 0, 255), 3)

        self._update_display(display_frame)

    # ==================== 共用停止方法 ====================
    def stop_current_function(self):
        if not self.running: return
        self._cleanup_resources()
        self._update_ui_state(self.mode or 'none', False)

    # ==================== 窗口关闭 ====================
    def closeEvent(self, event):
        self._cleanup_resources()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VisualSystem()
    window.show()
    sys.exit(app.exec())