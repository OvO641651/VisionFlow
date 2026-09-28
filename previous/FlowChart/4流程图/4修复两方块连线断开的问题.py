from PySide2.QtCore import Qt, QPointF, Signal, QObject, QTimer
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem
)

'''
修复两方框连线断开的问题
'''

class NodeItem(QObject, QGraphicsRectItem):
    """流程图节点"""
    positionChanged = Signal()

    def __init__(self, name, pos):
        # 多重基础，分别初始化
        QObject.__init__(self)
        QGraphicsRectItem.__init__(self, 0, 0, 140, 50)

        self.name = name
        self.setPos(pos)
        self.setBrush(QBrush(QColor(250, 250, 250)))
        self.setPen(QPen(QColor("darkblue"), 2))

        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.in_port = QPointF(0, 25)  # 左侧中心
        self.out_port = QPointF(140, 25)  # 右侧中心

    # 【核心修复1】：不使用 itemChange，改用鼠标事件，确保拖拽时信号必定发出！
    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)  # 先让底层把方块真正拖拽过去
        self.positionChanged.emit()  # 立即通知外界位置变了

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)  # 鼠标松开时更新最后一次位置
        self.positionChanged.emit()

    def paint(self, painter, option: QStyleOptionGraphicsItem, widget=None):
        super().paint(painter, option, widget)
        painter.drawText(super().rect(), Qt.AlignCenter, self.name)

        painter.setBrush(Qt.red)
        painter.drawEllipse(self.in_port, 4, 4)

        painter.setBrush(Qt.blue)
        painter.drawEllipse(self.out_port, 4, 4)

    # 【核心修复2】：端口坐标映射
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


# ---------- 测试窗口 ----------
class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程图测试窗口")
        self.resize(800, 500)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setCentralWidget(self.view)

        # 1. 创建节点
        self.node1 = NodeItem('直线', QPointF(10, 10))
        self.node2 = NodeItem('圆线', QPointF(100, 100))
        self.scene.addItem(self.node1)
        self.scene.addItem(self.node2)

        # 2. 创建连线（占位）
        self.edge = EdgeItem(QPointF(0, 0), QPointF(0, 0))
        self.scene.addItem(self.edge)

        # 3. 绑定更新函数
        self.node1.positionChanged.connect(self.update_edge)
        self.node2.positionChanged.connect(self.update_edge)

        # 4. 【核心修复3】：保证程序刚打开时连线能立刻对齐
        QTimer.singleShot(0, self.update_edge)

    # 连线的更新槽函数
    def update_edge(self):
        # 实时获取两个方框最新的端口位置
        new_start = self.node1.get_output_pos()
        new_end = self.node2.get_input_pos()
        # 让连线更新过去
        self.edge.update_positions(new_start, new_end)


def main():
    import sys
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()