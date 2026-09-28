from PySide2.QtCore import Qt, QPointF, Signal, QObject, QTimer
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem, QMenu, QAction
)


class NodeItem(QObject, QGraphicsRectItem):
    """流程图节点（支持双输出端口）"""
    positionChanged = Signal()

    def __init__(self, name, pos):
        QObject.__init__(self)
        QGraphicsRectItem.__init__(self, 0, 0, 140, 50)
        self.name = name
        self.setPos(pos)
        self.setBrush(QBrush(QColor(250, 250, 250)))
        self.setPen(QPen(QColor("darkblue"), 2))

        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self.in_port = QPointF(70, 0)  # 输入端口（上侧红点）
        self.out_port_0 = QPointF(20, 50)  # 输出端口 0（下侧左蓝点）
        self.out_port_1 = QPointF(120, 50)  # 输出端口 1（下侧右蓝点）

        # 将端口放入列表，方便索引遍历
        self.out_ports = [self.out_port_0, self.out_port_1]

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.positionChanged.emit()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.positionChanged.emit()

    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_action = QAction("删除节点", menu)
        menu.addAction(delete_action)
        action = menu.exec_(event.screenPos())
        if action == delete_action:
            if self.scene() and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view, 'main_window'):
                    view.main_window.delete_flow_node(self)

    def paint(self, painter, option: QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, option, widget)
        painter.drawText(super().rect(), Qt.AlignCenter, self.name)

        # 绘制输入端口（红点）
        painter.setBrush(Qt.red)
        painter.drawEllipse(self.in_port, 6, 6)

        # 绘制输出端口 0（左侧蓝点）
        painter.setBrush(Qt.blue)
        painter.drawEllipse(self.out_port_0, 6, 6)

        # 绘制输出端口 1（右侧蓝点）
        painter.setBrush(Qt.blue)
        painter.drawEllipse(self.out_port_1, 6, 6)

    def get_input_pos(self):
        return self.mapToScene(self.in_port)

    def get_output_pos(self, port_index=0):
        """根据端口索引返回对应的输出端口坐标"""
        if port_index >= len(self.out_ports):
            port_index = 0
        return self.mapToScene(self.out_ports[port_index])


class EdgeItem(QGraphicsPathItem):
    """连线（带端口索引）"""

    def __init__(self, start_node, end_node, from_port_index=0):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.from_port_index = from_port_index  # 记录从哪个端口引出（0或1）
        self.update_path()
        self.setPen(QPen(QColor("darkGray"), 2))

    def update_path(self):
        # 根据存储的端口索引获取准确的起点坐标
        start = self.start_node.get_output_pos(self.from_port_index)
        end = self.end_node.get_input_pos()

        path = QPainterPath()
        path.moveTo(start)
        dy = abs(end.y() - start.y())
        ctrl1 = QPointF(start.x(), start.y() + dy * 0.5)
        ctrl2 = QPointF(end.x(), end.y() - dy * 0.5)
        path.cubicTo(ctrl1, ctrl2, end)
        self.setPath(path)

    def update_positions(self):
        self.update_path()

    # ============= 【修复：添加连线的右键删除菜单】 =============
    def contextMenuEvent(self, event):
        """右键点击连线时弹出菜单，实现删除连线"""
        menu = QMenu()
        delete_action = QAction("删除连线", menu)
        menu.addAction(delete_action)

        action = menu.exec_(event.screenPos())

        if action == delete_action:
            if self.scene() and self.scene().views():
                view = self.scene().views()[0]
                if hasattr(view, 'main_window'):
                    view.main_window.delete_edge(self)
    # ===========================================================


