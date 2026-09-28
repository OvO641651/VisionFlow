import numpy as np
from PySide2 import QtWidgets, QtCore
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QGraphicsView, QFileDialog
)
# 打开主窗口，显示小窗口，模体ui窗口，设置流程图画布，导入文件
from PySide2.QtUiTools import QUiLoader # 导入ui
from PySide2.QtGui import QIcon, QImage, QPixmap  # QIcon设置图标，QImage显示图像
from PySide2.QtCore import QTimer, Qt, QPointF # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2
import time


from Detector import DetectorShape
from FlowChart import NodeItem, EdgeItem, FlowchartView
from LineParamsDialog import LineParamsDialog
from CircleParamsDialog import CircleParamsDialog
from ImageGraphicsView import ImageGraphicsView
from ImageGalleryWidget import ImageGalleryWidget

"""
1、添加ImageGraphicsView类，实现使用GraphicsView控件代替 Qlabel 控件显示图像画面的功能
"""

uiloader = QUiLoader()

class MainWindow:
    def __init__(self):
        self.abc = 1
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头相关参数
        self.cap = None # 视频捕获对象
        self.timer = None # 刷新定时器
        self.camera_id = 0  # 默认摄像头ID，可通过设置菜单修改
        self._is_video_file = False  # 标记当前打开的是否为视频文件
        # 用于视频 / 摄像头的单步执行状态
        self.video_processing_mode = "continuous"  # "continuous" 表示连续执行，"step" 表示单步执行
        self.video_step_node = None  # 当前单步执行的节点对象

        # 存储当前加载的静态图片，用于删除方框后恢复原图
        self.current_static_image = None

        # 初始化选中节点变量，用来显示当前单击选中的节点
        self.selected_node = None

        # 保存主窗口最后一次的检测结果，用来显示直线检测的结果
        self.last_detected_data = None


        '''# 通过 findChild 找到被 tab 包裹的 video 控件
        # 将下面的所有 main_window.video 改成 videoLabel
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")
        # ===== 新增修复：设置视频标签的尺寸策略，阻止布局震荡 =====
        self.videoLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.videoLabel.setMinimumSize(1, 1)'''
        # 【新增】获取 UI 中的 QGraphicsView，并替换为自定义的 ImageGraphicsView
        view_video  = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView_video")
        if view_video :
            parent_layout = view_video .parentWidget().layout()
            if parent_layout:
                # 实例化我们刚才写的自定义视图
                new_view = ImageGraphicsView(view_video .parentWidget())
                # 原地替换，保留布局拉伸比例
                parent_layout.replaceWidget(view_video , new_view)
                view_video .deleteLater()
                # 保存新控件的引用，备用
                self.image_view = new_view




        # 通过 findChild 获取文本 label 控件
        # 显示当前选中的流程图节点文本 lbl_current_node
        self.current_node_label = self.main_window.findChild(QtWidgets.QLabel, "lbl_current_node")

        # 通过 findChild 获取按钮控件名字Name
        # 打开摄像头
        self.camera_button = self.main_window.findChild(QtWidgets.QPushButton, "camera_button")
        # 关闭摄像头 或者 关闭图片
        self.close_button = self.main_window.findChild(QtWidgets.QPushButton, "close_button")
        # 打开图片
        self.open_button = self.main_window.findChild(QtWidgets.QPushButton, "open_button")
        # 单步执行按钮 btn_step_execute
        self.btn_step = self.main_window.findChild(QtWidgets.QPushButton, "btn_step_execute")
        # 连续执行按钮 btn_continuous_execute
        self.btn_continuous = self.main_window.findChild(QtWidgets.QPushButton, "btn_continuous_execute")


        # 设置按钮的点击 clicked 槽事件
        self.camera_button.clicked.connect(self.open_camera) # 开启摄像头按钮
        self.close_button.clicked.connect(self.close_camera) # 关闭摄像头按钮
        self.open_button.clicked.connect(self.open_file) # 导入图片或者视频
        self.btn_step.clicked.connect(self.on_step_execute) # 单步执行
        self.btn_continuous.clicked.connect(self.on_continuous_execute) # 连续执行


        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后 弹出 新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 创建树控件
        self.tree = self.main_window.tree
        # 树状图点击事件
        # self.main_window.tree.itemClicked.connect(self.on_tree_item_clicked)
        # 当前检测模式，用于点击树状图执行对应的检测
        # self.detection_mode = None
        # 树控件 tree 绑定双击事件，双击实现在画布view中创建方框流程图
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)


        # 流程图初始化，按照 FlowChart 中的 TestWindow 类的内容进行初始化和编写具体内容
        # 初始化节点和连线列表
        self.flow_nodes = []  # 存放所有方框
        self.flow_edges = []  # 存放所有连线

        self.current_dialog = None  # 用于记录当前是否打开了配置窗口

        # 启用左侧树控件的拖拽功能
        self.main_window.tree.setDragEnabled(True) # 拖动使能，可以拖动里面树枝控件
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction) # 拖拽时的行为是“复制”，而不是“剪切”
        # 获取 UI 中的 graphicsView，替换为 FlowchartView，相对于在用来的基础上创建一个新的 graphicsView，这个新的可以实现拖拽等功能
        # 通过 findChild 找到被 tab 包裹的 flowView 控件
        view_flow = self.main_window.findChild(QtWidgets.QGraphicsView, "flowView")
        if view_flow:
            # 直接获取父级布局
            parent_layout = view_flow.parentWidget().layout()
            if parent_layout:
                # 实例化新的 FlowchartView，使用和旧控件相同的父容器
                new_view = FlowchartView(view_flow.parentWidget(), main_window=self)
                # 使用布局引擎的 replaceWidget 原地替换，拉伸比例、边距都会被完美继承
                parent_layout.replaceWidget(view_flow, new_view)
                # 彻底销毁旧控件，释放内存
                view_flow.deleteLater()
                # 保存新控件的引用，以便代码中后续使用
                self.main_window.graphicsView = new_view
                # 每次刷新时全屏更新，防止有拖尾残影
                self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)


        # 使用 QTableWidget 表格控件来显示运行日志，控件名字 Name 为 execution_log
        self.execution_log = self.main_window.findChild(QtWidgets.QTableWidget, "execution_log")
        if self.execution_log:
            # 4个头标题
            self.execution_log.setColumnCount(4)
            # 4个头标题名称，在ui文件里面已经设置，但是在这里用代码设置更直观
            self.execution_log.setHorizontalHeaderLabels(["执行序号", "执行时间", "模块", "结果数据"])
            # 设置只读，不能修改内容
            self.execution_log.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            # 隐藏最左侧的垂直表头（行号）
            self.execution_log.verticalHeader().setVisible(False)


        # 改为（封装逻辑）：
        self.image_gallery = self.main_window.findChild(QtWidgets.QListWidget, "image_gallery")
        if self.image_gallery:
            # 实例化逻辑类，传入 UI 控件自身
            self.gallery_widget = ImageGalleryWidget(self.image_gallery)
            # 连接图库点击信号到主窗口的显示函数
            self.gallery_widget.image_selected.connect(self._on_gallery_image_selected)


    def _on_gallery_image_selected(self, img_bgr):
        """当用户点击图库中的图片时，切换主画面显示"""
        if img_bgr is not None:
            self.current_static_image = img_bgr
            self._process_and_display_frame(img_bgr)





    def print_aaa(self):
        self.abc = 2
        print(111)

    def open_file(self):
        """点击打开按钮后弹出文件选择框，可以选择图片或者视频进行导入"""
        '''
        QFileDialog.getOpenFileName()函数:
        parent:main_window, 
        caption:打卡的界面的名字, 
        dir:默认选择的文件目录(默认不选择), 
        filter:文件类型过滤器, 中间用;;隔开
        option:对话框选项标注
        返回 file_path, _ :选中文件的绝对路径；选择的文件的名称(_表示忽略)
        '''
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "选择图片或视频",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;视频文件 (*.mp4 *.avi *.mkv);;所有文件(*.*)"
        )
        if not file_path:
            return

        # 无论当前是播放摄像头还是视频，先关闭释放资源
        self.close_camera()

        ext = file_path.lower() # 将获得的绝对路径转换成小写 PNG->png
        # endswith:检测后缀
        if ext.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            # 处理单张图片
            frame = cv2.imread(file_path) # 读取图片
            if frame is None:
                # 如果读取图片失败，则弹出小窗口警告
                QMessageBox.warning(self.main_window, "错误", "无法读取图片文件")
                return

            # 保存当前加载的静态图片
            self.current_static_image = frame

            # 单张图片不需要循环，直接处理并显示
            self._process_and_display_frame(frame)


            # ===== 新增：把读取到的图片加到图库里 =====
            # ===== 修改为调用封装类的方法 =====
            if hasattr(self, 'gallery_widget'):
                self.gallery_widget.add_image(frame)



            # 如果此时刚好有配置窗口开着，通知它刷新尺寸为图片的实际大小
            if self.current_dialog and self.current_dialog.isVisible():
                self.current_dialog.refresh_size()

        elif ext.endswith(('.mp4', '.avi', '.mkv')):
            # 处理视频文件
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                # 如果读取视频失败，则弹出小窗口警告
                QMessageBox.warning(self.main_window, "错误", "无法打开视频文件")
                return
            self.cap = cap
            self._is_video_file = True

            # 启动定时器循环读取视频帧，每隔 30ms 自动执行一次 update_frame
            if self.timer is not None:
                # 清除旧的定时器
                self.timer.stop()
                self.timer = None
            self.timer = QTimer() # 创建新的定时器
            # 绑定处理函数
            self.timer.timeout.connect(self.update_frame) # type:ignore
            self.timer.start(30) # 30帧fps
        else:
            # 既不是图片也不是视频时，弹出小窗口警告
            QMessageBox.warning(self.main_window, "错误", "不支持的文件格式")


    def _process_and_display_frame(self, frame):
        """按流程图或树状图模式处理一帧图像，并渲染到 videoLabel"""
        # 与 update_frame 函数基本相同
        # 根据 流程图 或 树状图点击模式 处理帧，如果不想要点击树状图也进行处理，则可以删除掉process_frame函数

        # 拷贝一份图像，修复删除方框后对应的检测内容依然在图片上显示的bug
        work_frame = frame.copy()

        '''通过 树状图 设置检测不同的内容'''
        if self.flow_nodes:
            # 三个值解包，忽略 exec_info
            work_frame, data, _ = self._run_flow_pipeline(work_frame)
        else:
            work_frame, data = work_frame, []
            # work_frame, data = self.process_frame(work_frame)

        # 调用抽取出来的显示函数，也可以直接将该函数的内容放到这里
        self._display_image(work_frame)

    '''
    def _display_image(self, img):
        """将 OpenCV 图像转换并渲染到 UI 的 videoLabel 上"""
        # OpenCV BGR -> RGB ; qt和opencv使用的颜色通道顺序不同，所以需要转换
        rgb_frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888)  # type: ignore

        # 缩放并显示，保持宽高比（使用 Qt.KeepAspectRatio）
        pixmap = QPixmap.fromImage(qt_img)


        # 获取布局分配的大小
        size = self.videoLabel.size()
        # ===== 新增修复：防止刚开始未分配尺寸时导致出错 =====
        if size.width() <= 0 or size.height() <= 0:
            # 如果尺寸无效，则尝试使用父容器尺寸，或设置一个默认安全尺寸 640x480
            parent = self.videoLabel.parentWidget()
            if parent:
                size = parent.size()
            else:
                size = QSize(640, 480)
        # ===================================================


        scaled = pixmap.scaled(self.videoLabel.size(), Qt.KeepAspectRatio)
        self.videoLabel.setPixmap(scaled)
        self.videoLabel.setStyleSheet("")
        '''
    def _display_image(self, img):
        """将 OpenCV 图像渲染到自定义的 QGraphicsView 上"""
        if not hasattr(self, 'image_view'):
            return
        # 直接调用自定义视图的 set_image 方法，无需手动缩放
        self.image_view.set_image(img)


    def open_camera(self):
        """打开摄像头并启动视频刷新"""
        # 原本不管是图片还是视频，点击打开摄像头后都会清空原本的画面
        self.close_camera()

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
        """关闭摄像头，停止定时器，清空显示区域，包括导入的视频和图片"""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        # 重置视频标注
        self._is_video_file = False

        # 关闭时清空静态图片缓存
        self.current_static_image = None

        # =====【关键修复】删除对 QLabel 的操作，改为清空自定义 QGraphicsView 的画面 =====
        if hasattr(self, 'image_view') and self.image_view is not None:
            # 清空场景
            self.image_view.scene().clear()
            # 将 pixmap_item 重置为 None，防止下次打开图片时残留引用出错
            self.image_view.pixmap_item = None




    def update_frame(self):
        """定时器槽函数：读取摄像头帧并显示到 video 标签"""
        if self.cap is None or not self.cap.isOpened():
            # 识别不到摄像头时或者打开摄像头失败时执行返回，不读取视频帧
            return

        ret, frame = self.cap.read()
        if not ret:
            # 区分是摄像头出错还是视频播放结束
            if self._is_video_file:
                # 视频播放结束，停止定时器，释放资源（不弹警告，不清除最后一帧画面）
                if self.timer is not None:
                    self.timer.stop()
                    self.timer = None
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                self._is_video_file = False
                return
            else:
                # 摄像头读取失败
                self.close_camera()
                QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
                return

        work_frame = frame.copy()


        # 根据模式选择执行管道
        if self.video_processing_mode == "step" and self.video_step_node:
            # 处于单步执行模式且指定了目标节点
            work_frame, data = self._run_flow_pipeline_step(work_frame, self.video_step_node)
        else:
            # 处于连续执行模式（或未指定节点），执行完整流程图，解包三个值
            work_frame, data, exec_info = self._run_flow_pipeline(work_frame)
            # 更新日志
            self._update_execution_log(exec_info)

        # 调用通用处理与显示函数
        # 处理图片可以只使用_process_and_display_frame()函数，使用这个函数处理视频会默认按流程图整个流程进行处理
        # 但是处理视频得换成_display_image()函数
        self._display_image(work_frame)

        # 保存消息，避免关闭摄像头/视频时数据消失
        self.last_detected_data = data

        # 实时更新配置窗口的计数
        if self.current_dialog and self.current_dialog.isVisible():
            self.current_dialog.update_result_count(data)


    def _process_single_node(self, img, clean_img, node):
        """
        处理单个节点的通用检测逻辑
        :param img: 当前处理的图像
        :param clean_img: 原始图像副本，用于算法切片
        :param node: 当前要执行的节点
        :return: (处理后的图像, ROI信息元组)
                 ROI信息: (roi_x, roi_y, roi_w, roi_h, hide_roi)
                 如果 ROI 尺寸为0，返回 (img, None)
        """
        params = node.params
        roi_shape = params.get("roi_shape", "矩形") # 标记当前绘制ROI区域的形状
        roi_x = params.get("roi_x", 0)
        roi_y = params.get("roi_y", 0)
        roi_w = params.get("roi_w", img.shape[1])
        roi_h = params.get("roi_h", img.shape[0])

        # 隐藏 ROI
        hide_roi = params.get("hide_roi", False)

        # 截取 ROI 区域的图像
        roi_img = clean_img[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w].copy()

        # 复制纯净的切片，用于计算“新增像素”，即检测出来的 直线 或者 圆 等
        roi_img_original = roi_img.copy()

        data = []  # 初始化数据列表，用来输出检测到的直线/圆的数量

        if roi_img.size == 0:
            return img, None, []  # 跳过尺寸为0的异常情况

        processed_roi = None

        # 具体的检测逻辑
        if node.name == "直线":
            # 提取运行参数并传给检测算法
            canny_low = params.get("canny_low", 50)
            canny_high = params.get("canny_high", 150)
            hough_threshold = params.get("hough_threshold", 100)
            min_line_length = params.get("min_line_length", 100.0)
            max_line_gap = params.get("max_line_gap", 10.0)

            processed_roi, data = self.detector.line_detector(
                roi_img,
                roi_offset_x=roi_x,
                roi_offset_y=roi_y,
                canny_low=canny_low,
                canny_high=canny_high,
                threshold=hough_threshold,
                min_line_length=min_line_length,
                max_line_gap=max_line_gap
            )

        elif node.name == "圆":
            # 提取运行参数并传给圆的检测算法
            dp = params.get("dp", 1.0)
            min_dist = params.get("min_dist", 150.0)
            param1 = params.get("param1", 100.0)
            param2 = params.get("param2", 80.0)
            min_radius = params.get("min_radius", 20)
            max_radius = params.get("max_radius", 0)
            processed_roi, data = self.detector.circle_detector(
                roi_img,
                roi_offset_x=roi_x,
                roi_offset_y=roi_y,
                dp=dp,
                min_dist=min_dist,
                param1=param1,
                param2=param2,
                min_radius=min_radius,
                max_radius=max_radius
            )

        elif node.name == "灰度":
            # 传入纯净层切片 和 显示层切片
            clean_roi = clean_img[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
            display_roi = img[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
            # 调用 Detector 封装好的灰度处理方法
            processed_roi = self.detector.gray_with_preserve_lines(clean_roi, display_roi)
            if processed_roi is not None:
                img[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w] = processed_roi
            return img, (roi_x, roi_y, roi_w, roi_h, hide_roi, roi_shape), data
        # 后续可加入人脸、颜色等

        if processed_roi is not None:
            # 目标显示区域
            target_roi = img[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
            # 利用差值掩码，仅将新变化的像素叠加到显示层
            diff_mask = np.sum(np.abs(roi_img.astype(np.int16)
                                      - roi_img_original.astype(np.int16)), axis=2) > 0
            # 将画出的元素替换到原图中
            target_roi[diff_mask] = roi_img[diff_mask]
            # 将处理后的子图贴回原图
            img[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w] = target_roi

        # 把 roi_shape 作为一个 6 元素元组返回，由于输出检测到的直线/圆的数量
        return img, (roi_x, roi_y, roi_w, roi_h, hide_roi, roi_shape), data


    def _run_flow_pipeline(self, frame):
        """按流程图节点顺序执行检测"""
        from collections import deque  # 构造有向图，把无序的方框和连线转化成计算机能理解的有向图结构。

        img = frame.copy()
        all_data = []  # 汇总数据列表
        clean_img = frame.copy() # 干净的图片副本

        # 没有节点 or 没有连线
        if not self.flow_nodes or not self.flow_edges:
            return img, all_data, []

        # 建立图结构和入度统计
        # in_degree入度表：记录每个方框被多少条线指向。如果一个方框被3条线指向，它的入度就是 3；如果没有任何线指向它，入度就是 0。
        in_degree = {node: 0 for node in self.flow_nodes}
        # graph出边表：记录每个方框连着哪些方框。如果“直线”连向“圆”，那么graph["直线"]列表中就会包含"圆"对象。
        graph = {node: [] for node in self.flow_nodes}
        for edge in self.flow_edges:
            if edge.end_node not in graph[edge.start_node]:
                graph[edge.start_node].append(edge)
            in_degree[edge.end_node] += 1

        # 找出哪些是流程图的真正起点
        # in_degree[node] == 0 代表没有方框指向它（位于最顶端）
        # len(graph[node]) > 0 有线连向下一个方框
        queue = deque([node for node in self.flow_nodes if in_degree[node] == 0
                       and
                       len(graph[node]) > 0])
        executed = set()

        # 记录所有需要绘制的黄框参数列表
        rois_to_draw = []

        # 执行日志列表
        exec_info = []
        # 每个节点计数
        seq = 1

        while queue:
            node = queue.popleft() # 取出起点
            if node in executed:
                continue
            executed.add(node) # 用来记录哪些方框已经执行过了。如果发现已经执行过，就跳过，防止多分支循环导致的重复执行。

            # 调用 _process_single_node() 方法进行检测逻辑
            img, roi_info, data= self._process_single_node(img, clean_img, node)
            if roi_info is not None:
                rois_to_draw.append(roi_info)

            if data:  # 如果有数据，添加进总列表
                all_data.extend(data)


            # 无论有无数据都记录日志
            if node.name == "直线":
                result_text = f"检测到{len(data)}条直线"
            elif node.name == "圆":
                result_text = f"检测到{len(data)}个圆"
            elif node.name == "灰度":
                result_text = "执行成功"
            else:
                result_text = f"执行成功（{len(data)}条结果）"
            time_str = time.strftime("%H:%M:%S")
            exec_info.append((seq, time_str, node.name, result_text))
            seq += 1


            # 将所有的后继节点加入队列
            for edge in graph[node]:
                if edge.end_node not in executed:
                    queue.append(edge.end_node)

        # 在所有的算法执行完之后，统一在原图上绘制黄框
        for rx, ry, rw, rh, hide, roi_shape in rois_to_draw:
            if not hide:
                if roi_shape == "圆":
                    # 绘制黄色的圆形框
                    cv2.circle(img, (rx + rw // 2, ry + rh // 2), rw // 2, (0, 255, 255), 2)
                else:
                    # 绘制黄色的矩形框
                    cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), (0, 255, 255), 2)

        # 返回三个值
        return img, all_data, exec_info


    def _run_flow_pipeline_step(self, frame, target_node):
        """专门用于单步执行：仅对一个节点做 ROI 裁剪和处理"""
        img = frame.copy()
        clean_img = frame.copy() # 干净的图片副本

        # 调用 _process_single_node() 方法进行检测逻辑
        img, roi_info, data= self._process_single_node(img, clean_img, target_node)

        # 针对单步执行，画黄框的动作需要立刻在这里完成
        if roi_info is not None:
            # 解包 6 个参数
            rx, ry, rw, rh, hide, roi_shape = roi_info
            if not hide:
                if roi_shape == "圆":
                    # 绘制黄色的圆形 ROI 框
                    cv2.circle(img, (rx + rw // 2, ry + rh // 2), rw // 2, (0, 255, 255), 2)
                else:
                    # 绘制黄色的矩形 ROI 框
                    cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), (0, 255, 255), 2)

        return img, data



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

        # 模态显示（窗口打开后不能在动其他窗口），直到用户关闭
        dialog.exec_()

    '''
    # 不需要点击树控件执行对于的检测
    def on_tree_item_clicked(self, item, column):
        """
        # 根据点击树状图的内容（如检测）切换到不同的模式
        text = item.text(0)
        if text == '直线':
            self.detection_mode = 'line'
        elif text == '圆':
            self.detection_mode = 'circle'
        else:
            self.detection_mode = None
        """
        """
        根据点击项的层级索引来切换检测模式。
        索引路径：
            (0, 0) -> 检测 -> 直线
            (0, 1) -> 检测 -> 圆
        其他任意项 -> 取消检测 None
        """
        # 获取当前项的 QModelIndex
        index = self.tree.currentIndex()# 获取当前树控件的页面
        if not index.isValid():
            # 如果获取的页面是无效的则退出
            self.detection_mode = None
            return

        # 构建从根到当前项的索引路径（元组形式）
        path = []
        while index.isValid():
            # 将获取的项放到列表里面
            path.insert(0, index.row())
            index = index.parent()
        # 转换成元组，元组创建后不可更改，防止出错，而且元组可以直接进行比较path_tuple == (0, 0)
        path_tuple = tuple(path)

        # 根据路径设置检测模式
        if path_tuple == (0, 0):
            self.detection_mode = 'line'
        elif path_tuple == (0, 1):
            self.detection_mode = 'circle'
        elif path_tuple == (0, 2):
            self.detection_mode = 'gray'
        elif path_tuple == (1, 0):
            print(11)

        else:
            self.detection_mode = None


    def process_frame(self, frame):
        """根据当前检测模式，对视频帧进行处理并返回结果"""
        if self.detection_mode == 'line':
            return self.detector.line_detector(frame)
        elif self.detection_mode == 'circle':
            return self.detector.circle_detector(frame)
        elif self.detection_mode == 'gray':
            return self.detector.gray(frame)
        else:
            # 无检测时返回原图（即正常播放视频）
            return frame, [] # 需要返回两个值，第二个列表，保持和外面检测内容一样
    '''

    def add_flow_node(self, name, pos):
        # 添加节点时，绑定信号并更新连线逻辑
        node = NodeItem(name, pos)  # 创建节点方框
        self.main_window.graphicsView.scene.addItem(node)  # 添加到画布view中
        # 给这个节点绑上连线刷新信号
        node.positionChanged.connect(self.update_all_edges)  # type:ignore
        '''
        if self.flow_nodes:
            prev_node = self.flow_nodes[-1]
            # 自动连线：前一个节点的输出 -> 当前节点的输入
            edge = EdgeItem(prev_node.get_output_pos(), node.get_input_pos())  # 连线
            self.main_window.graphicsView.scene.addItem(edge)  # 添加到画布view中
            self.flow_edges.append(edge)  # 添加到列表flow_edges[]中，方便管理
        '''
        self.flow_nodes.append(node)  # 添加到flow_nodes[]中，方便管理
        # 新节点加入后，立刻用延时器保证连线正确对齐
        #QTimer.singleShot(0, self.update_all_edges)

        # 如果当前有静态图片，立刻用更新后的流程图重绘
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

        return node

    def add_edge(self, start_node, end_node):
        """从蓝点开始生成一条曲线"""
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                # 防止重连，即相同的起点和相同的终点
                return
        edge = EdgeItem(start_node, end_node) # 实例化EdgeItem类对象
        self.main_window.graphicsView.scene.addItem(edge) # 添加到画布里面
        self.flow_edges.append(edge) # 添加到列表里面记录
        self.update_all_edges() # 刷新一次画面，刷新出曲线

        # 如果当前有静态图片，立刻用更新后的流程图重绘
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def delete_flow_node(self, node_to_delete):
        """实现删除与需要删除的节点相连接的曲线"""
        if node_to_delete not in self.flow_nodes:
            # 检测节点是否存在
            return
        edges_to_remove = []
        for edge in self.flow_edges:
            # 找出任何起点或终点是当前要删除节点的连线
            if edge.start_node == node_to_delete or edge.end_node == node_to_delete:
                edges_to_remove.append(edge)
        for edge in edges_to_remove:
            # 遍历刚才找出来的待删除连线列表
            self.main_window.graphicsView.scene.removeItem(edge) # 从画布上擦除这条线的图像
            self.flow_edges.remove(edge) # 从数据列表里清空这条线的记录
        self.main_window.graphicsView.scene.removeItem(node_to_delete) # 把这个方块本身从画布上彻底抹去
        self.flow_nodes.remove(node_to_delete) # 从列表中移除节点记录
        self.update_all_edges() # 刷新画面

        # 如果当前有静态图片，立刻用更新后的流程图重绘
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def update_all_edges(self):
        """可更新的边缘连接曲线，移动方框后曲线会跟着移动"""
        for edge in self.flow_edges:
            # 遍历所有已存在的连线
            edge.update_positions()  # 命令这条连线执行自身的刷新方法


    def _on_tree_double_click(self, _item, _column):
        """双击左侧树节点时触发（数据抓取阶段）"""
        # 获取当前项的 QModelIndex
        index = self.tree.currentIndex()
        if not index.isValid():
            return

        # 判断是否是根节点（一级标题），如果是则不放行，即只双击树枝使才创建方框
        parent = index.parent()
        if not parent.isValid():
            return

        # 直接通过 index 获取节点名称
        node_name = index.data(0)
        if not node_name:
            return

        # 延迟 1 毫秒的，把“文本数据”而不是“C++对象”传给创建函数，然后触发创建方框的功能
        QTimer.singleShot(1, lambda: self._create_node_from_name(node_name))

    def _create_node_from_name(self, name):
        """双击树状图的树枝后执行的内容"""

        '''计算新方框的摆放坐标'''
        if self.flow_nodes:
            # 第二个或者之后方框的位置
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x()  # + 180 # x方向距离增加180
            new_y = last_node.pos().y() + 180  # y方向距离不变
        else:
            new_x, new_y = 20, 20  # 第一个方框的位置

        self.add_flow_node(name, QPointF(new_x, new_y))

    def delete_edge(self, edge_to_delete):
        """删除连接曲线"""
        if edge_to_delete not in self.flow_edges:
            # 判断要删除的曲线线是否还在当前的连线列表中
            return
        self.main_window.graphicsView.scene.removeItem(edge_to_delete) # 在画布上删除
        self.flow_edges.remove(edge_to_delete) # 在列表中删除
        self.update_all_edges() # 刷新画面

        # 如果当前有静态图片，立刻用更新后的流程图重绘
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def on_node_double_clicked(self, node):
        """双击流程图方框时触发的函数"""
        self.abc = 3
        """双击流程图方框时触发，弹出配置窗口"""
        # 双击直线检测节点弹出 LineParamsDialog 窗口
        if node.name == "直线":
            # 直接使用导入的 LineParamsDialog，传入 (父窗口, 节点对象, 主窗口)
            dialog = LineParamsDialog(self.main_window, node=node, main_window=self)
            dialog.resize(390, 560)

            # 记录当前激活的对话框，并绑定关闭时清空引用的信号
            self.current_dialog = dialog
            dialog.finished.connect(lambda: self._clear_current_dialog())

            dialog.exec_()  # 模态显示

        # 双击圆检测节点弹出 CircleParamsDialog 窗口
        elif node.name == "圆":
            # 【新增】弹出圆配置窗口
            dialog = CircleParamsDialog(self.main_window, node=node, main_window=self)
            dialog.resize(390, 560)
            self.current_dialog = dialog
            dialog.finished.connect(lambda: self._clear_current_dialog())
            dialog.exec_()


        else:
            print(33)

    def _clear_current_dialog(self):
        """对话框关闭时，清除内部持有的引用"""
        self.current_dialog = None


    def on_node_selected(self, node):
        """处理节点选中，当流程图中的节点被单击选中时调用"""
        self.selected_node = node
        if node:
            # 设置文本控件 label 的文本内容，文本控件的 Name 为 current_node_label
            self.current_node_label.setText(f"当前选中的节点为：{node.name}")
        else:
            self.current_node_label.setText("未选中节点")

    def on_step_execute(self):
        """点击单步执行按钮时触发：只执行当前选中的节点"""
        # 前置检查
        if self.current_static_image is None and self.cap is None:
            # 检测是否导入图片 / 视频 或者打开摄像头
            QMessageBox.warning(self.main_window, "提示", "请先导入图片/视频或者打开摄像头！")
            return
        if self.selected_node is None:
            # 检测是否选中节点
            QMessageBox.warning(self.main_window, "提示", "请先在流程图中单击选择一个节点！")
            return

        # 处理静态图片模式
        if self.current_static_image is not None:
            # 复制图像处理，防止污染原图
            work_frame = self.current_static_image.copy()
            # 仅执行选中的这个节点，调用单步执行_run_flow_pipeline_step函数
            work_frame, data = self._run_flow_pipeline_step(work_frame, self.selected_node)
            # 显示处理后的图像
            self._display_image(work_frame)

            # 保存数据并同步窗口
            self.last_detected_data = data  # 保存给以后打开的窗口使用
            if self.current_dialog and self.current_dialog.isVisible():
                self.current_dialog.update_result_count(data)

            return

        # 处理视频 / 摄像头模式
        if self.cap is not None and self.cap.isOpened():
            # 设置状态
            self.video_processing_mode = "step"
            self.video_step_node = self.selected_node
            # 立即主动刷新一帧画面，让用户立刻看到变成了单步检测的效果
            self.update_frame()

    def on_continuous_execute(self):
        """点击连续执行按钮时触发：按整个流程图顺序执行"""
        if self.current_static_image is None and self.cap is None:
            QMessageBox.warning(self.main_window, "提示", "请先导入图片/视频或者打开摄像头！")
            return

        # 静态图片模式：直接完整执行一次
        if self.current_static_image is not None:
            # 复用现有的完整图执行逻辑
            # self._process_and_display_frame(self.current_static_image)
            # 将上面的一行代码换成下面的一行
            work_frame = self.current_static_image.copy()
            # 调用连续执行_run_flow_pipeline函数，接收返回的 data，和日志 exec_info
            work_frame, data, exec_info = self._run_flow_pipeline(work_frame)
            # 更新日志
            self._update_execution_log(exec_info)
            self._display_image(work_frame)

            # 保存数据并同步窗口
            self.last_detected_data = data  # 保存给以后打开的窗口使用
            if self.current_dialog and self.current_dialog.isVisible():
                self.current_dialog.update_result_count(data)

            return

        # 视频 / 摄像头模式
        if self.cap is not None and self.cap.isOpened():
            # 恢复连续执行状态
            self.video_processing_mode = "continuous"
            self.video_step_node = None
            # 立即主动刷新一帧画面，恢复完整流程图检测效果
            self.update_frame()

    # 用表格显示执行日志，execution_log可更新的执行记录
    def _update_execution_log(self, exec_info):
        """
        用表格显示执行日志，刷新 execution_log 表格内容。
        该函数接收一个执行记录列表，将其清空并重新填充到 QTableWidget 中，实现执行日志的实时更新。
        :param exec_info: 执行记录列表，每个元素为 (序号, 时间字符串, 模块名, 结果描述)
        """
        if not self.execution_log:
            # 如果控件不存在
            return
        # 根据执行记录的数量设置表格的行数，自动清空旧数据并调整表格高度
        self.execution_log.setRowCount(len(exec_info))
        # 遍历每一条执行记录，row 为行号（从 0 开始），seq序号, time_str时间, module模式, result结果 为解包后的四个字段
        for row, (seq, time_str, module, result) in enumerate(exec_info):
            # 将四个字段转换为字符串列表，准备填充到表格的四个列中
            values = [str(seq), time_str, module, result]

            # 遍历当前行的每一列，col 为列号（0~3）
            for col, text in enumerate(values):
                # 创建一个新的表格项，存储该单元格的文本内容
                item = QtWidgets.QTableWidgetItem(text)
                # 将表格项放入指定行和列的单元格中
                # 如果该单元格已有内容，会自动替换；如果之前没有，会创建新单元格
                self.execution_log.setItem(row, col, item)





def main():
    # 开启高DPI缩放支持（必须在 QApplication 创建之前设置）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))#主窗口添加图标
    window = MainWindow()

    # 窗口启动时直接最大化
    window.main_window.showMaximized()
    # window.main_window.show() # 只显示，不最大化

    app.exec_()

if __name__ == '__main__':
    main()