from PySide2.QtCore import Qt, QPointF, Signal, QObject, QTimer
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem
)

'''
修改了方框移动后，曲线没有跟着移动，还是在原来的位置的问题
'''

class NodeItem(QObject, QGraphicsRectItem):
    """流程图节点"""

    positionChanged = Signal()# 自定义信号，解决线没有跟着方框一起动的问题

    def __init__(self, name, pos):
        """
        :param name: 节点名字
        :param pos: 位置
        """
        # 多重继承，继承QObject,QGraphicsRectItem，分别初始化
        QObject.__init__(self)
        QGraphicsRectItem.__init__(self, 0, 0, 140, 50) # 创建一个方块 (x,y,length,wide),(x,y)为左上角点的坐标
        self.name = name
        self.setPos(pos)
        self.setBrush(QBrush(QColor(250, 250, 250))) # QBrush画刷，方块的内颜色(r,g,b),QBrush为填充颜色
        self.setPen(QPen(QColor("darkblue"), 2)) # QPen画笔，方块边框样式，参数为(颜色,线框宽度)

        # 设置标志位，可以与外界交互
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)# 允许用户用鼠标拖拽这个节点 | 允许节点被鼠标点击选中
        # 方框的尺寸为(140, 50)
        self.in_port = QPointF(0, 25)  # 输入端口（左侧）
        self.out_port = QPointF(140, 25)  # 输出端口（右侧）

    def mouseMoveEvent(self, event):
        """实时拖拽响应"""
        super().mouseMoveEvent(event)  # 先让底层把方块真正拖拽过去
        # 立即通知外界位置变了
        self.positionChanged.emit()  # type:ignore

    def mouseReleaseEvent(self, event):
        """鼠标松开"""
        super().mouseReleaseEvent(event)  # 鼠标松开时更新最后一次位置
        self.positionChanged.emit() # type:ignore

    def paint(self, painter, option: QStyleOptionGraphicsItem, widget=None):
        """
        描述节点的样子，如输入输出节点的颜色
        :param painter:画家
        :param option:风格选择
        :param widget:装饰物
        :return:
        """
        super().paint(painter, option, widget) # 将init定义的输入输出位置和方块背景颜色等初始化
        painter.drawText(super().rect(), Qt.AlignCenter, self.name) # (rect:(length,width),居中对齐,名字(直线，圆，或者其他))

        # 绘制输入端口（红点）
        painter.setBrush(Qt.red) # setBrush填充颜色
        painter.drawEllipse(self.in_port, 4, 4) # 绘制圆形(椭圆)，圆心为in_port，(宽,高)为(4,4)

        # 绘制输出端口（蓝点）
        painter.setBrush(Qt.blue) # setBrush填充颜色
        painter.drawEllipse(self.out_port, 4, 4) # 绘制圆形(椭圆)，圆心为out_port，(宽,高)为(4,4)


    def get_input_pos(self):
        """
        mapToScene：将节点自身的“本地坐标”，转换为整个流程图画布的“全局场景坐标”。
        即把方框，输入/输出圆点合并成一个控件，一起移动
        返回起点start位置
        """
        return self.mapToScene(self.in_port)

    def get_output_pos(self):
        return self.mapToScene(self.out_port) # 返回终点end位置


class EdgeItem(QGraphicsPathItem):
    """连线（贝塞尔曲线）：S型平滑曲线"""
    def __init__(self, start, end):
        super().__init__()
        self.start = start
        self.end = end
        self.update_path() # 设置可更新的路径
        self.setPen(QPen(QColor("darkGray"), 2)) # 设置画笔，即设置颜色，厚度为2

    def update_path(self):
        """生成可更新路径"""
        path = QPainterPath() # 创建一个画布
        path.moveTo(self.start) # 移动到起点start
        '''生成路径点，三次贝塞尔曲线：需要两个点ctrl1，ctrl2'''
        dx = abs(self.end.x() - self.start.x()) * 0.5
        ctrl1 = QPointF(self.start.x() + dx, self.start.y())
        ctrl2 = QPointF(self.end.x() - dx, self.end.y())

        path.cubicTo(ctrl1, ctrl2, self.end) # 从起点出发，经过控制点1 和 控制点2，最终平滑地连接到终点end
        self.setPath(path) # 设置在对象画布上

    def update_positions(self, start, end):
        """生成可更新位置"""
        self.start = start
        self.end = end
        self.update_path()



# ---------- 用于独立测试的窗口类 ----------
class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("流程图测试窗口")
        self.resize(800, 500)

        # 创建图形场景（画布）
        self.scene = QGraphicsScene()
        # 创建一个图形视图（显示画布的窗口），并将场景设置进去
        self.view = QGraphicsView(self.scene)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate) # 每次刷新时全屏更新，防止有拖尾残影
        self.setCentralWidget(self.view)
        # 创建两个方框
        self.node1 = NodeItem('直线', QPointF(10, 10))
        self.node2 = NodeItem('圆线', QPointF(100, 100))
        self.scene.addItem(self.node1)  # 将节点添加到场景中
        self.scene.addItem(self.node2)  # 将节点添加到场景中

        '''
        # 创建贝塞尔曲线连接两个方框，node1的终点连接node2的起点
        # 直接创建会导致方框移动的时候线在原来的地方部分，变成一个固定的直线
        # 将创建曲线封装成update_edge()函数，移动方框时会自动刷新曲线的位置
        node_end = self.node1.get_output_pos()
        node_start = self.node2.get_input_pos()
        edge = EdgeItem(node_start,node_end)
        self.scene.addItem(edge)
        '''

        # 创建连线
        self.edge = EdgeItem(QPointF(0, 0), QPointF(0, 0)) # 创建曲线，起点(0,0)，终点(0,0)
        self.scene.addItem(self.edge) # 将曲线绘制到画布中

        # 绑定更新函数，信号槽绑定
        self.node1.positionChanged.connect(self.update_edge) # type:ignore
        self.node2.positionChanged.connect(self.update_edge) # type:ignore

        # 保证程序刚打开时连线能立刻对齐
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