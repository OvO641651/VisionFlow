import sys
import cv2
import numpy as np
from PySide2.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                               QComboBox, QSpinBox, QPushButton, QRadioButton,
                               QWidget, QSlider, QLabel, QCheckBox,
                               QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QMessageBox)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QBrush  # 【修改】增加了 QBrush 用于填充圆心点
from PySide2.QtCore import Qt, QRectF


# ===== 用于在弹窗中显示图片并绘制框选的画布 =====
class ROISelectGraphicsView(QGraphicsView):
    def __init__(self, pixmap, shape_type="矩形", parent=None):
        """
        :param pixmap: 图像数据载体
        :param shape_type: 框选的形状 (矩形 或 圆)
        :param parent: 父对象
        """
        super().__init__(parent)
        self.shape_type = shape_type
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # 将图片添加到场景中
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())

        # 开启抗锯齿和更新优化
        self.setRenderHints(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.NoDrag)

        self.start_point = None  # 鼠标按下点
        self.center_point = None  # 圆形的圆心
        self.rect_item = None  # 记录矩形对象
        self.ellipse_item = None  # 记录圆形对象
        self.center_dot_item = None  # 【新增】记录圆心点对象
        self.final_rect = None  # 矩形最终位置
        self.final_ellipse = None  # 圆形最终数据 (cx, cy, r)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.start_point = self.mapToScene(event.pos())

            # 如果是画圆，记录圆心
            if self.shape_type == "圆":
                self.center_point = self.start_point

                # 【新增】绘制并显示圆心点（绿色小实心圆）
                if self.center_dot_item:
                    self.scene.removeItem(self.center_dot_item)
                self.center_dot_item = QGraphicsEllipseItem(self.center_point.x() - 3, self.center_point.y() - 3, 6, 6)
                self.center_dot_item.setBrush(QBrush(QColor(0, 255, 0)))  # 填充绿色
                self.scene.addItem(self.center_dot_item)

            # 清除画布上已有的图形
            if self.shape_type == "矩形" and self.rect_item:
                self.scene.removeItem(self.rect_item)
                self.rect_item = None
            elif self.shape_type == "圆" and self.ellipse_item:
                self.scene.removeItem(self.ellipse_item)
                self.ellipse_item = None

    def mouseMoveEvent(self, event):
        """鼠标拖动事件"""
        if self.start_point and event.buttons() == Qt.LeftButton:
            current_point = self.mapToScene(event.pos())

            if self.shape_type == "矩形":
                x = min(self.start_point.x(), current_point.x())
                y = min(self.start_point.y(), current_point.y())
                w = abs(self.start_point.x() - current_point.x())
                h = abs(self.start_point.y() - current_point.y())

                if self.rect_item is None:
                    self.rect_item = QGraphicsRectItem(x, y, w, h)
                    self.rect_item.setPen(QPen(QColor(0, 255, 0), 2, Qt.SolidLine))
                    self.scene.addItem(self.rect_item)
                else:
                    self.rect_item.setRect(x, y, w, h)

            elif self.shape_type == "圆":
                # 计算半径：鼠标当前位置 到 圆心的距离
                cx = self.center_point.x()
                cy = self.center_point.y()
                dx = current_point.x() - cx
                dy = current_point.y() - cy
                r = np.sqrt(dx * dx + dy * dy)

                # 【新增】保持圆心点固定不动
                if self.center_dot_item:
                    self.center_dot_item.setRect(cx - 3, cy - 3, 6, 6)

                if self.ellipse_item is None:
                    self.ellipse_item = QGraphicsEllipseItem(cx - r, cy - r, 2 * r, 2 * r)
                    self.ellipse_item.setPen(QPen(QColor(0, 255, 0), 2, Qt.SolidLine))
                    self.scene.addItem(self.ellipse_item)
                else:
                    self.ellipse_item.setRect(cx - r, cy - r, 2 * r, 2 * r)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.start_point:
            current_point = self.mapToScene(event.pos())

            if self.shape_type == "矩形":
                self.final_rect = QRectF(self.start_point, current_point).normalized()
            elif self.shape_type == "圆":
                cx = self.center_point.x()
                cy = self.center_point.y()
                dx = current_point.x() - cx
                dy = current_point.y() - cy
                r = np.sqrt(dx * dx + dy * dy)
                self.final_ellipse = (cx, cy, r)

            self.start_point = None  # 结束本次框选

    def get_roi(self):
        """获取框选的坐标 (x, y, w, h)"""
        if self.shape_type == "矩形":
            if hasattr(self, 'final_rect') and self.final_rect:
                return (int(self.final_rect.x()), int(self.final_rect.y()),
                        int(self.final_rect.width()), int(self.final_rect.height()))
        elif self.shape_type == "圆":
            if hasattr(self, 'final_ellipse') and self.final_ellipse:
                cx, cy, r = self.final_ellipse
                return (int(cx), int(cy), int(r), 0)  # 返回圆心xy和半径，h暂时返回0
        return 0, 0, 0, 0


