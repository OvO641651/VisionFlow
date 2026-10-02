from PySide2.QtWidgets import (QWidget, QListWidgetItem, QListWidget,
                               QApplication, QMainWindow, QVBoxLayout,
                               QListView, QAbstractItemView)
from PySide2.QtCore import Signal, Qt, QSize, QEvent
from PySide2.QtGui import QPixmap, QImage
import cv2
import os
import sys

# 图像预览进度条 QListWidget 控件

class ImageGalleryWidget(QWidget):
    """
    ImageGalleryWidget 类：图像源（图库）管理器。

    功能说明：
        接管外部传入的 QListWidget 控件，将其配置为横向排列的缩略图列表。
        提供 add_image 方法，将 OpenCV 的 BGR 图片转换成无文字的纯净缩略图添加到图库。
        当用户点击某个缩略图时，将触发 image_selected 信号，并把该图片的原图数据传送出去，供主窗口切换大图显示。

    注意：
        本控件已彻底禁用拖拽 / 放置功能（见 eventFilter）。因此只支持"点击缩略图切换大图"，
        拖动缩略图不会有任何反应，更不会复制 / 移动条目。
        图库中的图片只能通过 add_image() 主动添加，例如主窗口的"打开"按钮。
    """

    # 自定义信号：当点击缩略图时，把原图的数据（OpenCV BGR numpy数组）发送出去
    image_selected = Signal(object)

    # 需要拦截并丢弃的拖放类事件（配合 eventFilter 使用）
    # 类属性 _DROP_EVENTS
    # QEvent.DragEnter	拖拽进入事件	鼠标拖着一个东西刚进入控件范围时触发
    # QEvent.DragMove	拖拽移动事件	鼠标拖着东西在控件内移动时持续触发
    # QEvent.DragLeave	拖拽离开事件	鼠标拖着东西离开控件范围时触发
    # QEvent.Drop	放下事件	在控件内松开鼠标（完成放下动作）时触发
    _DROP_EVENTS = (QEvent.DragEnter, QEvent.DragMove,
                    QEvent.DragLeave, QEvent.Drop)

    def __init__(self, list_widget, parent=None):
        """
        初始化图库管理器。
        :param list_widget: 外部传入的 QListWidget 控件实例 (UI 拖放的控件)。
        :param parent: 父级组件；不传时自动挂靠到 list_widget 的父容器。
        """
        if parent is None:
            parent = list_widget.parentWidget()
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

        #    setUniformItemSizes(True) 会强制每一个条目的尺寸严格保持一致。
        self.gallery_list.setUniformItemSizes(True)

        #    FixedHeight: 固定图库控件自身的高度为 85 像素，防止它撑破主布局。
        #    缩略图高度为 60，加上上下内边距，85 像素刚好能紧密包裹住图片，去除了下方多余的方形空白区域。
        self.gallery_list.setFixedHeight(85)

        # 彻底关闭图库控件的拖拽 / 放置功能
        # 现象：图片导入图库后，只要在控件里拖一下（把缩略图拖动，或把外部文件 /
        #       左侧树里的条目拖进来），图库中就会自动多出一张一模一样的图片。
        # 原因：QListWidget 继承自 QAbstractItemView，它本身就是拖放目标。其默认
        #       defaultDropAction 是 Qt.CopyAction，一旦拖放发生，Qt 就会以"复制"
        #       的方式新增一个条目；而条目里的图标和 UserRole 中保存的原图会被一并
        #       复制，所以看上去就是凭空多了一张相同的图片。
        # 处理：1、把相关属性显式关掉，用代码覆盖 .ui 里可能存在的设置；
        #      2、再挂事件过滤器把拖放事件直接吞掉（见 eventFilter），双保险，这样无论拖放来自哪里，都不可能再往图库里添加条目。
        self.gallery_list.setDragEnabled(False)                            # 禁止从本控件把条目拖出去
        self.gallery_list.setAcceptDrops(False)                            # 禁止接受任何拖入
        self.gallery_list.setDropIndicatorShown(False)                     # 不显示放置指示线
        self.gallery_list.setDragDropMode(QAbstractItemView.NoDragDrop)    # 直接关闭拖放模式
        self.gallery_list.setDefaultDropAction(Qt.IgnoreAction)            # 默认拖放动作改成"忽略"
        self.gallery_list.setMovement(QListView.Static)                    # 条目位置固定，不允许拖动

        # 拖放事件实际是发给 viewport 的，所以控件本体和 viewport 都要装事件过滤器
        self.gallery_list.installEventFilter(self)
        self.gallery_list.viewport().installEventFilter(self)

        # 绑定列表内部点击信号槽到自定义的处理函数
        self.gallery_list.itemClicked.connect(self._on_item_clicked)

    def eventFilter(self, watched, event):
        """
        事件过滤器：把落在图库控件上的拖放事件全部拦截并丢弃。

        :param watched: 事件发生的对象（图库控件本身，或它的 viewport）。
        :param event: Qt 传过来的事件对象。
        :return: True 表示事件已处理完毕，不再向下传递；其它事件交回基类默认处理。
        """
        if event.type() in self._DROP_EVENTS:
            event.ignore()  # 明确拒绝这次拖放
            return True     # 不再交给 QListWidget 处理，条目不会被复制 / 新增

        # 非拖放事件交回 QWidget 的默认实现，避免影响点击、绘制、滚动等正常功能
        return super().eventFilter(watched, event)

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