class FlowchartView(QGraphicsView):
    """自定义流程图视图（支持多端口拖拽）"""

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self._start_node = None
        self._start_port_index = 0
        self._temp_line = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() or isinstance(event.source(), QTreeWidget):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        text = ""
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

    # ================= 多端口鼠标事件 =================

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())

            if hasattr(self.main_window, 'flow_nodes'):
                for node in self.main_window.flow_nodes:
                    if not isinstance(node, NodeItem):
                        continue
                    local_pos = node.mapFromScene(scene_pos)

                    # 1. 检测左蓝点（端口 0）
                    if (local_pos - node.out_port_0).manhattanLength() < 30:
                        self.setDragMode(QGraphicsView.NoDrag)
                        self._start_connection(node, 0)
                        event.accept()
                        return
                    # 2. 检测右蓝点（端口 1）
                    if (local_pos - node.out_port_1).manhattanLength() < 30:
                        self.setDragMode(QGraphicsView.NoDrag)
                        self._start_connection(node, 1)
                        event.accept()
                        return
                    # 3. 检测红点（输入端口）
                    if (local_pos - node.in_port).manhattanLength() < 30:
                        if self._start_node is not None:
                            self._try_finish_edge(self._start_node, node, self._start_port_index, event)
                            return

            # 点到了方框空白处
            item = self.itemAt(event.pos())
            if isinstance(item, NodeItem):
                super().mousePressEvent(event)
                return

            # 点到了空白背景
            if self._start_node is not None:
                self._cancel_connection()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._start_node is not None:
            pos = self.mapToScene(event.pos())
            line = self._temp_line.line()
            line.setP2(pos)
            self._temp_line.setLine(line)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._start_node is not None:
            scene_pos = self.mapToScene(event.pos())

            target_node = None
            if hasattr(self.main_window, 'flow_nodes'):
                for node in self.main_window.flow_nodes:
                    if not isinstance(node, NodeItem):
                        continue
                    local_pos = node.mapFromScene(scene_pos)
                    if (local_pos - node.in_port).manhattanLength() < 30:
                        target_node = node
                        break

            if target_node is not None:
                self._try_finish_edge(self._start_node, target_node, self._start_port_index, event)
                return

            self._cancel_connection()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    # ================= 连线辅助函数 =================

    def _start_connection(self, node, port_index):
        self._cancel_connection()
        self._start_node = node
        self._start_port_index = port_index
        start_pos = node.get_output_pos(port_index)
        self._temp_line = self.scene.addLine(
            start_pos.x(), start_pos.y(),
            start_pos.x(), start_pos.y(),
            QPen(Qt.gray, 2, Qt.DashLine)
        )

    def _try_finish_edge(self, start_node, end_node, port_index, event=None):
        if start_node is not None and start_node != end_node:
            self.main_window.add_edge(start_node, end_node, port_index)
        self._cancel_connection()
        if event:
            event.accept()

    def _cancel_connection(self):
        if self._temp_line:
            self.scene.removeItem(self._temp_line)
            self._temp_line = None
        self._start_node = None
        self._start_port_index = 0
        self.setDragMode(QGraphicsView.ScrollHandDrag)


# ---------- 独立测试用的 TestWindow ----------
class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程图测试窗口 (多端口路由版)")
        self.resize(800, 500)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("检测模块")
        self.tree.setDragEnabled(True)
        self.tree.setDefaultDropAction(Qt.CopyAction)
        root = QTreeWidgetItem(self.tree, ["图像处理"])
        QTreeWidgetItem(root, ["直线"])
        QTreeWidgetItem(root, ["圆"])
        QTreeWidgetItem(root, ["灰度"])
        QTreeWidgetItem(root, ["条件分支"])  # 测试分支模块
        self.tree.expandAll()

        self.flow_nodes = []
        self.flow_edges = []

        self.view = FlowchartView(main_window=self)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.view.setAcceptDrops(True)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)

    def add_flow_node(self, name, pos):
        node = NodeItem(name, pos)
        self.view.scene.addItem(node)
        node.positionChanged.connect(self.update_all_edges)
        self.flow_nodes.append(node)
        return node

    def add_edge(self, start_node, end_node, from_port_index=0):
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                return
        edge = EdgeItem(start_node, end_node, from_port_index)
        self.view.scene.addItem(edge)
        self.flow_edges.append(edge)
        self.update_all_edges()

    def delete_flow_node(self, node_to_delete):
        if node_to_delete not in self.flow_nodes:
            return
        edges_to_remove = []
        for edge in self.flow_edges:
            if edge.start_node == node_to_delete or edge.end_node == node_to_delete:
                edges_to_remove.append(edge)
        for edge in edges_to_remove:
            self.view.scene.removeItem(edge)
            self.flow_edges.remove(edge)
        self.view.scene.removeItem(node_to_delete)
        self.flow_nodes.remove(node_to_delete)
        self.update_all_edges()

    def update_all_edges(self):
        for edge in self.flow_edges:
            edge.update_positions()

    def _on_tree_double_click(self, item, column):
        index = self.tree.currentIndex()
        if not index.isValid():
            return
        parent = index.parent()
        if not parent.isValid():
            return
        name = index.data(0)
        if not name:
            return
        if self.flow_nodes:
            last_node = self.flow_nodes[-1]
            new_x = last_node.pos().x()
            new_y = last_node.pos().y() + 180
        else:
            new_x, new_y = 20, 20
        self.add_flow_node(name, QPointF(new_x, new_y))


if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())