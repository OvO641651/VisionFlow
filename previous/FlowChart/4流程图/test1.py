import numpy as np
from PySide2 import QtWidgets
from PySide2.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout
)
from PySide2.QtUiTools import QUiLoader
from PySide2.QtGui import QIcon, QImage, QPixmap, QPainterPath, QPen, QColor, QBrush
from PySide2.QtCore import QTimer, Qt, QPointF, QRectF

import cv2
from Detector import DetectorShape

'''
流程图
'''

# ---------- 自定义节点和连线类 ----------
class NodeItem(QtWidgets.QGraphicsRectItem):
    """流程图节点"""
    def __init__(self, name, pos):
        super().__init__(0, 0, 140, 50)
        self.name = name
        self.setPos(pos)
        self.setBrush(QColor(220, 230, 250))
        self.setPen(QPen(QColor("darkblue"), 2))
        self.setFlags(self.flags() | QtWidgets.QGraphicsItem.ItemIsMovable | QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.in_port = QPointF(0, 25)     # 输入端口（左侧）
        self.out_port = QPointF(140, 25)  # 输出端口（右侧）

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.drawText(self.rect(), Qt.AlignCenter, self.name)
        painter.setBrush(Qt.red)
        painter.drawEllipse(self.in_port, 4, 4)
        painter.setBrush(Qt.blue)
        painter.drawEllipse(self.out_port, 4, 4)

    def get_input_pos(self):
        return self.mapToScene(self.in_port)

    def get_output_pos(self):
        return self.mapToScene(self.out_port)


class EdgeItem(QtWidgets.QGraphicsPathItem):
    """连线（贝塞尔曲线）"""
    def __init__(self, start, end):
        super().__init__()
        self.start = start
        self.end = end
        self.update_path()
        self.setPen(QPen(Qt.darkGray, 2))

    def update_path(self):
        path = QPainterPath()
        path.moveTo(self.start)
        dx = abs(self.end.x() - self.start.x()) * 0.5
        ctrl1 = QPointF(self.start.x() + dx, self.start.y())
        ctrl2 = QPointF(self.end.x() - dx, self.end.y())
        path.cubicTo(ctrl1, ctrl2, self.end)
        self.setPath(path)

    def update_positions(self, start, end):
        self.start = start
        self.end = end
        self.update_path()


class FlowchartView(QtWidgets.QGraphicsView):
    """自定义流程图视图（支持拖放）"""
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.scene = QtWidgets.QGraphicsScene()
        self.setScene(self.scene)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() or isinstance(event.source(), QtWidgets.QTreeWidget):
            event.acceptProposedAction()

    def dropEvent(self, event):
        text = ""
        if isinstance(event.source(), QtWidgets.QTreeWidget):
            items = event.source().selectedItems()
            if items:
                text = items[0].text(0)
        else:
            text = event.mimeData().text()
        if text and self.main_window:
            pos = self.mapToScene(event.pos())
            self.main_window._add_flow_node(text, pos)
            event.acceptProposedAction()


# ---------- 主窗口 ----------
class MainWindow:
    def __init__(self):
        # 设置主窗口
        self.main_window = QUiLoader().load('main.ui')
        self.detector = DetectorShape()

        # ---------- 通过 findChild 获取被 tab 包裹的控件 ----------
        self.graphicsView = self.main_window.findChild(QtWidgets.QGraphicsView, "graphicsView")
        self.videoLabel = self.main_window.findChild(QtWidgets.QLabel, "video")
        # -------------------------------------------------------------

        # 摄像头相关参数
        self.cap = None
        self.timer = None
        self.camera_id = 0

        # 设置按钮
        self.main_window.open_button.clicked.connect(self.open_camera)
        self.main_window.close_button.clicked.connect(self.close_camera)

        # 主窗口关闭后清空摄像头内存
        self.main_window.closeEvent = self.close_event

        # 点击设置->摄像头设置后弹出新窗口
        self.main_window.action.triggered.connect(self.set_camera_id)

        # 创建树控件
        self.tree = self.main_window.tree
        self.main_window.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.detection_mode = None

        # ---------- 新增：流程图初始化 ----------
        self.flow_nodes = []      # 存储流程图节点
        self.flow_edges = []      # 存储连线

        # 设置左侧树控件为可拖拽
        self.main_window.tree.setDragEnabled(True)
        self.main_window.tree.setDefaultDropAction(Qt.CopyAction)

        # ---------- 替换 graphicsView 为自定义 FlowchartView ----------
        old_view = self.graphicsView
        parent = old_view.parent()
        geometry = old_view.geometry()
        old_view.deleteLater()

        self.main_window.graphicsView = FlowchartView(parent, self)
        self.main_window.graphicsView.setGeometry(geometry)
        self.main_window.graphicsView.show()
        # -------------------------------------------------------------

        # 连接双击信号
        self.main_window.tree.itemDoubleClicked.connect(self._on_tree_double_click)

    # ---------- 原有方法 ----------
    def open_camera(self):
        if self.cap is not None and self.cap.isOpened():
            return
        self.cap = cv2.VideoCapture(self.camera_id)
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
        self.videoLabel.clear()
        self.videoLabel.setText("video")
        self.videoLabel.setStyleSheet("background-color: black; color: white; font-size: 24px; font-weight: bold;")

    def update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return
        ret, frame = self.cap.read()
        if not ret:
            self.close_camera()
            QMessageBox.warning(self.main_window, "错误", "摄像头读取失败，已关闭")
            return

        '''通过树状图设置检测不同的内容'''
        data = []
        # 优先执行流程图中的多个检测，否则执行单模式检测
        if self.flow_nodes:
            frame, data = self._run_flow_pipeline(frame)
        else:
            frame, data = self.process_frame(frame)

        # OpenCV BGR -> RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        rgb_frame = np.ascontiguousarray(rgb_frame)
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(qt_img)
        scaled = pixmap.scaled(self.videoLabel.size(), Qt.KeepAspectRatio)
        self.videoLabel.setPixmap(scaled)
        self.videoLabel.setStyleSheet("")

    def close_event(self, event):
        self.close_camera()
        event.accept()

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

    def on_tree_item_clicked(self, item, column):
        index = self.tree.currentIndex()
        if not index.isValid():
            self.detection_mode = None
            return
        path = []
        while index.isValid():
            path.insert(0, index.row())
            index = index.parent()
        path_tuple = tuple(path)
        if path_tuple == (0, 0):
            self.detection_mode = 'line'
        elif path_tuple == (0, 1):
            self.detection_mode = 'circle'
        elif path_tuple == (1, 0):
            print(11)
        else:
            self.detection_mode = None

    def process_frame(self, frame):
        if self.detection_mode == 'line':
            return self.detector.line_detector(frame)
        elif self.detection_mode == 'circle':
            return self.detector.circle_detector(frame)
        else:
            return frame, []

    # ---------- 新增方法：流程图相关 ----------
    def _add_flow_node(self, name, pos):
        """在流程图视图中添加一个节点，并自动连线"""
        node = NodeItem(name, pos)
        self.main_window.graphicsView.scene.addItem(node)
        if self.flow_nodes:
            prev = self.flow_nodes[-1]
            edge = EdgeItem(prev.get_output_pos(), node.get_input_pos())
            self.main_window.graphicsView.scene.addItem(edge)
            self.flow_edges.append(edge)
        self.flow_nodes.append(node)

    def _on_tree_double_click(self, item):
        """双击左侧树控件，追加节点到流程图末尾"""
        name = item.text(0)
        if self.flow_nodes:
            last = self.flow_nodes[-1]
            new_x = last.pos().x() + 180
            new_y = last.pos().y()
        else:
            new_x, new_y = 20, 20
        self._add_flow_node(name, QPointF(new_x, new_y))

    def _run_flow_pipeline(self, frame):
        """按流程图顺序依次执行检测"""
        if not self.flow_nodes:
            return frame, []
        img = frame
        data = []
        for node in self.flow_nodes:
            if node.name == "直线":
                img, d = self.detector.line_detector(img)
                data.extend(d)
            elif node.name == "圆":
                img, d = self.detector.circle_detector(img)
                data.extend(d)
            # 可在此添加更多检测模块
        return img, data


def main():
    app = QApplication([])
    app.setWindowIcon(QIcon('image/lena.png'))
    window = MainWindow()
    window.main_window.show()
    app.exec_()

if __name__ == '__main__':
    main()