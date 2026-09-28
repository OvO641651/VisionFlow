from PySide2.QtCore import Qt, QPointF, Signal, QObject, QTimer
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem, QMenu, QAction
)

'''
点到方框里面的蓝点才能拖出灰色虚线，点到方框外面的蓝点不会拖出灰色虚线
'''

class NodeItem(QObject, QGraphicsRectItem):
    """流程图节点"""
    positionChanged = Signal()  # 节点位置改变信号

    def __init__(self, name, pos):
        QObject.__init__(self)
        QGraphicsRectItem.__init__(self, 0, 0, 140, 50)
        self.name = name
        self.setPos(pos)
        self.setBrush(QBrush(QColor(250, 250, 250)))
        self.setPen(QPen(QColor("darkblue"), 2))

        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self.in_port = QPointF(70, 0)  # 输入端口（上侧）
        self.out_port = QPointF(70, 50)  # 输出端口（下侧）

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

        # 绘制端口红蓝点
        painter.setBrush(Qt.red)
        painter.drawEllipse(self.in_port, 6, 6)

        painter.setBrush(Qt.blue)
        painter.drawEllipse(self.out_port, 6, 6)

    def get_input_pos(self):
        return self.mapToScene(self.in_port)

    def get_output_pos(self):
        return self.mapToScene(self.out_port)


class EdgeItem(QGraphicsPathItem):
    """连线（贝塞尔曲线）"""

    def __init__(self, start_node, end_node):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        self.update_path()
        self.setPen(QPen(QColor("darkGray"), 2))

    def update_path(self):
        start = self.start_node.get_output_pos()
        end = self.end_node.get_input_pos()
        path = QPainterPath()
        path.moveTo(start)
        dx = abs(end.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + dx, start.y())
        ctrl2 = QPointF(end.x() - dx, end.y())
        path.cubicTo(ctrl1, ctrl2, end)
        self.setPath(path)

    def update_positions(self):
        self.update_path()


class FlowchartView(QGraphicsView):
    """自定义流程图视图（支持拖放 和 手动连线）"""

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self._start_node = None
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

    # ================= 重新优化后的鼠标事件处理 =================

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if isinstance(item, NodeItem):
                # 【关键优化1】：暂时禁用平移模式，防止抢事件
                current_drag = self.dragMode()
                self.setDragMode(QGraphicsView.NoDrag)

                scene_pos = self.mapToScene(event.pos())
                local_pos = item.mapFromScene(scene_pos)

                # 【关键优化2】：点击判定距离放大到 30，极度宽容
                # 1. 判定蓝点（输出端口）
                if (local_pos - item.out_port).manhattanLength() < 20:
                    self._start_connection(item)
                    event.accept()
                    return

                # 2. 判定红点（输入端口）
                if (local_pos - item.in_port).manhattanLength() < 30:
                    if self._start_node is not None:
                        self._try_finish_edge(self._start_node, item, event)
                        self.setDragMode(current_drag)
                        return

                # 3. 点击了方框空白处（交由底层处理节点的选中或拖拽移动）
                super().mousePressEvent(event)
                self.setDragMode(current_drag)
                return

            # 如果正在连线，点击空白处取消连线
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
            # 获取鼠标当前位置下方所有的图元（忽略被虚线遮挡的情况）
            overlapping_items = self.scene.items(scene_pos)
            for item in overlapping_items:
                if isinstance(item, NodeItem):
                    target_node = item
                    break

            if target_node is not None:
                local_pos = target_node.mapFromScene(scene_pos)
                if (local_pos - target_node.in_port).manhattanLength() < 30:
                    self._try_finish_edge(self._start_node, target_node, event)
                    self.setDragMode(QGraphicsView.ScrollHandDrag)  # 恢复抓取平移模式
                    return

            self._cancel_connection()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    # ================= 连线辅助函数 =================

    def _start_connection(self, node):
        self._cancel_connection()
        self._start_node = node
        start_pos = node.get_output_pos()
        self._temp_line = self.scene.addLine(
            start_pos.x(), start_pos.y(),
            start_pos.x(), start_pos.y(),
            QPen(Qt.gray, 2, Qt.DashLine)
        )

    def _try_finish_edge(self, start_node, end_node, event=None):
        if start_node is not None and start_node != end_node:
            self.main_window.add_edge(start_node, end_node)
        self._cancel_connection()
        if event:
            event.accept()

    def _cancel_connection(self):
        if self._temp_line:
            self.scene.removeItem(self._temp_line)
            self._temp_line = None
        self._start_node = None
        # 恢复到正常的抓图平移模式
        self.setDragMode(QGraphicsView.ScrollHandDrag)


# ---------- 用于独立测试的窗口类 ----------
class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程图测试窗口 (手感大提升版)")
        self.resize(800, 500)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("检测模块")
        self.tree.setDragEnabled(True)
        self.tree.setDefaultDropAction(Qt.CopyAction)
        root = QTreeWidgetItem(self.tree, ["图像处理"])
        QTreeWidgetItem(root, ["直线"])
        QTreeWidgetItem(root, ["圆"])
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

    def add_edge(self, start_node, end_node):
        for edge in self.flow_edges:
            if edge.start_node == start_node and edge.end_node == end_node:
                return
        edge = EdgeItem(start_node, end_node)
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


def main():
    import sys
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()