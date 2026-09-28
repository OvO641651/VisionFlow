from PySide2.QtCore import Qt, QPointF, QObject, Signal, QTimer  # 新增 QObject, Signal, QTimer
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem
)

'''
修复了方框移动线不动的问题
修复了只能双击创建方框，不能拖动创建
'''


# ---------- 自定义节点和连线类 ----------
class NodeItem(QObject, QGraphicsRectItem):  # 关键修改1：多重继承 QObject
    """流程图节点"""
    positionChanged = Signal()  # 关键修改2：定义位置改变信号

    def __init__(self, name, pos):
        QObject.__init__(self)  # 显式初始化 QObject 父类
        QGraphicsRectItem.__init__(self, 0, 0, 140, 50)  # 显式初始化图形父类

        self.name = name
        self.setPos(pos)
        self.setBrush(QBrush(QColor(250, 250, 250)))
        self.setPen(QPen(QColor("darkblue"), 2))

        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)

        # 端口坐标（宽140，高50，所以端口在左右正中间）
        self.in_port = QPointF(0, 25)
        self.out_port = QPointF(140, 25)

    # 关键修改3：鼠标拖拽时实时更新信号
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)  # 物理移动方框
        self.positionChanged.emit()  # 通知外界位置变了

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)  # 鼠标松开
        self.positionChanged.emit()  # 最后一次安全更新

    def paint(self, painter, option: QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, option, widget)
        painter.drawText(super().rect(), Qt.AlignCenter, self.name)

        painter.setBrush(Qt.red)
        painter.drawEllipse(self.in_port, 4, 4)

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


class FlowchartView(QGraphicsView):
    """自定义流程图视图（支持拖放）"""
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window  # 保存主窗口的引用
        self.setAcceptDrops(True)  # 允许接收拖拽
        self.setDragMode(QGraphicsView.ScrollHandDrag)  # 开启抓手平移画布
        self.scene = QGraphicsScene()  # 创建画布场景
        self.setScene(self.scene)  # 绑定场景

    def dragEnterEvent(self, event):
        # 只要拖拽带有文本，或者来源于 QTreeWidget，都允许进入
        if event.mimeData().hasText() or isinstance(event.source(), QTreeWidget):
            event.acceptProposedAction()

    # 【核心修复 1】：必须加上 dragMoveEvent，否则因为 ScrollHandDrag 的干扰，dropEvent 永远不会触发
    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        print("======== dropEvent 已触发 ========") # 只要控制台输出这行，就说明拖拽成功了
        text = ""

        # 【核心修复 2】：无需依赖 MIME 数据，直接在拖拽完成时获取左侧树控件的当前选中项
        if self.main_window and hasattr(self.main_window, 'tree'):
            current = self.main_window.tree.currentItem()
            if current:
                text = current.text(0)
                print(f"✅ 成功抓取到模块名称: {text}")

        # 上面的方法 100% 有效，下面的作为备用保险
        if not text and self.main_window and hasattr(self.main_window, 'tree'):
            items = self.main_window.tree.selectedItems()
            if items:
                text = items[0].text(0)

        if not text:
            source = event.source()
            if isinstance(source, QTreeWidget):
                items = source.selectedItems()
                if items:
                    text = items[0].text(0)

        if not text:
            text = event.mimeData().text()

        # 如果提取到了文字，通知主窗口创建节点
        if text and self.main_window:
            pos = self.mapToScene(event.pos())
            self.main_window.add_flow_node(text, pos)
            event.acceptProposedAction()
        else:
            print("❌ 获取文本失败，请检查拖拽源！")
            event.ignore()


# ---------- 用于独立测试的窗口类 ----------
class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程图测试窗口 (拖拽连线测试版)")
        self.resize(800, 500)

        # 1. 左侧模块列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("检测模块")
        self.tree.setDragEnabled(True)
        self.tree.setDefaultDropAction(Qt.CopyAction)
        root = QTreeWidgetItem(self.tree, ["图像处理"])
        QTreeWidgetItem(root, ["直线"])
        QTreeWidgetItem(root, ["圆"])
        self.tree.expandAll()

        # 2. 右侧流程图
        self.flow_nodes = []  # 存放所有方块
        self.flow_edges = []  # 存放所有连线

        self.view = FlowchartView(main_window=self)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  # 防拖尾残影
        self.view.setAcceptDrops(True)

        # 3. 布局分割
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)  # type: ignore

    # 关键修改4：添加节点时，绑定信号并更新连线逻辑
    def add_flow_node(self, name, pos):
        node = NodeItem(name, pos)
        self.view.scene.addItem(node)

        # 给这个节点绑上连线刷新信号
        node.positionChanged.connect(self.update_all_edges)

        if self.flow_nodes:
            prev_node = self.flow_nodes[-1]
            # 自动连线：前一个节点的输出 -> 当前节点的输入
            edge = EdgeItem(prev_node.get_output_pos(), node.get_input_pos())
            self.view.scene.addItem(edge)
            self.flow_edges.append(edge)

        self.flow_nodes.append(node)

        # 关键修改5：新节点加入后，立刻用延时器保证连线正确对齐
        QTimer.singleShot(0, self.update_all_edges)

        return node

    def _on_tree_double_click(self, item, _):
        name = item.text(0)
        if self.flow_nodes:
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x() + 180
            new_y = last_node.pos().y()
        else:
            new_x, new_y = 20, 20
        self.add_flow_node(name, QPointF(new_x, new_y))

    # 关键修改6：全局连线更新函数，遍历所有节点并更新之间的连线
    def update_all_edges(self):
        # 如果有节点，根据现有的连线列表更新它们的端点坐标
        for i, edge in enumerate(self.flow_edges):
            start_node = self.flow_nodes[i]
            end_node = self.flow_nodes[i + 1]
            new_start = start_node.get_output_pos()
            new_end = end_node.get_input_pos()
            edge.update_positions(new_start, new_end)


def main():
    import sys
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()