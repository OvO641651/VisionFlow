import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt

'''
树状图多级菜单
'''

class TreeMenuDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多级菜单 Demo")
        self.resize(300, 500)

        # 创建树形控件
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)  # 隐藏表头，与图一致
        self.setCentralWidget(self.tree)

        # ---------- 添加数据 ----------
        # 第一组：Selenium
        selenium_item = QTreeWidgetItem(self.tree)
        selenium_item.setText(0, "Selenium")
        selenium_item.setExpanded(True)  # 默认展开

        sub_items = [
            "Selenium 原理与安装",
            "选择元素的基本方法",
            "操控元素的基本方法",
            "css表达式-上篇",
            "css表达式-下篇",
            "frame切换/窗口切换",
            "选择框",
            "实战技巧",
            "Xpath选择器"
        ]
        for text in sub_items:
            child = QTreeWidgetItem(selenium_item)
            child.setText(0, text)

        # 第二组：自动化测试框架
        framework_item = QTreeWidgetItem(self.tree)
        framework_item.setText(0, "自动化测试框架")
        framework_item.setExpanded(False)  # 默认折叠

        sub_framework = [
            "hytest 框架",
            "pytest 框架",
            "pytest 助手"
        ]
        for text in sub_framework:
            child = QTreeWidgetItem(framework_item)
            child.setText(0, text)

        # 第三组：API接口自动化
        api_item = QTreeWidgetItem(self.tree)
        api_item.setText(0, "API接口自动化")
        api_item.setExpanded(False)

        # 第四组：手机APP自动化
        app_item = QTreeWidgetItem(self.tree)
        app_item.setText(0, "手机APP自动化")
        app_item.setExpanded(False)

        # ---------- 样式美化（可选，为了更像图片） ----------
        self.tree.setStyleSheet("""
            QTreeWidget {
                font-size: 14px;
                padding: 10px;
            }
            QTreeWidget::item {
                height: 30px;
                padding-left: 5px;
            }
            QTreeWidget::item:hover {
                background-color: #f0f0f0;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TreeMenuDemo()
    window.show()
    sys.exit(app.exec_())