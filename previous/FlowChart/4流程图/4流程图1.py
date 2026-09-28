from PySide2.QtCore import Qt, QPointF
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
# 修复1：移除未使用的 import QtWidgets，并补充导入 QGraphicsItem 和 QStyleOptionGraphicsItem
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem
)


# ---------- 自定义节点和连线类 ----------
class NodeItem(QGraphicsRectItem):
    """流程图节点"""
    def __init__(self, name, pos):
        super().__init__(0, 0, 140, 50)
        self.name = name
        self.setPos(pos)
        self.setBrush(QBrush(QColor(250, 250, 250)))
        self.setPen(QPen(QColor("darkblue"), 2))

        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.in_port = QPointF(20, 25)  # 输入端口（左侧）
        self.out_port = QPointF(120, 15)  # 输出端口（右侧）

    # 修复3：补充参数类型注解，消除 IDE 提示的“签名不匹配”警告
    def paint(self, painter, option: QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, option, widget)
        painter.drawText(super().rect(), Qt.AlignCenter, self.name)

        # 绘制输入端口（红点）
        painter.setBrush(Qt.red)
        painter.drawEllipse(self.in_port, 4, 4)

        # 绘制输出端口（蓝点）
        painter.setBrush(Qt.blue)
        painter.drawEllipse(self.out_port, 4, 4)

    def get_input_pos(self):
        return self.mapToScene(self.in_port)

    def get_output_pos(self):
        return self.mapToScene(self.out_port)


class EdgeItem(QGraphicsPathItem):
    """连线（贝塞尔曲线）"""

    def __init__(self, start, end):
        super().__init__()
        self.start = start
        self.end = end
        self.update_path()
        self.setPen(QPen(Qt.darkGray, 2)) # 设置画笔，即设置颜色，厚度为2

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


class FlowchartView(QGraphicsView):
    """自定义流程图视图（支持拖放）"""

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() or isinstance(event.source(), QTreeWidget):
            event.acceptProposedAction()

    def dropEvent(self, event):
        text = ""
        if isinstance(event.source(), QTreeWidget):
            items = event.source().selectedItems()
            if items:
                text = items[0].text(0)
        else:
            text = event.mimeData().text()

        if text and self.main_window:
            # 鼠标释放的坐标转换到场景坐标
            pos = self.mapToScene(event.pos())
            # 修复5：方法名去掉了下划线，消除“访问 protected 成员”的警告
            self.main_window.add_flow_node(text, pos)
            event.acceptProposedAction()


# ---------- 用于独立测试的窗口类 ----------
class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程图测试窗口")
        self.resize(800, 500)

        # 1. 左侧模块列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("检测模块")
        self.tree.setDragEnabled(True)
        self.tree.setDefaultDropAction(Qt.CopyAction)

        # 添加测试节点
        root = QTreeWidgetItem(self.tree, ["图像处理"])
        QTreeWidgetItem(root, ["直线"])
        QTreeWidgetItem(root, ["圆"])
        self.tree.expandAll()

        # 2. 右侧流程图
        self.flow_nodes = []
        self.view = FlowchartView(main_window=self)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setAcceptDrops(True)

        # 3. 布局分割
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # 修复4：此处 IDE 静态检查无法识别 PySide2 的信号 connect 是正常现象，建议忽略此警告
        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)  # type: ignore

    # 修复5：更名为 add_flow_node（去掉下划线），变为公开方法
    def add_flow_node(self, name, pos):
        """在流程图中添加节点，并自动连线到前一个节点"""
        node = NodeItem(name, pos)
        self.view.scene.addItem(node)

        if self.flow_nodes:
            prev_node = self.flow_nodes[-1]
            # 自动连线：前一个节点的输出 -> 当前节点的输入
            edge = EdgeItem(prev_node.get_output_pos(), node.get_input_pos())
            self.view.scene.addItem(edge)

        self.flow_nodes.append(node)
        return node

    # 修复6：未使用的 column 形参，重命名为 _ 以消除警告
    def _on_tree_double_click(self, item, _):
        """双击列表项时，按顺序追加节点到流程图"""
        name = item.text(0)
        if self.flow_nodes:
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x() + 180
            new_y = last_node.pos().y()
        else:
            new_x, new_y = 20, 20

        self.add_flow_node(name, QPointF(new_x, new_y))


# ---------- 测试入口 ----------
def main():
    import sys
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()