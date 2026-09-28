from PySide2.QtCore import Qt, QPointF, Signal, QObject, QTimer
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem, QMenu, QAction, QWidget,
    QVBoxLayout
)


class NodeItem(QObject, QGraphicsRectItem):
    """流程图节点"""
    positionChanged = Signal()  # 自定义信号，解决线没有跟着方框一起动的问题

    def __init__(self, name, pos):
        """
        :param name: 节点名字
        :param pos: 位置
        """
        # 多重继承，继承QObject,QGraphicsRectItem，分别初始化
        QObject.__init__(self)
        QGraphicsRectItem.__init__(self, 0, 0, 140, 50)
        self.name = name
        self.setPos(pos)
        self.setBrush(QBrush(QColor(250, 250, 250)))
        self.setPen(QPen(QColor("darkblue"), 2))

        # 设置标志位，可以与外界交互
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        # 方框的尺寸为(140, 50)
        self.in_port = QPointF(70, 0)   # 输入端口（顶侧）
        self.out_port = QPointF(70, 50) # 输出端口（底侧）

    def mouseMoveEvent(self, event):
        """实时拖拽响应"""
        super().mouseMoveEvent(event)
        self.positionChanged.emit()  # type:ignore

    def mouseReleaseEvent(self, event):
        """鼠标松开"""
        super().mouseReleaseEvent(event)
        self.positionChanged.emit()  # type:ignore

    def contextMenuEvent(self, event):
        """右键点击节点时弹出菜单，实现删除方框"""
        menu = QMenu()
        delete_action = QAction("删除节点", menu)
        menu.addAction(delete_action)

        # 在鼠标点击的屏幕位置弹出菜单
        action = menu.exec_(event.screenPos())

        if action == delete_action:
            # 触发删除，通过视图寻找主窗口执行删除逻辑
            if self.scene() and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view, 'main_window'):
                    view.main_window.delete_flow_node(self)

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
    """连线（贝塞尔曲线）：S型平滑曲线"""
    def __init__(self, start, end):
        super().__init__()
        self.start = start
        self.end = end
        self.update_path()
        self.setPen(QPen(QColor("darkGray"), 2))

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
    """
    自定义流程图视图（支持拖放）
    继承画布QGraphicsView模块(用来放置方块的模块)
    """
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window  # 这里传入的是外部使用者的窗口实例，为了获取其 tree 属性
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() or isinstance(event.source(), QTreeWidget):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        text = ""
        # 注意：这里通过外部传入的 main_window 读取其 tree
        if self.main_window and hasattr(self.main_window, 'tree'):
            current = self.main_window.tree.currentItem()
            if current:
                text = current.text(0)

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

        if text and self.main_window:
            pos = self.mapToScene(event.pos())
            self.main_window.add_flow_node(text, pos)
            event.acceptProposedAction()
        else:
            event.ignore()


# =====================================================================
# 纯净的流程图画布组件。不包含左侧树控件！
# 用于在 main.py 中直接使用
# =====================================================================
class FlowchartCanvas(QWidget):
    """
    纯净的流程图画布组件。不包含左侧树控件。
    如果你在 main.py 中使用，直接实例化并添加到你的 TabWidget 布局中即可。
    """
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)

        # 内部只维护节点和连线数据
        self.flow_nodes = []  # 存放所有方块
        self.flow_edges = []  # 存放所有连线

        # 创建视图
        self.view = FlowchartView(self, main_window) # 将外部的 main_window 传给 view
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setAcceptDrops(True)

        # 纯画布布局
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0) # 去除边缘空白
        layout.addWidget(self.view)
        self.setLayout(layout)

    # ----------------- 【对外暴露的操作方法】 -----------------
    def add_flow_node(self, name, pos):
        """外部调用的添加节点方法"""
        node = NodeItem(name, pos)
        self.view.scene.addItem(node)

        node.positionChanged.connect(self.update_all_edges)  # type:ignore

        if self.flow_nodes:
            prev_node = self.flow_nodes[-1]
            edge = EdgeItem(prev_node.get_output_pos(), node.get_input_pos())
            self.view.scene.addItem(edge)
            self.flow_edges.append(edge)

        self.flow_nodes.append(node)
        QTimer.singleShot(0, self.update_all_edges)
        return node

    def delete_flow_node(self, node_to_delete):
        """外部调用的删除节点方法"""
        if node_to_delete not in self.flow_nodes:
            return

        idx = self.flow_nodes.index(node_to_delete)
        n = len(self.flow_nodes)
        self.view.scene.removeItem(node_to_delete)

        if n == 1:
            self.flow_nodes.clear()
            for e in self.flow_edges:
                self.view.scene.removeItem(e)
            self.flow_edges.clear()
        elif idx == 0:
            self.flow_nodes.pop(0)
            e = self.flow_edges.pop(0)
            self.view.scene.removeItem(e)
        elif idx == n - 1:
            self.flow_nodes.pop()
            e = self.flow_edges.pop()
            self.view.scene.removeItem(e)
        else:
            self.flow_nodes.pop(idx)
            e1 = self.flow_edges.pop(idx - 1)
            e2 = self.flow_edges.pop(idx - 1)
            self.view.scene.removeItem(e1)
            self.view.scene.removeItem(e2)

            prev_node = self.flow_nodes[idx - 1]
            next_node = self.flow_nodes[idx]
            new_edge = EdgeItem(prev_node.get_output_pos(), next_node.get_input_pos())
            self.view.scene.addItem(new_edge)
            self.flow_edges.insert(idx - 1, new_edge)

        self.update_all_edges()

    def update_all_edges(self):
        """手动触发全画面连线刷新"""
        for i, edge in enumerate(self.flow_edges):
            start_node = self.flow_nodes[i]
            end_node = self.flow_nodes[i + 1]
            new_start = start_node.get_output_pos()
            new_end = end_node.get_input_pos()
            edge.update_positions(new_start, new_end)

    def get_flow_nodes(self):
        """获取当前流程图的所有节点列表"""
        return self.flow_nodes

    def clear_all_flow_nodes(self):
        """清空所有方框和连线"""
        for node in self.flow_nodes:
            self.view.scene.removeItem(node)
        for edge in self.flow_edges:
            self.view.scene.removeItem(edge)
        self.flow_nodes.clear()
        self.flow_edges.clear()


# =====================================================================
# 独立测试入口：在这里重建树控件，让测试效果和之前一模一样
# =====================================================================
class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程图测试窗口 (独立测试)")
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

        # 2. 右侧纯净画布 (将自己作为 main_window 传进去，实现双向通信)
        self.canvas = FlowchartCanvas(self, main_window=self)

        # 3. 布局分割
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.canvas)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # 绑定双击信号
        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)

    def add_flow_node(self, name, pos):
        self.canvas.add_flow_node(name, pos)

    def delete_flow_node(self, node_to_delete):
        self.canvas.delete_flow_node(node_to_delete)

    def _on_tree_double_click(self, item, _):
        if item.parent() is None: # 阻止根节点创建方框
            return
        name = item.text(0)
        if self.canvas.flow_nodes:
            last_node = self.canvas.flow_nodes[-1]
            new_x = last_node.pos().x()
            new_y = last_node.pos().y() + 180
        else:
            new_x, new_y = 20, 20
        self.add_flow_node(name, QPointF(new_x, new_y))


def main():
    import sys
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()