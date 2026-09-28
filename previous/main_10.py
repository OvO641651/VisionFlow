import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QGraphicsView, QFileDialog
)
# 打开主窗口，显示小窗口，模体ui窗口，设置layout，设置流程图画布，导入文件
from PySide2.QtUiTools import QUiLoader  # 导入ui
from PySide2.QtGui import QIcon, QImage, QPixmap  # 设置图标，显示图像
from PySide2.QtCore import QTimer, Qt, QPointF  # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2

from Detector import DetectorShape
from FlowChart import NodeItem, EdgeItem, FlowchartView

"""
添加删除连接曲线的功能
并修复删除方框后对应的检测内容依然在图片上显示的bug
"""

uiloader = QUiLoader()


class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头相关参数
        self.cap = None  # 视频捕获对象
        self.timer = None  # 刷新定时器
        self.camera_id = 0  # 默认摄像头ID，可通过设置菜单修改
        self._is_video_file = False  # 标记当前打开的是否为视频文件

        # 【新增】用于存储当前加载的静态图片
        self.current_static_image = None

        # 通过 findChild 找到被 tab 包裹的 video 和 graphicsView 控件
        # 将下面的所有 main_window.video 改成 videoLabel
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")

        # 设置按钮
        self.main_window.camera_button.clicked.connect(self.open_camera)  # 开启摄像头按钮
        self.main_window.close_button.clicked.connect(self.close_camera)  # 关闭摄像头按钮
        self.main_window.open_button.clicked.connect(self.open_file)  # 导入图片或者视频

        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后 弹出 新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 创建树控件
        self.tree = self.main_window.tree
        # 树状图点击事件
        self.main_window.tree.itemClicked.connect(self.on_tree_item_clicked)
        # 当前检测模式
        self.detection_mode = None

        # 流程图初始化，按照 FlowChart 中的 TestWindow 类的内容进行初始化和编写具体内容
        # 初始化节点和连线列表
        self.flow_nodes = []  # 存放所有方框
        self.flow_edges = []  # 存放所有连线
        # 启用左侧树控件的拖拽功能
        self.main_window.tree.setDragEnabled(True)  # 拖动使能，可以拖动里面树枝控件
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction)  # 拖拽时的行为是“复制”，而不是“剪切”
        # 获取 UI 中的 graphicsView，替换为 FlowchartView，相对于在用来的基础上创建一个新的 graphicsView，这个新的可以实现拖拽等功能
        # 通过 findChild 找到被 tab 包裹的 video 和 graphicsView 控件
        view = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        if view:
            parent = view.parent()  # 获取这个空画布的父容器
            geometry = view.geometry()  # 获取这个画布当前所在的位置和大小
            view.deleteLater()  # 把原先那个只是用来占位、没有任何交互功能的空画布彻底销毁，释放内存。
            # 实例化 FlowchartView，把主窗口 self 传进去
            self.main_window.graphicsView = FlowchartView(parent, main_window=self)
            self.main_window.graphicsView.setGeometry(geometry)  # 覆盖原来的 graphicsView 的位置和大小
            self.main_window.graphicsView.show()  # 显示
            # 每次刷新时全屏更新，防止有拖尾残影
            self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # 树控件 tree 绑定双击事件，双击实现在画布view中创建方框流程图
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)

    def print_aaa(self):
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

        ext = file_path.lower()  # 将获得的绝对路径转换成小写 PNG->png
        # endswith:检测后缀
        if ext.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            # 处理单张图片
            frame = cv2.imread(file_path)  # 读取图片
            if frame is None:
                # 如果读取图片失败，则弹出小窗口警告
                QMessageBox.warning(self.main_window, "错误", "无法读取图片文件")
                return

            # 【修改】保存当前加载的静态图片
            self.current_static_image = frame

            # 单张图片不需要循环，直接处理并显示
            self._process_and_display_frame(frame)

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
            self.timer = QTimer()  # 创建新的定时器
            # 绑定处理函数
            self.timer.timeout.connect(self.update_frame)  # type:ignore
            self.timer.start(30)  # 30帧fps
        else:
            # 既不是图片也不是视频时，弹出小窗口警告
            QMessageBox.warning(self.main_window, "错误", "不支持的文件格式")

    def _process_and_display_frame(self, frame):
        """按流程图或树状图模式处理一帧图像，并渲染到 videoLabel"""
        # 【核心修复】：必须在这里拷贝一份图像！(在副本上进行修改)
        # 否则 cv2.line/cv2.circle 会直接修改原始的 self.current_static_image 缓存，
        # 导致即使流程图空了，显示的图片依然是“画花”的版本。
        work_frame = frame.copy()

        '''通过 树状图 和 流程图 设置检测不同的内容'''
        if self.flow_nodes:
            # 流程图模式：将副本传入流水线
            work_frame, data = self._run_flow_pipeline(work_frame)
        else:
            # 流程图空时，直接返回纯净的原始图片副本
            work_frame, data = work_frame, []

        # OpenCV BGR -> RGB ; qt和opencv使用的颜色通道顺序不同，所以需要转换
        rgb_frame = cv2.cvtColor(work_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888)  # type: ignore

        # 缩放并显示，保持宽高比（使用 Qt.KeepAspectRatio）
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.videoLabel.size(), Qt.KeepAspectRatio)
        self.videoLabel.setPixmap(scaled)
        self.videoLabel.setStyleSheet("")  # 清除文字样式

    def open_camera(self):
        """打开摄像头并启动视频刷新"""
        # 如果当前正在播放视频，强制关闭视频，避免冲突
        if self.cap is not None and self.cap.isOpened() and self._is_video_file:
            self.close_camera()

        if self.cap is not None and self.cap.isOpened():
            return

        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            # 如果识别不到摄像头标签，则弹出警告的小窗口
            QMessageBox.warning(self.main_window, "错误", "无法打开摄像头，请检查设备连接")
            self.cap = None
            return

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)  # type: ignore
        self.timer.start(30)

    def close_camera(self):
        """关闭摄像头，停止定时器，清空显示区域"""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        # 重置视频标注
        self._is_video_file = False

        # 【新增】关闭时清空静态图片缓存
        self.current_static_image = None

        self.videoLabel.clear()  # 关闭摄像头
        self.videoLabel.setText("video")  # 设置label里面的文本为video
        # 设置video背景为黑色，虽然在stylesheet里面设置，但是关闭摄像头时会情况，所以需要在代码中修改
        self.videoLabel.setStyleSheet(
            "background-color: black; color: white; font-size: 24px; font-weight: bold;")

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

        # 调用通用处理与显示函数
        self._process_and_display_frame(frame)

    def _run_flow_pipeline(self, frame):
        """按流程图节点顺序执行检测"""
        img = frame
        data = []
        for node in self.flow_nodes:
            if node.name == "直线":
                img, d = self.detector.line_detector(img)
                data.extend(d)
            elif node.name == "圆":
                img, d = self.detector.circle_detector(img)
                data.extend(d)
            elif node.name == "灰度":
                img, _ = self.detector.gray(img)
            # 后续可加入人脸、颜色等
        return img, data

    def close_event(self, event):
        """窗口关闭时释放摄像头"""
        self.close_camera()
        event.accept()  # 允许窗口关闭

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

    def on_tree_item_clicked(self, item, column):
        """
        '''根据点击树状图的内容（如检测）切换到不同的模式'''
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
        index = self.tree.currentIndex()  # 获取当前树控件的页面
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
        else:
            # 无检测时返回原图（即正常播放视频）
            return frame, []  # 需要返回两个值，第二个列表，保持和外面检测内容一样

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
        # QTimer.singleShot(0, self.update_all_edges)

        # 【新增】如果当前有静态图片，立刻用更新后的流程图重绘
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

        return node

    def add_edge(self, start_node, end_node):
        """从蓝点开始生成一条曲线"""
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                # 防止重连，即相同的起点和相同的终点
                return
        edge = EdgeItem(start_node, end_node)  # 实例化EdgeItem类对象
        self.main_window.graphicsView.scene.addItem(edge)  # 添加到画布里面
        self.flow_edges.append(edge)  # 添加到列表里面记录
        self.update_all_edges()  # 刷新一次画面，刷新出曲线

        # 【新增】如果当前有静态图片，立刻用更新后的流程图重绘
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
            self.main_window.graphicsView.scene.removeItem(edge)  # 从画布上擦除这条线的图像
            self.flow_edges.remove(edge)  # 从数据列表里清空这条线的记录
        self.main_window.graphicsView.scene.removeItem(node_to_delete)  # 把这个方块本身从画布上彻底抹去
        self.flow_nodes.remove(node_to_delete)  # 从列表中移除节点记录
        self.update_all_edges()  # 刷新画面

        # 【新增】如果当前有静态图片，立刻用更新后的流程图重绘
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def update_all_edges(self):
        """可更新的边缘连接曲线，移动方框后曲线会跟着移动"""
        for edge in self.flow_edges:
            # 遍历所有已存在的连线
            edge.update_positions()  # 命令这条连线执行自身的刷新方法

    def _on_tree_double_click(self, item, column):
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
        self.main_window.graphicsView.scene.removeItem(edge_to_delete)  # 在画布上删除
        self.flow_edges.remove(edge_to_delete)  # 在列表中删除
        self.update_all_edges()  # 刷新画面

        # 【新增】如果当前有静态图片，立刻用更新后的流程图重绘
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))  # 主窗口添加图标
    window = MainWindow()
    window.main_window.show()
    app.exec_()


if __name__ == '__main__':
    main()