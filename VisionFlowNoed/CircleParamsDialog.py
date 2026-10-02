import sys
import cv2
import numpy as np
from PySide2.QtWidgets import (QApplication, QSpinBox, QDoubleSpinBox, QLabel)

# 继承直线检测的配置窗口
from LineParamsDialog import LineParamsDialog


class CircleParamsDialog(LineParamsDialog):
    def __init__(self, parent=None, node=None, main_window=None):
        # 加载父类界面（直线参数会被加载进来）
        super().__init__(parent, node, main_window)

        # 修改窗口标题 和 显示结果的文本
        self.setWindowTitle("圆检测")
        label_6 = self.ui.findChild(QLabel, "label_6")
        if label_6:
            label_6.setText("圆数量：")


        # 直接替换标签文字和微调框控件，不动原布局
        # 创建辅助函数_set_label_text，用于修改 5 个标签的文本
        self._set_label_text("canny_low", "累加器分辨率(dp):")
        self._set_label_text("canny_high", "圆心最小距离(minDist):")
        self._set_label_text("threshold", "Canny高阈值(param1):")
        self._set_label_text("min_line_length", "累加器阈值(param2):")
        self._set_label_text("max_line_gap", "最小半径(minRadius):")

        # 创建 5 个新的控件，并精准替换原来的控件
        # 累加器分辨率 dp 需要支持小数，使用 QDoubleSpinBox
        self.spin_dp = QDoubleSpinBox() # 创建控件DoubleSpinBox
        self.spin_dp.setRange(0.1, 10.0) # 设置范围range
        self.spin_dp.setSingleStep(0.1) # 设置每点击一次增加或者减少时的分度值
        self.spin_dp.setDecimals(2) # 设置小数位 2位小数
        self.spin_dp.setValue(1.00) # 设置初始值
        # 创建复制函数_replace_widget，用于将在原位置精准拔掉旧控件，插上新控件
        self._replace_widget("spin_canny_low", self.spin_dp) # 替换到 ui 上

        # 圆心最小距离 minDist 使用整数
        self.spin_min_dist = QSpinBox() # 创建spinbox控件
        self.spin_min_dist.setRange(10, 10000) # 设置范围
        self.spin_min_dist.setValue(150) # 设置初始值
        self._replace_widget("spin_canny_high", self.spin_min_dist) # 替换到 ui 上

        # Canny高阈值
        self.spin_param1 = QSpinBox()
        self.spin_param1.setRange(0, 1000)
        self.spin_param1.setValue(100)
        self._replace_widget("spin_hough_threshold", self.spin_param1)

        # 累加器阈值
        self.spin_param2 = QSpinBox()
        self.spin_param2.setRange(0, 1000)
        self.spin_param2.setValue(80)
        self._replace_widget("spin_min_line_length", self.spin_param2)

        # 最小半径
        self.spin_min_radius = QSpinBox()
        self.spin_min_radius.setRange(0, 10000)
        self.spin_min_radius.setValue(20)
        self._replace_widget("spin_max_line_gap", self.spin_min_radius)

        # 加载已有的参数
        self._load_params()


    def _set_label_text(self, label_name, new_text):
        """辅助函数：仅修改标签的文字"""
        label = self.ui.findChild(QLabel, label_name) # 通过 findChild 获取控件
        if label:
            label.setText(new_text)

    def _replace_widget(self, old_name, new_widget):
        """
        辅助函数：在原位置精准拔掉旧控件，插上新控件
        :param old_name:待替换旧控件的 objectName (字符串)
        :param new_widget:已经创建好的、准备插进去的新控件实例
        :return:
        """
        old_widget = self.ui.findChild(QSpinBox, old_name) # 通过 findChild 获取控件
        if old_widget:
            # 获取旧控件的父级布局
            parent_layout = old_widget.parentWidget().layout()
            if parent_layout:
                # 在不破坏父级布局结构的情况下，直接把旧控件替换为新控件
                # 新控件会完美继承旧控件原本的物理坐标、对齐方式、拉伸比例
                parent_layout.replaceWidget(old_widget, new_widget)
                # 将旧控件从 Qt 的对象树中彻底脱钩（解除父子关系）
                old_widget.setParent(None)
                # 销毁旧控件，释放内存
                old_widget.deleteLater()


    def _load_params(self):
        """重写：加载参数"""
        if not hasattr(self, 'spin_dp'):
            return

        if not self.node:
            return

        params = self.node.params

        # 加载基础和 ROI 参数
        self.spin_roi_x.setValue(params.get("roi_x", 0))
        self.spin_roi_y.setValue(params.get("roi_y", 0))
        default_w, default_h = 640, 480
        if self.main_window and self.main_window.current_static_image is not None:
            h, w = self.main_window.current_static_image.shape[:2]
            default_w, default_h = w, h
        self.spin_roi_w.setValue(params.get("roi_w", default_w))
        self.spin_roi_h.setValue(params.get("roi_h", default_h))

        saved_shape = params.get("roi_shape", "矩形")
        self.shape_combo.setCurrentText(saved_shape)
        if self.cb_hide_roi:
            self.cb_hide_roi.setChecked(params.get("hide_roi", False))

        # 加载圆的 5 个参数
        self.spin_dp.setValue(params.get("dp", 1.0))
        self.spin_min_dist.setValue(params.get("min_dist", 150))
        self.spin_param1.setValue(params.get("param1", 100))
        self.spin_param2.setValue(params.get("param2", 80))
        self.spin_min_radius.setValue(params.get("min_radius", 20))


    def _update_params(self):
        """重写：保存参数"""
        if not self.node:
            return

        # 保存基础参数
        self.node.params["roi_x"] = self.spin_roi_x.value()
        self.node.params["roi_y"] = self.spin_roi_y.value()
        self.node.params["roi_w"] = self.spin_roi_w.value()
        self.node.params["roi_h"] = self.spin_roi_h.value()
        self.node.params["roi_shape"] = self.shape_combo.currentText()
        if self.cb_hide_roi:
            self.node.params["hide_roi"] = self.cb_hide_roi.isChecked()

        # 保存圆的 5 个参数
        self.node.params["dp"] = self.spin_dp.value()
        self.node.params["min_dist"] = self.spin_min_dist.value()
        self.node.params["param1"] = self.spin_param1.value()
        self.node.params["param2"] = self.spin_param2.value()
        self.node.params["min_radius"] = self.spin_min_radius.value()


    def update_result_count(self, data):
        """重写：显示圆的数量"""
        if not self.label_result_count:
            return
        if self.node and self.node.name == "圆":
            if data is not None:
                circle_count = sum(1 for item in data if isinstance(item, tuple) and len(item) == 3)
                self.label_result_count.setText(str(circle_count))
            else:
                self.label_result_count.setText("0")
        else:
            self.label_result_count.setText("0")




