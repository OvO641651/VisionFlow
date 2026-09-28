from PySide2.QtCore import Qt, QPointF
from PySide2.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide2.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QSplitter, QGraphicsRectItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QStyleOptionGraphicsItem
)

'''
完成NodeItem节点类的编写和测试
'''

class NodeItem(QGraphicsRectItem):
    """流程图节点"""
    def __init__(self, name, pos):
        """
        :param name: 节点名字
        :param pos: 位置
        """
        super().__init__(0, 0, 140, 50) # 创建一个方块 (x,y,length,wide),(x,y)为左上角点的坐标
        self.name = name
        self.setPos(pos)
        self.setBrush(QBrush(QColor(220, 230, 250))) # QBrush画刷，方块的内颜色(r,g,b),QBrush为填充颜色
        self.setPen(QPen(QColor("darkblue"), 2)) # Qpen画笔，方块边框样式，参数为(颜色,线框宽度)

        # 设置标志位，可以与外界交互
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)# 允许用户用鼠标拖拽这个节点 | 允许节点被鼠标点击选中
        self.in_port = QPointF(0, 25)  # 输入端口（左侧）
        self.out_port = QPointF(140, 25)  # 输出端口（右侧）

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
        '''
        mapToScene：将节点自身的“本地坐标”，转换为整个流程图画布的“全局场景坐标”。
        即把方框，输入/输出圆点合并成一个控件，一起移动
        '''
        return self.mapToScene(self.in_port)

    def get_output_pos(self):
        return self.mapToScene(self.out_port)



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

        node = NodeItem('直线', QPointF(10, 10))
        self.scene.addItem(node)  # 将节点添加到场景中


def main():
    import sys
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()