# ===== 创建框选 ROI 的独立对话框 =====
class ROISelectDialog(QDialog):
    def __init__(self, img_bgr, parent=None, shape_type="矩形"):
        """
        :param img_bgr: OpenCV 读取的 BGR 格式图像数据
        :param parent: 父窗口控件
        :param shape_type: 选择框选的形状
        """
        super().__init__(parent)
        self.setWindowTitle("ROI 框选工具")
        self.setModal(True)

        # 将 OpenCV 的 BGR 图片转换为 Qt 的 QPixmap
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.pixmap = QPixmap.fromImage(q_img)

        # 主布局
        layout = QVBoxLayout(self)

        # 实例化专门用于显示和交互的画布，并把形状类型传进去
        self.view = ROISelectGraphicsView(self.pixmap, shape_type=shape_type)
        self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)
        layout.addWidget(self.view)

        # 底部按钮区
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        self.resize(min(800, w + 30), min(600, h + 60))

    def get_roi(self):
        """获取画布上框选的坐标"""
        return self.view.get_roi()


# ===== 主配置窗口类 =====
class LineParamsDialog(QDialog):
    def __init__(self, parent=None, node=None, main_window=None):
        """
        :param parent:标准父类窗口参数，父类窗口关闭时，该窗口也关闭
        :param node:传入流程图中双击的方框对象，用于修改ui中的XY等值
        :param main_window:传入主窗口示例
        """
        super().__init__(parent)
        self.node = node
        self.main_window = main_window

        # 加载 UI 文件
        loader = QUiLoader()
        self.ui = loader.load('LineParamsDialog.ui')

        # 将加载的 UI 嵌入到当前 Dialog 的垂直布局中
        layout = QVBoxLayout(self)
        layout.addWidget(self.ui)
        layout.setContentsMargins(0, 0, 0, 0)

        # 通过findChild函数来获取 UI 内部的控件引用
        self.input_source = self.ui.findChild(QComboBox, "input_source")
        self.input_source.addItem("0 图像源1.图像")

        self.roi_draw = self.ui.findChild(QRadioButton, "roi_draw")
        self.roi_inherit = self.ui.findChild(QRadioButton, "roi_inherit")

        self.spin_roi_x = self.ui.findChild(QSpinBox, "spin_roi_x")
        self.spin_roi_y = self.ui.findChild(QSpinBox, "spin_roi_y")
        self.spin_roi_w = self.ui.findChild(QSpinBox, "spin_roi_w")
        self.spin_roi_h = self.ui.findChild(QSpinBox, "spin_roi_h")

        self.btn_roi_toggle = self.ui.findChild(QPushButton, "btn_roi_toggle")
        self.roi_params_widget = self.ui.findChild(QWidget, "roi_params_widget")

        self.pos_correction_slider = self.ui.findChild(QSlider, "pos_correction_slider")
        self.pos_correction_slider.setValue(0)

        self.shape_combo = self.ui.findChild(QComboBox, "comboBox")
        self.label_w = self.ui.findChild(QLabel, "label_w")
        self.label_h = self.ui.findChild(QLabel, "label_h")

        self.btn_cont = self.ui.findChild(QPushButton, "btn_cont")
        self.btn_run = self.ui.findChild(QPushButton, "btn_run")
        self.btn_ok = self.ui.findChild(QPushButton, "btn_ok")

        self.cb_hide_roi = self.ui.findChild(QCheckBox, "cb_hide_roi")

        self.btn_select = self.ui.findChild(QPushButton, "pushButton")
        if self.btn_select:
            self.btn_select.clicked.connect(self.on_select_click)

        # 界面初始化与事件绑定
        self.roi_params_widget.setVisible(True)
        self.btn_roi_toggle.setText("ROI参数 ▲")
        self.btn_roi_toggle.clicked.connect(self.toggle_roi_params)

        self.roi_draw.toggled.connect(self._update_roi_params_visibility)
        self.roi_inherit.toggled.connect(self._update_roi_params_visibility)
        self.shape_combo.currentTextChanged.connect(self._update_shape_layout)

        # 绑定底部按钮
        if self.btn_run:
            self.btn_run.clicked.connect(self.on_step_click)
        if self.btn_ok:
            self.btn_ok.clicked.connect(self.on_ok)
        if self.btn_cont:
            self.btn_cont.clicked.connect(self.on_cont_click)

        # 加载节点已有的参数
        self.roi_draw.setChecked(True)
        self._load_params()
        self._update_shape_layout(self.shape_combo.currentText())

    def _load_params(self):
        """从 node.params 加载参数到 UI 控件"""
        if self.node:
            params = self.node.params
            self.spin_roi_x.setValue(params.get("roi_x", 0))
            self.spin_roi_y.setValue(params.get("roi_y", 0))

            default_w = 640
            default_h = 480
            if self.main_window:
                if self.main_window.current_static_image is not None:
                    h, w = self.main_window.current_static_image.shape[:2]
                    default_w, default_h = w, h
                elif self.main_window.cap is not None and self.main_window.cap.isOpened():
                    stream_w = self.main_window.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    stream_h = self.main_window.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    if stream_w > 0 and stream_h > 0:
                        default_w, default_h = int(stream_w), int(stream_h)

            if self.cb_hide_roi:
                self.cb_hide_roi.setChecked(params.get("hide_roi", False))

            self.spin_roi_w.setValue(params.get("roi_w", default_w))
            self.spin_roi_h.setValue(params.get("roi_h", default_h))



    def _update_params(self):
        """从 UI 控件保存参数到 node.params"""
        if self.node:
            roi_shape = self.shape_combo.currentText()

            # 无论形状如何，先保存基本的 X, Y, W, H (H 对于圆形来说也是直径)
            self.node.params["roi_x"] = self.spin_roi_x.value()
            self.node.params["roi_y"] = self.spin_roi_y.value()
            self.node.params["roi_w"] = self.spin_roi_w.value()
            self.node.params["roi_h"] = self.spin_roi_h.value()
            self.node.params["roi_shape"] = roi_shape

            # 如果是圆形，额外保存精准的圆心和半径
            if roi_shape == "圆":
                self.node.params["roi_cx"] = self.spin_roi_x.value()
                self.node.params["roi_cy"] = self.spin_roi_y.value()
                self.node.params["roi_r"] = self.spin_roi_w.value()

            if self.cb_hide_roi:
                self.node.params["hide_roi"] = self.cb_hide_roi.isChecked()




    def on_step_click(self):
        """点击'执行'按钮时触发：单步执行（只执行当前节点）"""
        self._update_params()
        if self.main_window:
            if self.main_window.current_static_image is not None:
                work_frame = self.main_window.current_static_image.copy()
                work_frame, _ = self.main_window._run_flow_pipeline_step(work_frame, self.node)
                self.main_window._display_image(work_frame)
            elif self.main_window.cap is not None:
                self.main_window.video_processing_mode = "step"
                self.main_window.video_step_node = self.node
                self.main_window.update_frame()

    def on_cont_click(self):
        """点击'连续执行'按钮时触发：按完整的流程图顺序执行"""
        self._update_params()
        if self.main_window:
            if self.main_window.current_static_image is not None:
                self.main_window._process_and_display_frame(self.main_window.current_static_image)
            elif self.main_window.cap is not None:
                self.main_window.video_processing_mode = "continuous"
                self.main_window.video_step_node = None
                self.main_window.update_frame()

    def on_ok(self):
        """点击确定：执行一次单步检测并关闭配置窗口"""
        self.on_step_click()
        self.accept()

    def toggle_roi_params(self):
        current_visible = self.roi_params_widget.isVisible()
        self.roi_params_widget.setVisible(not current_visible)
        if not current_visible:
            self.btn_roi_toggle.setText("ROI参数 ▲")
        else:
            self.btn_roi_toggle.setText("ROI参数 ▼")

    def _update_roi_params_visibility(self):
        if self.roi_draw.isChecked():
            self.btn_roi_toggle.setVisible(True)
            if not self.roi_params_widget.isVisible():
                self.roi_params_widget.setVisible(True)
                self.btn_roi_toggle.setText("ROI参数 ▲")
        else:
            self.roi_params_widget.setVisible(False)
            self.btn_roi_toggle.setVisible(False)

    def _update_shape_layout(self, shape_text):
        """根据形状下拉框当前选中的文字，动态更新参数框的标签名和可见性"""
        if shape_text == "圆":
            self.label_w.setText("R:")
            self.label_h.setVisible(False)
            self.spin_roi_h.setVisible(False)
        else:
            self.label_w.setText("W:")
            self.label_h.setVisible(True)
            self.spin_roi_h.setVisible(True)

    def refresh_size(self):
        if self.main_window:
            if self.main_window.current_static_image is not None:
                h, w = self.main_window.current_static_image.shape[:2]
                self.spin_roi_w.setValue(w)
                self.spin_roi_h.setValue(h)
            elif self.main_window.cap is not None and self.main_window.cap.isOpened():
                stream_w = self.main_window.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                stream_h = self.main_window.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                if stream_w > 0 and stream_h > 0:
                    self.spin_roi_w.setValue(int(stream_w))
                    self.spin_roi_h.setValue(int(stream_h))

    # "框选"按钮触发的功能
    def on_select_click(self):
        """点击框选按钮：根据形状类型调出框选窗口，回填坐标"""
        img_bgr = None
        timer_paused = False

        # 获取当前选中的形状类型
        shape_text = self.shape_combo.currentText()

        if self.main_window is not None and self.main_window.current_static_image is not None:
            img_bgr = self.main_window.current_static_image
        elif self.main_window is not None and self.main_window.cap is not None and self.main_window.cap.isOpened():
            timer = self.main_window.timer
            if timer is not None and timer.isActive():
                timer.stop()
                timer_paused = True
            ret, frame = self.main_window.cap.read()
            if ret:
                img_bgr = frame
            else:
                if timer_paused:
                    timer.start(30)
                QMessageBox.warning(self, "提示", "视频/摄像头读取失败，无法获取当前画面！")
                return
            if timer_paused:
                timer.start(30)

        if img_bgr is None:
            QMessageBox.warning(self, "提示", "请先导入图片或打开摄像头/视频！")
            return

        # 将当前形状类型(shape_text)传给框选工具
        select_dialog = ROISelectDialog(img_bgr, self, shape_text)

        if select_dialog.exec_() == QDialog.Accepted:
            x, y, w, h = select_dialog.get_roi()
            self.spin_roi_x.setValue(x)
            self.spin_roi_y.setValue(y)

            # 根据形状类型，正确回填 R (W) 和 H
            if shape_text == "矩形":
                self.spin_roi_x.setValue(x)
                self.spin_roi_y.setValue(y)
                self.spin_roi_w.setValue(w)
                self.spin_roi_h.setValue(h)
            elif shape_text == "圆":
                # 【修复】：将框选得到的圆心(x,y)和半径r，转换为外接正方形的左上角和边长
                cx, cy, r = x, y, w
                self.spin_roi_x.setValue(int(cx - r))  # 左上角 X
                self.spin_roi_y.setValue(int(cy - r))  # 左上角 Y
                self.spin_roi_w.setValue(int(2 * r))  # 边长 = 直径 (由 "R:" 充当)
                self.spin_roi_h.setValue(int(2 * r))  # 高度 = 直径


