import sys
import cv2
import numpy as np
from PySide2.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                               QComboBox, QSpinBox, QPushButton, QRadioButton,
                               QWidget, QSlider, QLabel, QCheckBox,
                               QGraphicsView, QGraphicsScene, QGraphicsRectItem, QMessageBox)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PySide2.QtCore import Qt, QRectF

# ===== 用于在弹窗中显示图片并绘制框选的画布 =====
class ROISelectGraphicsView(QGraphicsView):
    def __init__(self, pixmap, parent=None):
        """
        :param pixmap: 图像数据载体，QPixmap 类的一个实例，用来在屏幕上显示和处理图像
        :param parent: 父对象
        """
        super().__init__(parent)
        self.scene = QGraphicsScene(self) # 作为背景存放画面
        self.setScene(self.scene)

        # 将图片添加到场景中
        self.pixmap_item = self.scene.addPixmap(pixmap)
        # 设置场景大小和图片完全一致
        self.setSceneRect(0, 0, pixmap.width(), pixmap.height())

        # 开启抗锯齿和更新优化，作用是确保画布的交互体验丝滑、图像清晰，并且与后续的鼠标框选逻辑不产生冲突。
        self.setRenderHints(QPainter.Antialiasing) # 开启抗锯齿，使画出的矩形框的边光滑
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate) # 将视口的更新模式设置为"全视口更新"
        self.setDragMode(QGraphicsView.NoDrag) # 禁用拖拽模式

        self.start_point = None # 记录鼠标开始的起始点
        self.rect_item = None # 记录矩形对象
        self.final_rect = None # 矩形最终的位置


    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 判断是否为左键按下
            self.start_point = self.mapToScene(event.pos())# mapToScene 会自动计算因为图片缩放产生的坐标差异，拿到绝对像素坐标
            if self.rect_item:
                # 如果有矩形对象已经存在
                self.scene.removeItem(self.rect_item) # 去除已有的矩形对象
                self.rect_item = None # 重置矩形对象的记录

    def mouseMoveEvent(self, event):
        """鼠标拖动事件"""
        if self.start_point and event.buttons() == Qt.LeftButton:
            # 判断已经按下了鼠标左键，且当前依然按着左键拖拽时，才执行
            current_point = self.mapToScene(event.pos())
            # # 计算矩形的左上角和宽高
            x = min(self.start_point.x(), current_point.x()) # 开始和末尾的最小值(预防反向拖拽的情况)
            y = min(self.start_point.y(), current_point.y())
            w = abs(self.start_point.x() - current_point.x()) #绝对值(反向时也可以获取长度)
            h = abs(self.start_point.y() - current_point.y())

            if self.rect_item is None:
                # 画笔上原来没有矩形框
                self.rect_item = QGraphicsRectItem(x, y, w, h) # 创建一个新的矩形图元对象
                self.rect_item.setPen(QPen(QColor(0, 255, 0), 2, Qt.SolidLine)) # 设置矩形的画笔样式：绿色、线宽2、实线
                self.scene.addItem(self.rect_item) # 将绿框添加到场景画布中
            else:
                # 矩形框已经存在
                self.rect_item.setRect(x, y, w, h) # 直接更新它的坐标和宽高

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton and self.start_point:
            # 只有当松开的键是左键，且之前有记录过起点坐标时，才执行收尾动作
            # 记录松开鼠标时，鼠标位置的原始真实像素坐标（作为终点）
            current_point = self.mapToScene(event.pos())
            # 根据起点和终点生成一个矩形，并调用 .normalized() 进行规范化
            self.final_rect = QRectF(self.start_point, current_point).normalized()
            # 将起点坐标重置为 None，彻底结束这一次的框选动作
            self.start_point = None

    def get_roi(self):
        """获取框选的坐标 (x, y, w, h)"""
        if hasattr(self, 'final_rect') and self.final_rect:
            return (int(self.final_rect.x()), int(self.final_rect.y()),
                    int(self.final_rect.width()), int(self.final_rect.height()))
        return 0, 0, 0, 0


