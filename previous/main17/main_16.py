import numpy as np
import cv2
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QGraphicsView, QFileDialog
)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QIcon, QImage, QPixmap
from PySide2.QtCore import QTimer, Qt, QPointF

from Detector_16 import DetectorShape
from FlowChart_16 import NodeItem, EdgeItem, FlowchartView
from LineParamsDialog_17 import LineParamsDialog

"""
修复问题：
1、先创建节点再打开图片时，ROI参数会识别不到原图的大小，原本框住的区域应该为原图的大小
2、修复直线检测会检测到ROI绘制出的矩形框的边界的问题
3、在LineParamsDialog.ui里面添加了一个可以隐藏绘制出的黄框的复选框
4、流程图是一样的，都是直线->圆检测，但是隐藏绘制出的黄色矩形和不隐藏黄色矩形的圆检测结果却不同。
这可能是因为绘制的矩形影响到了下一次循环中的圆检测的过程。
"""


# ================= 主窗口类 MainWindow =================
class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # 摄像头相关参数
        self.cap = None
        self.timer = None
        self.camera_id = 0
        self._is_video_file = False
        self.current_static_image = None

        # 获取界面控件
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")
        self.main_window.camera_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)
        self.main_window.open_button.clicked.connect(self.open_file)
        self.main_window.closeEvent = self.close_event
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 树控件和画布
        self.tree = self.main_window.tree
        self.tree.setDragEnabled(True)
        self.tree.setDefaultDropAction(Qt.CopyAction)
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)

        self.flow_nodes = []
        self.flow_edges = []

        self.current_dialog = None  # 【新增】用于记录当前是否打开了配置窗口

        # 替换原有的 graphicsView 为流程图视图
        view = self.main_window.findChild(QtWidgets.QGraphicsView, "flowView")
        if view:
            parent = view.parent()
            geometry = view.geometry()
            view.deleteLater()
            self.main_window.graphicsView = FlowchartView(parent, main_window=self)
            self.main_window.graphicsView.setGeometry(geometry)
            self.main_window.graphicsView.show()
            self.main_window.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

    def _process_and_display_frame(self, frame):
        work_frame = frame.copy()
        if self.flow_nodes:
            work_frame, data = self._run_flow_pipeline(work_frame)

        # OpenCV BGR -> RGB
        rgb_frame = cv2.cvtColor(work_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.videoLabel.size(), Qt.KeepAspectRatio)
        self.videoLabel.setPixmap(scaled)
        self.videoLabel.setStyleSheet("")


    # =========== 【核心修改】处理流程 ===========
    def _run_flow_pipeline(self, frame):
        from collections import deque
        img = frame.copy()
        data = []
        if not self.flow_nodes or not self.flow_edges:
            return img, data

        # 构建图结构
        in_degree = {node: 0 for node in self.flow_nodes}
        graph = {node: [] for node in self.flow_nodes}
        for edge in self.flow_edges:
            if edge.end_node not in graph[edge.start_node]:
                graph[edge.start_node].append(edge)
            in_degree[edge.end_node] += 1

        queue = deque([node for node in self.flow_nodes if in_degree[node] == 0 and len(graph[node]) > 0])
        executed = set()

        # 【新增】：记录所有需要绘制的黄框参数列表
        rois_to_draw = []

        while queue:
            node = queue.popleft()
            if node in executed: continue
            executed.add(node)

            params = node.params
            roi_x = params.get("roi_x", 0)
            roi_y = params.get("roi_y", 0)
            roi_w = params.get("roi_w", img.shape[1])
            roi_h = params.get("roi_h", img.shape[0])

            # 截取 ROI 区域的图像，以免全图检测拖慢速度
            roi_img = img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
            if roi_img.size == 0:
                continue # 防止 ROI 尺寸为0报错

            # 执行具体检测（将子图的偏移量传入）
            if node.name == "直线":
                processed_roi, d = self.detector.line_detector(roi_img, roi_offset_x=roi_x, roi_offset_y=roi_y)
                # 将处理后的子图贴回原图（处理后的图自带检测线）
                img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w] = processed_roi
            elif node.name == "圆":
                processed_roi, d = self.detector.circle_detector(roi_img, roi_offset_x=roi_x, roi_offset_y=roi_y)
                img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w] = processed_roi
            elif node.name == "灰度":
                processed_roi, _ = self.detector.gray(roi_img)
                processed_roi = cv2.cvtColor(processed_roi, cv2.COLOR_GRAY2BGR)
                img[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w] = processed_roi

            # 【移除】：不要在循环内部画黄框，改为记录！
            hide_roi = params.get("hide_roi", False)
            rois_to_draw.append((roi_x, roi_y, roi_w, roi_h, hide_roi))

            for edge in graph[node]:
                if edge.end_node not in executed:
                    queue.append(edge.end_node)

        # 【新增】：在所有的算法执行完之后，统一在原图上绘制黄框！
        for rx, ry, rw, rh, hide in rois_to_draw:
            if not hide:
                cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), (0, 255, 255), 2)

        return img, data


    # =========== 【核心修改】双击回调 ===========
    def on_node_double_clicked(self, node):
        """双击流程图方框时触发的函数"""
        if node.name == "直线":
            # 直接使用导入的 LineParamsDialog，传入 (父窗口, 节点对象, 主窗口)
            dialog = LineParamsDialog(self.main_window, node=node, main_window=self)
            dialog.resize(390, 560)

            # 【新增】：记录当前激活的对话框，并绑定关闭时清空引用的信号
            self.current_dialog = dialog
            dialog.finished.connect(lambda: self._clear_current_dialog())

            dialog.exec_()  # 模态显示（程序会卡在此处，直到关闭对话框）
        elif node.name == "圆":
            print(22)
        else:
            print(33)

    def _clear_current_dialog(self):
        """对话框关闭时，清除内部持有的引用"""
        self.current_dialog = None




    def add_flow_node(self, name, pos):
        node = NodeItem(name, pos)
        self.main_window.graphicsView.scene.addItem(node)
        node.positionChanged.connect(self.update_all_edges)
        self.flow_nodes.append(node)
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)
        return node

    def add_edge(self, start_node, end_node):
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                return
        edge = EdgeItem(start_node, end_node)
        self.main_window.graphicsView.scene.addItem(edge)
        self.flow_edges.append(edge)
        self.update_all_edges()
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def delete_flow_node(self, node_to_delete):
        if node_to_delete not in self.flow_nodes: return
        edges_to_remove = []
        for edge in self.flow_edges:
            if edge.start_node == node_to_delete or edge.end_node == node_to_delete:
                edges_to_remove.append(edge)
        for edge in edges_to_remove:
            self.main_window.graphicsView.scene.removeItem(edge)
            self.flow_edges.remove(edge)
        self.main_window.graphicsView.scene.removeItem(node_to_delete)
        self.flow_nodes.remove(node_to_delete)
        self.update_all_edges()
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def update_all_edges(self):
        for edge in self.flow_edges:
            edge.update_positions()

    def _on_tree_double_click(self, item, column):
        index = self.tree.currentIndex()
        if not index.isValid(): return
        parent = index.parent()
        if not parent.isValid(): return
        node_name = index.data(0)
        if not node_name: return
        QTimer.singleShot(1, lambda: self._create_node_from_name(node_name))

    def _create_node_from_name(self, name):
        if self.flow_nodes:
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x()
            new_y = last_node.pos().y() + 180
        else:
            new_x, new_y = 20, 20
        self.add_flow_node(name, QPointF(new_x, new_y))

    def delete_edge(self, edge_to_delete):
        if edge_to_delete not in self.flow_edges: return
        self.main_window.graphicsView.scene.removeItem(edge_to_delete)
        self.flow_edges.remove(edge_to_delete)
        self.update_all_edges()
        if self.current_static_image is not None:
            self._process_and_display_frame(self.current_static_image)

    def close_event(self, event):
        self.close_camera()
        event.accept()

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

            # 保存当前加载的静态图片
            self.current_static_image = frame

            # 单张图片不需要循环，直接处理并显示
            self._process_and_display_frame(frame)

            # 【新增】：如果此时刚好有配置窗口开着，通知它刷新尺寸为图片的实际大小！
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
            self.timer = QTimer()  # 创建新的定时器
            # 绑定处理函数
            self.timer.timeout.connect(self.update_frame)  # type:ignore
            self.timer.start(30)  # 30帧fps
        else:
            # 既不是图片也不是视频时，弹出小窗口警告
            QMessageBox.warning(self.main_window, "错误", "不支持的文件格式")

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

        # 关闭时清空静态图片缓存
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

def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()