if __name__ == '__main__':
    app = QApplication(sys.argv)
    test_img_path = 'image/lena.png'
    test_img = cv2.imread(test_img_path)
    if test_img is None:
        print(f"找不到图片，请检查路径: {test_img_path}")
        test_img = np.zeros((512, 512, 3), dtype=np.uint8)


    class MockMainWindow:
        def __init__(self, img):
            self.current_static_image = img
            self.cap = None
            self.video_processing_mode = "continuous"
            self.video_step_node = None

        @staticmethod
        def _process_and_display_frame(frame):
            print(f"[Mock主窗口] 执行连续执行，尺寸: {frame.shape}")

        @staticmethod
        def update_frame():
            print("[Mock主窗口] 执行视频帧更新")

        @staticmethod
        def _display_image(img):
            print(f"[Mock主窗口] 显示图片，尺寸: {img.shape}")

        @staticmethod
        def _run_flow_pipeline_step(frame, node):
            print(f"[Mock主窗口] 执行单步检测，节点名: {node.name}")
            return frame, []

        @staticmethod
        def _run_flow_pipeline(frame):
            print("[Mock主窗口] 执行完整流程图检测")
            return frame, []


    mock_main_window = MockMainWindow(test_img)


    class MockNode:
        def __init__(self):
            self.params = {}
            self.name = "模拟检测节点"


    mock_node = MockNode()

    dialog = LineParamsDialog(parent=None, node=mock_node, main_window=mock_main_window)
    dialog.setWindowTitle("直线查找 - 框选测试窗口")
    dialog.resize(390, 560)
    dialog.show()
    sys.exit(app.exec_())