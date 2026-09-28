from PySide2.QtWidgets import (QWidget, QListWidgetItem, QListWidget,
                               QApplication, QMainWindow, QVBoxLayout)
from PySide2.QtCore import Signal, Qt, QSize
from PySide2.QtGui import QPixmap, QImage
import cv2
import os
import sys


class ImageGalleryWidget(QWidget):
    """
    ImageGalleryWidget 类：图像源（图库）管理器。

    功能说明：
        接管外部传入的 QListWidget 控件，将其配置为横向排列的缩略图列表。
        提供 add_image 方法，将 OpenCV 的 BGR 图片转换成无文字的纯净缩略图添加到图库。
        当用户点击某个缩略图时，将触发 image_selected 信号，并把该图片的原图数据传送出去，供主窗口切换大图显示。
    """

    # 自定义信号：当点击缩略图时，把原图的数据（OpenCV BGR numpy数组）发送出去
    image_selected = Signal(object)

    def __init__(self, list_widget, parent=None):
        """
        初始化图库管理器。
        :param list_widget: 外部传入的 QListWidget 控件实例 (UI 拖放的控件)。
        :param parent: 父级组件。
        """
        super().__init__(parent)

        # 接管外部传入的 QListWidget 控件（此处不创建新控件，仅接管）
        self.gallery_list = list_widget

        # 在代码中重新配置 QListWidget 的显示属性。
        # 这些配置在qt设计师里面已经设置，但是这里代码设置会覆盖 Qt Designer 的 UI 设置，确保在不同的运行环境下行为统一。
        #    Flow: 设置为从左到右横向排列。
        self.gallery_list.setFlow(QListWidget.LeftToRight)
        #    ViewMode: 设置为图标模式，以支持显示大图标。
        self.gallery_list.setViewMode(QListWidget.IconMode)
        #    ResizeMode: 设置为自动调整，当窗口缩放时列表项会自动适应布局。
        self.gallery_list.setResizeMode(QListWidget.Adjust)
        #    Spacing: 设置缩略图之间的水平间距为 8 像素。
        self.gallery_list.setSpacing(8)
        #    IconSize: 强行指定图标显示的尺寸为 80x70 像素。
        self.gallery_list.setIconSize(QSize(80, 70))
        #    FixedHeight: 固定图库控件自身的高度为 110 像素，防止它撑破主布局。
        self.gallery_list.setFixedHeight(110)

        #    setUniformItemSizes(True) 会强制每一个条目的尺寸严格保持一致。
        self.gallery_list.setUniformItemSizes(True)

        #    缩略图高度为 60，加上上下内边距，85 像素刚好能紧密包裹住图片。去除了下方多余的方形空白区域。
        self.gallery_list.setFixedHeight(85)

        # 绑定列表内部点击信号槽到自定义的处理函数
        self.gallery_list.itemClicked.connect(self._on_item_clicked)


    def add_image(self, cv_img):
        """
        将一张 OpenCV 格式的图片添加到图库列表。

        :param cv_img: OpenCV 读取的 BGR 格式图像数据 (numpy 数组)。
        """
        # 图像格式转换：BGR -> RGB，并转换为 Qt 能够识别的 QPixmap。
        rgb_frame = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        # 使用零拷贝方式创建 QImage
        qt_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888) # type:ignore
        # 将原始图片按比例缩小至 80x60 像素，作为缩略图显示。
        pixmap = QPixmap.fromImage(qt_img).scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # 创建一个空白的列表项，并设置图标。
        # QListWidgetItem 不能直接传 pixmap，必须使用 setIcon 方法
        item = QListWidgetItem()
        # 将刚才生成的 QPixmap 设为该条目的图标
        item.setIcon(pixmap)

        # 将原始的大图数据存到条目中。
        item.setData(Qt.UserRole, cv_img)

        # 将配置好的条目添加到 QListWidget 中
        self.gallery_list.addItem(item)


    def _on_item_clicked(self, item):
        """
        内部槽函数：处理列表项的点击事件，并发射信号。
        :param item: 被点击的 QListWidgetItem 对象。
        """
        # 从点击的条目中取出之前绑定的原图数据
        img_bgr = item.data(Qt.UserRole)
        if img_bgr is not None:
            # 触发自定义信号，把原图数据传给主窗口
            self.image_selected.emit(img_bgr) # type:ignore



# 独立测试代码
# 功能描述: 用于不启动主程序，单独测试该图库控件的图片加载、布局和点击交互功能。
if __name__ == '__main__':
    # 创建独立测试用的 Qt 应用
    app = QApplication(sys.argv)

    # 创建模拟主窗口，设置窗口标题和尺寸
    window = QMainWindow()
    window.setWindowTitle("ImageGalleryWidget 独立测试")
    window.resize(800, 200)

    # 模拟主 UI 的布局（放一个普通的 QListWidget 进去）
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(10, 10, 10, 10)

    test_list = QListWidget()
    layout.addWidget(test_list)

    window.setCentralWidget(central_widget)

    # 实例化我们的逻辑类（传入 test_list 作为控件引用）
    gallery_widget = ImageGalleryWidget(test_list)

    # 遍历 image 文件夹并添加所有图片，用来在 GalleryWidget 控件中展示
    image_folder = "image"
    if os.path.exists(image_folder):
        files = os.listdir(image_folder)
        # 按照文件名排序，看起来更整齐
        files.sort()

        loaded_count = 0
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                path = os.path.join(image_folder, f)
                img = cv2.imread(path)
                if img is not None:
                    gallery_widget.add_image(img)
                    loaded_count += 1
                else:
                    print(f"警告：无法读取图片文件 {f}")

        print(f"测试完成，成功加载了 {loaded_count} 张图片。")
    else:
        print(f"警告：当前目录下没有找到名为 '{image_folder}' 的文件夹，请确保程序运行目录下存在 image 文件夹。")

    # 显示窗口并进入事件循环
    window.show()
    sys.exit(app.exec_())