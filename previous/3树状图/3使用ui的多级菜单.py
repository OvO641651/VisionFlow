from PySide6.QtWidgets import QApplication
from PySide6.QtUiTools import QUiLoader

# 导入 QTreeWidget, QTreeWidgetItem, QIcon
from PySide6.QtWidgets import  QTreeWidget, QTreeWidgetItem
from PySide6.QtGui import QIcon

uiloader = QUiLoader()

'''
使用ui的多级菜单
'''

class SomeWindow:

    def __init__(self):

        self.ui = QUiLoader().load('main.ui')
        # 调用设置树控件
        self.setupTree()
        #self.ui.leafItem.clicked.connect(self.print_aaa())

    def print_aaa(self):
        print(111)

    def setupTree(self):
        # 获取树控件对象
        tree = self.ui.tree

        # 隐藏标头栏
        tree.setHeaderHidden(True)

        # 获取树控件的不可见根节点
        root = tree.invisibleRootItem()

        # 准备一个folder节点
        folderItem = QTreeWidgetItem()
        '''
        # 创建图标对象
        folderIcon = QIcon("image/lena.png")
        # 设置节点图标
        folderItem.setIcon(0, folderIcon)
        '''
        # 设置该节点  第1个column 文本
        folderItem.setText(0, '学员李辉')
        # 添加到树的不可见根节点下，就成为第一层节点
        root.addChild(folderItem)
        # 设置该节点为展开状态
        folderItem.setExpanded(True)

        # 准备一个 叶子 节点
        leafItem = QTreeWidgetItem()
        '''        
        leafIcon = QIcon("image/lena.png")
        # 设置节点图标
        leafItem.setIcon(0, leafIcon)
        '''
        # 设置该节点  第1个column 文本
        leafItem.setText(0, '作业 - web自动化1')
        # 添加到 叶子节点 到 folderItem 目录节点下
        folderItem.addChild(leafItem)#添加到 folderItem 目录节点下

        # 准备一个 叶子 节点
        leafItem1 = QTreeWidgetItem()
        # 设置该节点  第1个column 文本
        leafItem1.setText(0, '作业 - web自动化12')
        # 添加到 叶子节点 到 folderItem 目录节点下
        folderItem.addChild(leafItem1)  # 添加到folderItem目录节点下


        # 准备一个 叶子 节点
        leafItem1 = QTreeWidgetItem()
        # 设置该节点  第1个column 文本
        leafItem1.setText(0, '作业 - web自动化123')
        # 添加到 叶子节点 到 folderItem 目录节点下
        leafItem.addChild(leafItem1)# 添加到leafItem目录节点下

app = QApplication([])
w = SomeWindow()
w.ui.show()
app.exec_()