# ===== 创建框选 ROI 的独立对话框 =====
class ROISelectDialog(QDialog):
    def __init__(self, img_bgr, parent=None):
        """
        :param img_bgr: OpenCV 读取的 BGR 格式图像数据
        :param parent: 父窗口控件
        """
        super().__init__(parent)
        self.setWindowTitle("ROI 框选工具") # ROI窗口名字
        self.setModal(True) # Modal模态窗口

        # 将 OpenCV 的 BGR 图片转换为 Qt 的 QPixmap，参考main.py的_process_and_display_frame()函数
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888) # type:ignore
        self.pixmap = QPixmap.fromImage(q_img)

        # 主布局
        layout = QVBoxLayout(self)

        # 实例化专门用于显示和交互的画布
        self.view = ROISelectGraphicsView(self.pixmap)
        # 自动缩放图片以完整适应视图大小，同时保持宽高比，彻底消除滚动条
        self.view.fitInView(self.view.sceneRect(), Qt.KeepAspectRatio)
        # 把缩放好的画布加入到窗口的布局中
        layout.addWidget(self.view)

        # 底部按钮区
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("确定")
        self.btn_cancel = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # 点击(槽)事件
        self.btn_ok.clicked.connect(self.accept) # type:ignore
        self.btn_cancel.clicked.connect(self.reject) # type:ignore

        # 调整窗口自适应图片大小，并设置最大限制以防超出显示器
        self.resize(min(800, w + 30), min(600, h + 60))

    def get_roi(self):
        """获取画布上框选的坐标 (x, y, w, h)"""
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
        layout.setContentsMargins(0, 0, 0, 0) # 去除布局的四周内边距

        # 通过findChild函数来获取 UI 内部的控件引用，即获取各控件的名字 Name
        # 获取下拉框
        self.input_source = self.ui.findChild(QComboBox, "input_source")
        self.input_source.addItem("0 图像源1.图像") # 设置下拉框的第一条内容

        # 获取 "绘制" 和 "继承" 两个单选框
        self.roi_draw = self.ui.findChild(QRadioButton, "roi_draw")
        self.roi_inherit = self.ui.findChild(QRadioButton, "roi_inherit")

        # 获取 ROI 区域的四个计数框
        self.spin_roi_x = self.ui.findChild(QSpinBox, "spin_roi_x")
        self.spin_roi_y = self.ui.findChild(QSpinBox, "spin_roi_y")
        self.spin_roi_w = self.ui.findChild(QSpinBox, "spin_roi_w")
        self.spin_roi_h = self.ui.findChild(QSpinBox, "spin_roi_h")

        # 获取 "ROI参数" 这个按钮，用来实现下面 XYWH 的显示与隐藏
        self.btn_roi_toggle = self.ui.findChild(QPushButton, "btn_roi_toggle")
        self.roi_params_widget = self.ui.findChild(QWidget, "roi_params_widget")

        # 获取滑动条（即位置修正右边的左右移动条）
        self.pos_correction_slider = self.ui.findChild(QSlider, "pos_correction_slider")
        self.pos_correction_slider.setValue(0) # 设置默认状态的代码 (0 代表关闭,左滑)

        # 获取形状右边的下拉框(选择矩阵或者圆) 和  WH 的文本内容(label)
        self.shape_combo = self.ui.findChild(QComboBox, "comboBox")
        self.label_w = self.ui.findChild(QLabel, "label_w")
        self.label_h = self.ui.findChild(QLabel, "label_h")

        # 从 UI 文件中获取底部的 3 个按钮
        self.btn_cont = self.ui.findChild(QPushButton, "btn_cont")
        self.btn_run = self.ui.findChild(QPushButton, "btn_run")
        self.btn_ok = self.ui.findChild(QPushButton, "btn_ok")

        # 获取隐藏 "ROI参数" 绘制的黄色框的复选框
        self.cb_hide_roi = self.ui.findChild(QCheckBox, "cb_hide_roi")

        # 获取框选按钮
        self.btn_select = self.ui.findChild(QPushButton, "pushButton")
        if self.btn_select:
            self.btn_select.clicked.connect(self.on_select_click)

        # 界面初始化与事件绑定
        self.roi_params_widget.setVisible(True) # 控件是否可见，用于选择继承时隐藏 XYWH 部分
        self.btn_roi_toggle.setText("ROI参数 ▲") # 设置 "ROI参数" 这个按钮的箭头形式
        self.btn_roi_toggle.clicked.connect(self.toggle_roi_params) # 通过点击来控制 "ROI参数"这个按钮的箭头形式

        # 绘制和继承两种形式时 "ROI参数" 这个按钮的显示控制，绘制时显示，继承时隐藏
        self.roi_draw.toggled.connect(self._update_roi_params_visibility)
        self.roi_inherit.toggled.connect(self._update_roi_params_visibility)
        # 控制四个计数框，如果形状选择矩形时，为 XYWH;如果选择圆时，为 XYR，第四个参数隐藏
        self.shape_combo.currentTextChanged.connect(self._update_shape_layout)


        # 绑定 UI 中的三个按钮事件，使用if谱段这三个按钮是否存在
        if self.btn_run:
            self.btn_run.clicked.connect(self.on_run)
        if self.btn_ok:
            self.btn_ok.clicked.connect(self.on_ok)
        if self.btn_cont:
            self.btn_cont.clicked.connect(self.on_run)  # 暂定连续执行等同于单次执行

        # 加载节点已有的参数
        self.roi_draw.setChecked(True) # "ROI创建"滑动条 默认为 "绘制" 打开
        self._load_params() # 设置 XYWH 的默认值
        self._update_shape_layout(self.shape_combo.currentText()) # 强制执行一次 UI 布局对齐


    def _load_params(self):
        """从 node.params 加载参数到 UI 控件，并使用当前图像尺寸作为默认值"""
        if self.node:
            params = self.node.params
            # 设置 XY 的默认值为 0
            self.spin_roi_x.setValue(params.get("roi_x", 0))
            self.spin_roi_y.setValue(params.get("roi_y", 0))

            # 设定没有图片或者视频时的 WH 默认值
            default_w = 640
            default_h = 480

            # 尝试获取当前主窗口加载的图像或视频尺寸
            if self.main_window:
                # 当前打开的是静态图片，current_static_image = True 表示当前静态图片存在
                if self.main_window.current_static_image is not None:
                    h, w = self.main_window.current_static_image.shape[:2]
                    default_w, default_h = w, h

                # 当前打开的是摄像头或视频流
                elif self.main_window.cap is not None and self.main_window.cap.isOpened():
                    # 获取视频流的真实宽高
                    stream_w = self.main_window.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    stream_h = self.main_window.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    # 只有正确读到了宽高才覆盖默认值
                    if stream_w > 0 and stream_h > 0:
                        default_w, default_h = int(stream_w), int(stream_h)

            # 加载复选框状态 (如果节点没保存过，默认设为 False 即显示黄框)
            if self.cb_hide_roi:
                self.cb_hide_roi.setChecked(params.get("hide_roi", False))

            # 将默认值写入 UI (如果 node.params 里没有存过数据，就会使用计算出的 default_w/h)
            self.spin_roi_w.setValue(params.get("roi_w", default_w))
            self.spin_roi_h.setValue(params.get("roi_h", default_h))


    def _update_params(self):
        """从 UI 控件保存参数到 node.params"""
        if self.node:
            # 将 XYWH 进度条的数值写到 params 里面
            self.node.params["roi_x"] = self.spin_roi_x.value()
            self.node.params["roi_y"] = self.spin_roi_y.value()
            self.node.params["roi_w"] = self.spin_roi_w.value()
            self.node.params["roi_h"] = self.spin_roi_h.value()

            # 将复选框状态写入节点参数
            if self.cb_hide_roi:
                self.node.params["hide_roi"] = self.cb_hide_roi.isChecked()


    def on_run(self):
        """点击执行：保存参数 -> 重新处理图像"""
        self._update_params() # 保存参数，自动更新参数
        # 触发主窗口重新渲染画面
        if self.main_window:
            # 静态图像时
            if self.main_window.current_static_image is not None:
                # 按流程图或树状图模式处理一帧图像，并渲染到 videoLabel
                self.main_window._process_and_display_frame(self.main_window.current_static_image) # noqa
            # 摄像头或者视频时
            elif self.main_window.cap is not None:
                self.main_window.update_frame() # 自动更新图像画面

    def on_ok(self):
        """点击确定：执行一次并关闭窗口"""
        self.on_run() # 执行 on_run() 函数
        self.accept() # 关闭对话款(窗口)

    def toggle_roi_params(self):
        """点击"ROI参数"这个按钮后触发，切换 "ROI参数" 区域的展开与折叠状态，并同步修改按钮图标"""
        # 获取当前参数区域 XYWH 是否处于可见状态，True表示可见，False表示不可见
        current_visible = self.roi_params_widget.isVisible()
        # 取反，可见变隐藏，隐藏变可见
        self.roi_params_widget.setVisible(not current_visible)
        # 根据点击前的状态同步更新按钮上的箭头方向
        if not current_visible:
            self.btn_roi_toggle.setText("ROI参数 ▲")
        else:
            self.btn_roi_toggle.setText("ROI参数 ▼")

    def _update_roi_params_visibility(self):
        """根据“ROI创建”的单选框状态(选择绘制 或者 继承)，控制展开按钮及参数区域的显示与隐藏"""
        # 选择的是 绘制roi_draw 时
        if self.roi_draw.isChecked():
            # 将"ROI参数"按钮展示出来
            self.btn_roi_toggle.setVisible(True)
            if not self.roi_params_widget.isVisible():
                # 把 XYWH 展示出来
                self.roi_params_widget.setVisible(True)
                # 改变 "ROI参数"的图标
                self.btn_roi_toggle.setText("ROI参数 ▲")
        else:
            # 选中的是 继承roi_params_widget 时，隐藏下面的内容
            self.roi_params_widget.setVisible(False)
            self.btn_roi_toggle.setVisible(False)

    def _update_shape_layout(self, shape_text):
        """根据形状下拉框当前选中的文字，动态更新参数框的标签名和可见性"""
        if shape_text == "圆":
            # 选中的是"圆"时，label_w的文本为 "R"，label_h这一行隐藏
            self.label_w.setText("R:")
            self.label_h.setVisible(False)
            self.spin_roi_h.setVisible(False)
        else:
            # 选择的是其他时(矩阵，绘制矩形)，正常按照ui展示
            self.label_w.setText("W:")
            self.label_h.setVisible(True)
            self.spin_roi_h.setVisible(True)

    def refresh_size(self):
        """允许外部主窗口在加载图片后，手动触发对话框重新计算尺寸"""
        if self.main_window:
            # 如果当前是静态图片
            if self.main_window.current_static_image is not None:
                h, w = self.main_window.current_static_image.shape[:2]
                # 直接强制赋值，避免被 node.params 里可能存在的旧值覆盖
                self.spin_roi_w.setValue(w)
                self.spin_roi_h.setValue(h)

            # 如果当前是摄像头或视频流
            elif self.main_window.cap is not None and self.main_window.cap.isOpened():
                stream_w = self.main_window.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                stream_h = self.main_window.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                if stream_w > 0 and stream_h > 0:
                    self.spin_roi_w.setValue(int(stream_w))
                    self.spin_roi_h.setValue(int(stream_h))

    # "框选"按钮触发的功能
    def on_select_click(self):
        """点击框选按钮：检查图片或视频/摄像头帧，调出框选窗口，回填坐标"""
        img_bgr = None
        timer_paused = False

        # 1. 情况A：优先取主窗口的静态图片
        if self.main_window is not None and self.main_window.current_static_image is not None:
            img_bgr = self.main_window.current_static_image

        # 2. 情况B：没有静态图片，但有开启的摄像头/视频流
        elif self.main_window is not None and self.main_window.cap is not None and self.main_window.cap.isOpened():
            # 为了框选画面时画面不跳动，先暂定主窗口的视频刷新定时器
            timer = self.main_window.timer
            if timer is not None and timer.isActive():
                timer.stop()
                timer_paused = True

            # 捕获当前最新的一帧
            ret, frame = self.main_window.cap.read()
            if ret:
                img_bgr = frame
            else:
                # 如果读取失败，需要恢复定时器并给出提示
                if timer_paused:
                    timer.start(30)
                QMessageBox.warning(self, "提示", "视频/摄像头读取失败，无法获取当前画面！")
                return

            # 抓取完成，立刻恢复主窗口的视频刷新
            if timer_paused:
                timer.start(30)

        # 3. 情况C：什么都没有
        if img_bgr is None:
            QMessageBox.warning(self, "提示", "请先导入图片或打开摄像头/视频！")
            return

        # 4. 弹出框选窗口，将图片/视频帧传进去
        select_dialog = ROISelectDialog(img_bgr, self)

        # 5. 如果用户点击了“确定”，获取坐标并填入输入框
        if select_dialog.exec_() == QDialog.Accepted:
            x, y, w, h = select_dialog.get_roi()
            self.spin_roi_x.setValue(x)
            self.spin_roi_y.setValue(y)
            self.spin_roi_w.setValue(w)
            self.spin_roi_h.setValue(h)


