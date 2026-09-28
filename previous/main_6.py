import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QGraphicsView
)
# 打开主窗口，显示小窗口，模体ui窗口，设置layout， 设置流程图画布
from PySide2.QtUiTools import QUiLoader # 导入ui
from PySide2.QtGui import QIcon, QImage, QPixmap  # 设置图标，显示图像
from PySide2.QtCore import QTimer, Qt, QPointF # 图像显示需要设置线程，不然打开摄像头后ui界面会卡死

import cv2

from Detector import DetectorShape
from FlowChart import NodeItem, EdgeItem, FlowchartView

'''
修复RuntimeError错误
'''

uiloader = QUiLoader()

class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头相关参数
        self.cap = None # 视频捕获对象
        self.timer = None # 刷新定时器
        self.camera_id = 0  # 默认摄像头ID，可通过设置菜单修改

        # 通过 findChild 找到被 tab 包裹的 video 和 graphicsView 控件
        # 将下面的所有 main_window.video 改成 videoLabel
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")

        # 设置按钮
        self.main_window.camera_button.clicked.connect(self.open_camera) # 开启摄像头按钮
        self.main_window.close_button.clicked.connect(self.close_camera) # 关闭摄像头按钮
        self.main_window.open_button.clicked.connect(self.print_aaa)

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
        self.main_window.tree.setDragEnabled(True) # 拖动使能，可以拖动里面树枝控件
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction) # 拖拽时的行为是“复制”，而不是“剪切”
        # 获取 UI 中的 graphicsView，替换为 FlowchartView，相对于在用来的基础上创建一个新的 graphicsView，这个新的可以实现拖拽等功能
        # 通过 findChild 找到被 tab 包裹的 video 和 graphicsView 控件
        view = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        if view:
            parent = view.parent() # 获取这个空画布的父容器
            geometry = view.geometry() # 获取这个画布当前所在的位置和大小
            view.deleteLater() # 把原先那个只是用来占位、没有任何交互功能的空画布彻底销毁，释放内存。
            # 实例化 FlowchartView，把主窗口 self 传进去
            self.main_window.graphicsView = FlowchartView(parent, main_window=self)
            self.main_window.graphicsView.setGeometry(geometry) # 覆盖原来的 graphicsView 的位置和大小
            self.main_window.graphicsView.show() # 显示
            # 每次刷新时全屏更新，防止有拖尾残影
            self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # 树控件 tree 绑定双击事件，双击实现在画布view中创建方框流程图
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)


    def print_aaa(self):
        print(111)


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

        self.videoLabel.clear() # 关闭摄像头
        self.videoLabel.setText("video") # 设置label里面的文本为video
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
            self.close_camera()
            QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
            return

        '''通过 树状图 和 流程图 设置检测不同的内容'''
        data = []
        if self.flow_nodes:
            frame, data = self._run_flow_pipeline(frame)
        else:
            pass
            frame, data = self.process_frame(frame)

        # OpenCV BGR -> RGB ; qt和opencv使用的颜色通道顺序不同，所以需要转换
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888) # type: ignore

        # 缩放并显示，保持宽高比（使用 Qt.KeepAspectRatio）
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.videoLabel.size(), Qt.KeepAspectRatio)
        self.videoLabel.setPixmap(scaled)
        self.videoLabel.setStyleSheet("")  # 清除文字样式

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
            # 后续可加入人脸、颜色等
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
            return frame, [] # 需要返回两个值，第二个列表，保持和外面检测内容一样


    def add_flow_node(self, name, pos):
        # 添加节点时，绑定信号并更新连线逻辑
        node = NodeItem(name, pos)  # 创建节点方框
        self.main_window.graphicsView.scene.addItem(node)  # 添加到画布view中

        # 给这个节点绑上连线刷新信号
        node.positionChanged.connect(self.update_all_edges)  # type:ignore

        if self.flow_nodes:
            prev_node = self.flow_nodes[-1]
            # 自动连线：前一个节点的输出 -> 当前节点的输入
            edge = EdgeItem(prev_node.get_output_pos(), node.get_input_pos())  # 连线
            self.main_window.graphicsView.scene.addItem(edge)  # 添加到画布view中
            self.flow_edges.append(edge)  # 添加到列表flow_edges[]中，方便管理

        self.flow_nodes.append(node)  # 添加到flow_nodes[]中，方便管理

        # 新节点加入后，立刻用延时器保证连线正确对齐
        QTimer.singleShot(0, self.update_all_edges)

        return node

    def delete_flow_node(self, node_to_delete):
        """删除节点方框，并重新整理方框的连接曲线"""
        if node_to_delete not in self.flow_nodes:
            return

        idx = self.flow_nodes.index(node_to_delete) # 流程图节点序号
        n = len(self.flow_nodes) # 流程图节点列表长度

        # 从画布中移除节点
        self.main_window.graphicsView.scene.removeItem(node_to_delete)

        # 根据节点位置处理列表和连线
        if n == 1:
            # 只有一个节点，清空所有列表
            self.flow_nodes.clear()
            for e in self.flow_edges:
                self.main_window.graphicsView.scene.removeItem(e)
            self.flow_edges.clear()

        elif idx == 0:
            # 删除头部节点
            self.flow_nodes.pop(0)
            e = self.flow_edges.pop(0)
            self.main_window.graphicsView.scene.removeItem(e)

        elif idx == n - 1:
            # 删除尾部节点
            self.flow_nodes.pop()
            e = self.flow_edges.pop()
            self.main_window.graphicsView.scene.removeItem(e)

        else:
            # 删除中间节点
            self.flow_nodes.pop(idx)
            # 弹出与它相关的两条连线
            e1 = self.flow_edges.pop(idx - 1)
            e2 = self.flow_edges.pop(idx - 1)
            self.main_window.graphicsView.scene.removeItem(e1)
            self.main_window.graphicsView.scene.removeItem(e2)

            # 将它的前一个和后一个节点重新连接起来
            prev_node = self.flow_nodes[idx - 1]
            next_node = self.flow_nodes[idx]
            new_edge = EdgeItem(prev_node.get_output_pos(), next_node.get_input_pos())
            self.main_window.graphicsView.scene.addItem(new_edge)
            self.flow_edges.insert(idx - 1, new_edge)

        # 触发全局面板更新
        self.update_all_edges()

    def update_all_edges(self):
        """
        可更新的边缘连接曲线，移动方框后曲线会跟着移动
        全局连线更新函数，遍历所有节点并更新之间的连线
        """
        # 如果有节点，根据现有的连线列表更新它们的端点坐标
        for i, edge in enumerate(self.flow_edges):
            start_node = self.flow_nodes[i] # 开始start节点
            end_node = self.flow_nodes[i + 1] # 结束end节点
            new_start = start_node.get_output_pos() # 获取开始节点
            new_end = end_node.get_input_pos() # 获取结束节点
            edge.update_positions(new_start, new_end) # 更新位置

    def _on_tree_double_click(self, item, column):
        """双击左侧树节点时触发（数据抓取阶段）"""
        # 获取当前项的 QModelIndex（这是轻量级值，非常安全）
        index = self.tree.currentIndex()
        if not index.isValid():
            return

        # 判断是否是根节点（一级标题），如果是则不放行
        parent = index.parent()
        if not parent.isValid():
            return

        # 直接通过 index 获取节点名称（安全的纯文本数据，并非指针）
        node_name = index.data(0)
        if not node_name:
            return

        # 只有 1 毫秒的延迟，把“文本数据”而不是“C++对象”传给创建函数
        QTimer.singleShot(1, lambda: self._create_node_from_name(node_name))


    def _create_node_from_name(self, name):
        """
        双击树状图的树枝后执行的内容
        _为只有item这个参数，不用管第二个参数(_)，但是第二个参数不能删除
        有出错RuntimeError，相较于 FlowChart 进行了略微修改
        """

        '''计算新方框的摆放坐标'''
        if self.flow_nodes:
            # 第二个或者之后方框的位置
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x()  # + 180 # x方向距离增加180
            new_y = last_node.pos().y() + 180  # y方向距离不变
        else:
            new_x, new_y = 20, 20  # 第一个方框的位置

        self.add_flow_node(name, QPointF(new_x, new_y))



def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))#主窗口添加图标
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()