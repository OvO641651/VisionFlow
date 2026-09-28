import sys
import cv2
import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QMimeData
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush, QPainterPath, QAction, QDrag
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QListWidget, QListWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsPixmapItem, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QFileDialog, QMessageBox
)

'''
拖拽窗口
'''

# ---------- 图像处理模块（示例） ----------
class LineDetector:
    """直线检测（霍夫变换）"""
    def process(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 50, minLineLength=50, maxLineGap=10)
        result = image.copy()
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 2)
        return result


class CircleDetector:
    """圆形检测（霍夫圆）"""
    def process(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, 20,
                                   param1=50, param2=30, minRadius=10, maxRadius=100)
        result = image.copy()
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                cv2.circle(result, (i[0], i[1]), i[2], (0, 255, 0), 2)
        return result


# 模块名称 -> 处理器
MODULE_MAP = {
    "直线检测": LineDetector(),
    "圆形检测": CircleDetector(),
}


# ---------- 流程图节点 ----------
class NodeItem(QGraphicsRectItem):
    """可拖动的处理模块节点"""
    pos_changed = Signal()  # 位置变化后通知更新连线

    def __init__(self, name, position):
        super().__init__(QRectF(0, 0, 120, 50))
        self.name = name
        self.setPos(position)
        self.setBrush(QColor(220, 230, 250))
        self.setPen(QPen(Qt.darkBlue, 2))
        self.setFlags(
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemIsSelectable |
            QGraphicsRectItem.ItemSendsGeometryChanges
        )
        self.in_port = QPointF(0, 25)          # 左侧中点
        self.out_port = QPointF(120, 25)       # 右侧中点

    def paint(self, painter: QPainter, option, widget):
        """绘制节点样式"""
        super().paint(painter, option, widget)
        painter.drawText(self.rect(), Qt.AlignCenter, self.name)
        # 输入端口（红点）
        painter.setBrush(Qt.red)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.in_port, 4, 4)
        # 输出端口（蓝点）
        painter.setBrush(Qt.blue)
        painter.drawEllipse(self.out_port, 4, 4)

    def get_input_port_scene_pos(self):
        return self.mapToScene(self.in_port)

    def get_output_port_scene_pos(self):
        return self.mapToScene(self.out_port)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.ItemPositionHasChanged:
            self.pos_changed.emit()
        return super().itemChange(change, value)


class EdgeItem(QGraphicsPathItem):
    """有向连线"""
    def __init__(self, start_pos, end_pos):
        super().__init__()
        self.start = start_pos
        self.end = end_pos
        self.setPen(QPen(Qt.darkGray, 2))
        self._update_path()

    def _update_path(self):
        path = QPainterPath()
        path.moveTo(self.start)
        # 贝塞尔曲线
        dx = abs(self.end.x() - self.start.x()) * 0.5
        ctrl1 = QPointF(self.start.x() + dx, self.start.y())
        ctrl2 = QPointF(self.end.x() - dx, self.end.y())
        path.cubicTo(ctrl1, ctrl2, self.end)
        self.setPath(path)

    def update_positions(self, start, end):
        self.start = start
        self.end = end
        self._update_path()


# ---------- 流程图场景 ----------
class FlowchartScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.nodes = []    # 顺序存储节点
        self.edges = []    # 存储连线
        self.setSceneRect(0, 0, 1600, 200)

    def add_module_node(self, pos, module_name):
        node = NodeItem(module_name, pos)
        self.addItem(node)
        # 自动与前一个节点连线
        if self.nodes:
            prev = self.nodes[-1]
            edge = EdgeItem(prev.get_output_port_scene_pos(),
                            node.get_input_port_scene_pos())
            self.addItem(edge)
            self.edges.append(edge)
            # 连接移动信号更新连线
            prev.pos_changed.connect(self._update_edges)
            node.pos_changed.connect(self._update_edges)
        self.nodes.append(node)
        return node

    def _update_edges(self):
        """所有连线更新位置"""
        for i, edge in enumerate(self.edges):
            start_node = self.nodes[i]
            end_node = self.nodes[i + 1]
            edge.update_positions(start_node.get_output_port_scene_pos(),
                                  end_node.get_input_port_scene_pos())

    def clear_flow(self):
        """清空流程图"""
        for item in self.nodes + self.edges:
            self.removeItem(item)
        self.nodes.clear()
        self.edges.clear()