if __name__ == '__main__':
    # 创建 Qt 应用
    app = QApplication(sys.argv)

    # 读取测试图片
    test_img_path  = 'image/lena.png'
    test_img  = cv2.imread(test_img_path )
    if test_img  is None:
        print(f"找不到图片，请检查路径: {test_img_path }")
        # 如果没找到图片，直接创建一个黑图以防报错退出
        test_img  = np.zeros((512, 512, 3), dtype=np.uint8)

    # 创建一个模拟的"主窗口"对象
    # 测试对话框需要访问 main_window.current_static_image，
    # 这里我们用 MockMainWindow 模拟这个属性
    class MockMainWindow:
        def __init__(self, img):
            self.current_static_image = img # 把图片赋给这个属性
            self.cap = None

        # 占位函数，防止调用时抛出 AttributeError
        def _process_and_display_frame(self, frame):
            pass

        def update_frame(self):
            pass

    mock_main_window = MockMainWindow(test_img )

    # 创建一个模拟的流程图节点
    class MockNode:
        def __init__(self):
            self.params = {}

    mock_node = MockNode()

    # 实例化参数配置对话框，将模拟的主窗口和节点传进去
    dialog = LineParamsDialog(parent=None, node=mock_node, main_window=mock_main_window)
    dialog.setWindowTitle("直线查找 - 框选测试窗口")
    dialog.resize(390, 560)

    # 显示对话框
    dialog.show()

    sys.exit(app.exec_())