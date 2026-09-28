import sys
from PySide2.QtWidgets import QApplication, QTreeWidgetItem
from PySide2.QtUiTools import QUiLoader

'''
实现控制树控件的树枝控件的点击
'''

class MainWindow:
    def __init__(self):
        self.ui = QUiLoader().load('main.ui')
        self.tree = self.ui.tree
        self.tree.itemClicked.connect(self.on_tree_item_clicked)

    def on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        # 固定位置：第0个顶层项的第0个子项（无论它叫什么名字）
        fixed_item = self.tree.topLevelItem(0).child(0)

        if item is fixed_item:
            print("aaa")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.ui.show()
    sys.exit(app.exec_())