# ---------- 流程图视图（支持拖放） ----------
class FlowchartView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setRenderHint(QPainter.Antialiasing)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('application/x-module'):
            event.acceptProposedAction()

    def dropEvent(self, event):
        data = event.mimeData().data('application/x-module')
        module_name = bytes(data).decode()
        scene_pos = self.mapToScene(event.position().toPoint())
        # 自动放置位置（顺序水平排列）
        scene = self.scene()
        if scene.nodes:
            last = scene.nodes[-1]
            x = last.pos().x() + 180
            y = last.pos().y()
        else:
            x, y = scene_pos.x(), scene_pos.y()
        scene.add_module_node(QPointF(x, y), module_name)
        event.acceptProposedAction()


# ---------- 图像显示区（可缩放平移） ----------
class ImageViewer(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self.pixmap_item)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setRenderHint(QPainter.SmoothPixmapTransform)

    def set_image(self, cv_image):
        """显示OpenCV图像 (BGR)"""
        rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.pixmap_item.setPixmap(QPixmap.fromImage(qimg))
        self._scene.setSceneRect(QRectF(0, 0, w, h))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def wheelEvent(self, event):
        """滚轮缩放"""
        factor = 1.1
        if event.angleDelta().y() < 0:
            factor = 0.9
        self.scale(factor, factor)


# ---------- 主窗口 ----------
class VisionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("简易视觉处理流程")
        self.resize(1400, 900)

        # 原始图像和处理结果
        self.original_image = None
        self.result_image = None

        # ---------- 左侧工具箱 ----------
        self.tool_list = QListWidget()
        self.tool_list.setDragEnabled(True)
        self.tool_list.setDefaultDropAction(Qt.CopyAction)
        for name in MODULE_MAP.keys():
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, name)
            self.tool_list.addItem(item)
        # 双击添加
        self.tool_list.itemDoubleClicked.connect(self._on_double_click)

        # ---------- 右侧上方：图像显示 ----------
        self.image_view = ImageViewer()

        # ---------- 右侧下方：流程图 ----------
        self.flow_scene = FlowchartScene()
        self.flow_view = FlowchartView(self.flow_scene)
        self.flow_view.setFixedHeight(200)  # 固定高度或使用布局

        # ---------- 右侧布局 ----------
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.image_view)
        right_splitter.addWidget(self.flow_view)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)

        # ---------- 总布局 ----------
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.tool_list)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 4)

        # 控制按钮
        control_widget = QWidget()
        btn_layout = QHBoxLayout(control_widget)
        btn_open = QPushButton("打开图片")
        btn_run = QPushButton("运行流程")
        btn_clear = QPushButton("清空流程")
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_run)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()

        central_layout = QVBoxLayout()
        central_layout.addWidget(main_splitter)
        central_layout.addWidget(control_widget)

        central_widget = QWidget()
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)

        # 信号连接
        btn_open.clicked.connect(self._open_image)
        btn_run.clicked.connect(self._run_pipeline)
        btn_clear.clicked.connect(self.flow_scene.clear_flow)

    def _on_double_click(self, item):
        """双击左侧列表项，添加到流程图末尾"""
        module_name = item.data(Qt.UserRole)
        scene = self.flow_scene
        if scene.nodes:
            last = scene.nodes[-1]
            x = last.pos().x() + 180
            y = last.pos().y()
        else:
            x, y = 20, 20
        scene.add_module_node(QPointF(x, y), module_name)

    def _open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开图片", "",
                                              "Images (*.png *.jpg *.bmp)")
        if path:
            self.original_image = cv2.imread(path)
            self.result_image = self.original_image.copy()
            self.image_view.set_image(self.original_image)

    def _run_pipeline(self):
        if self.original_image is None:
            QMessageBox.warning(self, "提示", "请先打开一张图片")
            return
        if not self.flow_scene.nodes:
            QMessageBox.warning(self, "提示", "流程图为空，请添加检测模块")
            return

        image = self.original_image.copy()
        for node in self.flow_scene.nodes:
            processor = MODULE_MAP.get(node.name)
            if processor:
                image = processor.process(image)
            else:
                QMessageBox.critical(self, "错误", f"未知模块: {node.name}")
                return
        self.result_image = image
        self.image_view.set_image(image)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VisionApp()
    window.show()
    sys.exit(app.exec())
