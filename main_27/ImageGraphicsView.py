from PySide2.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide2.QtCore import Qt
from PySide2.QtGui import QPainter, QPixmap, QImage
import numpy as np
import cv2

# 使用 GraphicsView控件代替原本的QLabel控件

# ===== 自定义图像视图类（替代 QLabel） =====
class ImageGraphicsView(QGraphicsView):
    """
    专门用于显示图像并可缩放/平移的自定义视图。
    功能特点：
        支持鼠标滚轮缩放（以鼠标位置为中心）
        支持鼠标左键按住拖拽平移
        使用硬件加速渲染，缩放平移丝滑无卡顿
        隐藏滚动条，保持界面整洁
    """

    def __init__(self, parent=None):
        """初始化视图场景和交互参数"""
        super().__init__(parent)
        # 创建图形场景（画布），所有图元（图像、线条、矩形等）都放在这里
        self.setScene(QGraphicsScene(self))
        # 用来存放当前显示的图像图元（QGraphicsPixmapItem）
        self.pixmap_item = None
        # 启用抗锯齿和图像平滑缩放（避免缩放时出现锯齿或马赛克）
        self.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )

        # 设置鼠标左键拖拽模式为"平移画面"（ScrollHandDrag），这样按住左键拖动时，视图会随之移动，实现平移效果。
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        # 设置视口更新模式为"全视口更新"，防止拖拽时产生残影
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

        # 隐藏水平/垂直滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def set_image(self, cv_img):
        """
        设置并显示一幅 OpenCV 格式的图像（BGR 格式）,将 OpenCV 图像转换并渲染到 UI 的 videoLabel 上
        OpenCV BGR -> RGB : qt和opencv使用的颜色通道顺序不同，所以需要转换
        :param cv_img: numpy 数组，OpenCV 读取的 BGR 图像
        """
        if cv_img is None:
            return

        # 颜色空间转换
        # OpenCV 读取的图像是 BGR 格式，而 Qt 显示需要 RGB 格式，所以必须转换。
        rgb_frame = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        # 获取图像高度、宽度、通道数
        h, w, ch = rgb_frame.shape
        # 确保数组内存连续
        rgb_frame = np.ascontiguousarray(rgb_frame)
        # 将 numpy 数组转换为 QImage
        # 参数：数据指针，宽度，高度，每行字节数（width * channels），图像格式
        qt_img = QImage(rgb_frame.data, w, h, w * ch, QImage.Format_RGB888) # type:ignore
        # 将 QImage 转换为 QPixmap
        pixmap = QPixmap.fromImage(qt_img)

        # 更新场景中的图像图元
        if self.pixmap_item is None:
            # 如果还没有图像图元，则创建一个并添加到场景中
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene().addItem(self.pixmap_item)
        else:
            # 如果已经存在，直接更新它的 pixmap
            self.pixmap_item.setPixmap(pixmap)

        # 设置场景的矩形边界与图像尺寸一致（使视图能正确居中显示）
        self.setSceneRect(0, 0, w, h)

    def wheelEvent(self, event):
        """重写滚轮事件，实现以鼠标位置为中心的缩放"""
        # 判断滚轮滚动方向：向上滚动（角度增量为正）放大，向下滚动缩小
        if event.angleDelta().y() > 0:
            factor = 1.1   # 放大系数 1.1 倍
        else:
            factor = 1.0 / 1.1   # 缩小系数 1/1.1 倍

        # 获取鼠标当前在场景坐标系中的位置（作为缩放中心）
        mouse_pos = self.mapToScene(event.pos())

        # 执行缩放（以视图中心为基准缩放，但需要保持鼠标位置不变）
        self.scale(factor, factor)

        # 缩放后，鼠标指向的场景坐标会发生变化，需要平移视图来补偿，
        # 让鼠标指向的位置依然停留在原来的像素位置。
        new_mouse_pos = self.mapToScene(event.pos())
        delta = new_mouse_pos - mouse_pos
        self.translate(delta.x(), delta.y())




# 独立测试入口
if __name__ == '__main__':
    import sys
    from PySide2.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

    # 创建 Qt 应用
    app = QApplication(sys.argv)

    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("ImageGraphicsView 测试窗口")
    window.resize(800, 600)

    # 创建中心控件，并放入布局
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(0, 0, 0, 0)

    # 实例化我们的自定义图像视图
    view = ImageGraphicsView()
    layout.addWidget(view)

    # 加载测试图片（如果找不到图片，生成一张黑图）
    test_img_path = 'image/lena.png'
    img = cv2.imread(test_img_path)
    if img is None:
        # 如果没有图片，生成一个 512x512 的彩色渐变图用于测试
        print(f"未找到 {test_img_path}，使用生成的测试图像。")
        img = np.zeros((512, 512, 3), dtype=np.uint8)
        # 绘制一个简单的渐变
        for i in range(512):
            img[i, :, 0] = i // 2  # 蓝色通道渐变
            img[i, :, 1] = 128     # 绿色通道固定
            img[:, i, 2] = i // 2  # 红色通道渐变

    # 将图像显示到视图中
    view.set_image(img)

    # 设置中央控件并显示
    window.setCentralWidget(central_widget)
    window.show()

    # 进入事件循环
    sys.exit(app.exec_())