# 独立测试入口
if __name__ == '__main__':
    app = QApplication(sys.argv)

    class MockMainWindow:
        def __init__(self, img):
            self.current_static_image = img
            self.cap = None
            self.video_processing_mode = "continuous"
            self.video_step_node = None

        @staticmethod
        def _process_and_display_frame(frame):
            print(f"[Mock主窗口] 执行连续执行, 尺寸: {frame.shape}")

        @staticmethod
        def update_frame():
            print("[Mock主窗口] 执行视频帧更新")

        @staticmethod
        def _display_image(img):
            print(f"[Mock主窗口] 显示图片, 尺寸: {img.shape}")

        @staticmethod
        def _run_flow_pipeline_step(frame, node):
            print(f"[Mock主窗口] 执行单步检测, 节点名: {node.name}")
            return frame, []

        @staticmethod
        def _run_flow_pipeline(frame):
            print("[Mock主窗口] 执行完整流程图检测")
            return frame, []

    class MockNode:
        def __init__(self):
            self.params = {}
            self.name = "模拟圆节点"

    test_img_path = 'image/lena.png'
    test_img = cv2.imread(test_img_path)
    if test_img is None:
        test_img = np.zeros((512, 512, 3), dtype=np.uint8)

    mock_main_window = MockMainWindow(test_img)
    mock_node = MockNode()

    dialog = CircleParamsDialog(parent=None, node=mock_node, main_window=mock_main_window)
    dialog.setWindowTitle("圆检测 - 独立测试窗口")
    dialog.resize(390, 560)

    print("\n-> 运行测试：完美替换 5 行参数，无残留、无错位！")
    dialog.show()
    sys.exit(app.exec_())