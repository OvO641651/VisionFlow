from PySide2.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTabWidget,
                               QGraphicsView, QMenu, QMessageBox, QLineEdit,
                               QToolButton, QTabBar)
from PySide2.QtCore import QObject, Qt, QEvent, QTimer


class FlowPageManager(QObject):
    """
    流程图多页面管理器：把 main.ui 里的 flowWidget(QTabWidget) 改造成"浏览器式"标签页。

    每一页都有自己独立的一份东西：
        view  —— 一页一个 FlowchartView（自带 QGraphicsScene）
        nodes —— 这一页的方框列表
        edges —— 这一页的连线列表
        label —— 这一页底部"当前选中的节点"提示
    所以各页的流程图内容互不干扰。

    标签栏上可以做的操作：
        点最后面那个独立的 + 标签 —— 新建一页（和右键菜单里的"添加页面"是同一个动作）
        双击标签        —— 就地改这一页的名字（标签文字原地变成小输入框，不弹窗口）
        拖动标签        —— 调整页面顺序（每页的内容跟着标签一起走，不会串页）
        点标签右边的 ×  —— 关掉这一页（不弹确认框，像浏览器那样干脆）
    右键标签栏还能：
        添加页面 / 重命名页面 / 删除页面（"删除页面"会先弹确认框）
    注意：至少保留一页，只剩一页时 × 和"删除页面"都会提示。

    职责边界：
        这个类只管"页面"本身（标签页、每页的画布和方框/连线表），
        不碰检测、参数、图像。
        换页之后主窗口需要做的事（切换当前节点表、换参数、刷新画面），
        通过 on_page_switched 回调交给调用方处理。
    """

    def __init__(self, tab_widget, view_factory, on_page_switched=None, parent=None):
        """
        :param tab_widget: main.ui 里的 QTabWidget（控件名 flowWidget）。
        :param view_factory: 创建画布的函数，签名 view_factory(parent_widget) -> FlowchartView。
        :param on_page_switched: 换页后的回调，签名 on_page_switched(new_page, old_page)。
        :param parent: Qt 父对象。
        """
        super().__init__(parent)
        self.tab_widget = tab_widget
        self.view_factory = view_factory
        self.on_page_switched = on_page_switched

        self.pages = []            # 每页一条记录，顺序和标签栏保持一致
        self._pages_by_key = {}    # {页面标识: 页面记录}；拖动标签换序后靠它认页，不会认错
        self.current_page = None   # 当前正在使用的那一页
        self.switching = False     # 换页 / 删页过程中的保护标志（调用方也会读它）
        self._seq = 0              # 页面标识计数器(flow1,flow2,flow3...)
        self._title_editor = None        # 双击标题改名用的小输入框（没在改名字时是 None）
        self._title_editor_index = None  # 这个小输入框正在改第几页
        self.add_button = None           # "+"标签里那个按钮（setup() 里创建）
        self.add_tab_widget = None       # "+"所在的那个装饰标签（它不是流程图页面）

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def setup(self):
        """接管 flowWidget：登记第一页，装上 + 新建 / 右键菜单 / 双击改名 / × 关闭 / 拖动换序，返回第一页记录"""
        # 1、第一页：main.ui 里已经有一页（标题 Flow），把里面的 flowView 换成自定义画布
        first_widget = self.tab_widget.widget(0)
        first_view = self._make_view(first_widget)
        first_label = first_widget.findChild(QLabel, "lbl_current_node")
        self.current_page = self._register_page(first_widget, first_view, first_label)

        # 2、右键标签栏 → 弹出"添加页面 / 重命名页面 / 删除页面"
        tab_bar = self.tab_widget.tabBar()
        tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._on_tab_context_menu)
        tab_bar.setToolTip("点最后面那个 + 标签可以新建页面；右键点击标签可以添加 / 重命名 / 删除流程图页面；"
                           "双击标签可就地改名；拖动标签可以调整页面顺序")
        # 双击标签 → 重命名（QTabBar 没有双击信号，用事件过滤器接）
        tab_bar.installEventFilter(self)
        # 标签控件被销毁时（关窗口 / 退出程序）先把引用清掉，
        # 不然之后还会收到事件、去访问已经销毁的 C++ 对象而报 RuntimeError
        self.tab_widget.destroyed.connect(self._on_tab_widget_destroyed)

        # 3、每个标签右边显示一个 × ：点它就关掉这一页
        #    （右键菜单里的"删除页面"仍然会先弹确认框，两个入口都保留）
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)

        # 4、允许用鼠标拖动标签调整页面顺序（像浏览器 / 编辑器那样）
        self.tab_widget.setMovable(True)
        tab_bar.tabMoved.connect(self._on_tab_moved)

        # 5、在最后面放一个独立的"+"标签（它自己就是一个标签，
        #    位置和间距都由标签栏负责，不用手算坐标）
        self._create_add_tab()

        # 6、切换标签页 → 换掉 current_page 并通知调用方
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        return self.current_page

    def _create_add_tab(self):
        """
        建一个独立的"+"标签放在最后面。作为标签栏里的一个标签，位置、间距、高度全由标签栏自己算，

        它不是流程图页面：
            它没有页面记录（标签的 tabData 里没有它的标识），
            所以 _page_at() 找不到它 —— 双击改名、删除页面都会自动跳过它。
        它的"×"位置被换成了我们自己的"+"按钮，
            所以这个标签上不会出现关闭按钮。
        """
        tab_bar = self.tab_widget.tabBar()
        self.add_tab_widget = QWidget()
        index = self.tab_widget.addTab(self.add_tab_widget, "")   # 标签文字留空，只放按钮

        self.add_button = QToolButton(self.tab_widget)
        self.add_button.setText("+")
        self.add_button.setAutoRaise(True)          # 扁平样式，像浏览器那样
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setFixedSize(16, 22)        # 固定大小，让这个标签看起来像个小标签
        self.add_button.clicked.connect(self.add_page) # type:ignore
        # 把标签右侧那个位置交给我们的按钮（那个位置本来是放 × 的）
        tab_bar.setTabButton(index, QTabBar.RightSide, self.add_button)
        tab_bar.setTabToolTip(index, "新建页面")
        return index

    def _add_tab_index(self):
        """"+"那个装饰标签的下标（新页面都插在它前面，"+"永远在最后）"""
        if self.add_tab_widget is None:
            return self.tab_widget.count()
        index = self.tab_widget.indexOf(self.add_tab_widget)
        return index if index >= 0 else self.tab_widget.count()

    def _ensure_add_tab_last(self):
        """"+"标签必须永远待在最后：被拖到别处时，这里把它移回最后"""
        try:
            if self.add_tab_widget is None or self.tab_widget is None:
                return
            index = self.tab_widget.indexOf(self.add_tab_widget)
            if index < 0:
                return
            last = self.tab_widget.count() - 1
            if index != last:
                self.tab_widget.tabBar().moveTab(index, last)
                # 拖动"+"标签没有意义（它不是页面），顺手把当前页同步回真正的页面
                self._resync_current_page()
        except RuntimeError:
            # 控件已经销毁（关窗口 / 退出程序），忽略
            return

    def page_key(self):
        """当前页的标识；用来给"每页 × 每图"这类缓存做键"""
        return self.current_page["key"] if self.current_page is not None else None

    def add_page(self):
        """添加一页流程图，并自动切换到新页面，返回新页记录"""
        page_widget = QWidget()
        layout = QVBoxLayout(page_widget)
        # 新页面里也放一个"当前选中节点"的提示 label，和第一页保持一致
        label = QLabel("未选中节点")
        view = self._create_view(page_widget)
        layout.addWidget(view)
        layout.addWidget(label)

        # 用页面标识来编号；再用 _unique_title 挡一下"用户手动改过名字"造成的重名
        title = self._unique_title("Flow{0}".format(self._seq + 1))
        # 新页面插在"+"标签前面（"+"永远待在最后）
        index = self.tab_widget.insertTab(self._add_tab_index(), page_widget, title)
        page = self._register_page(page_widget, view, label)

        # 切到新页面（会触发 currentChanged → _on_tab_changed → 通知调用方）
        self.tab_widget.setCurrentIndex(index)
        return page

    def delete_page(self, index=None):
        """右键菜单"删除页面"：先弹确认框，确认后再删；成功返回 True"""
        if index is None:
            index = self.tab_widget.currentIndex()
        # 注意：标签栏里还有一个"+"装饰标签，所以判断"只剩一页"要用 len(self.pages)
        if len(self.pages) <= 1:
            QMessageBox.information(self.tab_widget, "提示", "至少要保留一个流程图页面。")
            return False
        if self._page_at(index) is None:
            return False

        # 先确认，避免误删
        title = self.tab_widget.tabText(index)
        ret = QMessageBox.question(
            self.tab_widget, "删除页面",
            "确定删除页面“{0}”吗？该页面里的方框和连线都会一起删除。".format(title),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return False

        return self._remove_page(index)

    def close_page(self, index=None):
        """
        关闭某一页（点标签右边的 × 时调用），成功返回 True。
        为了像浏览器那样干脆，这里不再弹确认框；
        右键菜单里的"删除页面"仍然会先确认，两个入口随便用哪个都行。
        """
        if index is None:
            index = self.tab_widget.currentIndex()
        if len(self.pages) <= 1:
            QMessageBox.information(self.tab_widget, "提示", "至少要保留一个流程图页面。")
            return False
        return self._remove_page(index)

    def _on_tab_close_requested(self, index):
        """点了标签上的 × ：关掉这一页"""
        self.close_page(index)

    def _remove_page(self, index):
        """真正删掉某一页：先把当前页切走 → 清画面 → 移除标签和数据记录 → 销毁页面控件"""
        deleted_page = self._page_at(index)
        if deleted_page is None:
            return False

        # 1、如果删的正好是当前页，先切到别的页，避免把正在使用的画布删掉
        if deleted_page is self.current_page:
            other_index = 0 if index != 0 else 1
            self.tab_widget.setCurrentIndex(other_index)   # 正常触发换页，调用方的引用会切过去

        # 2、丢掉这一页的画面（方框、连线都在这页自己的 scene 里），再移除标签页和数据记录。
        #    清空 scene 会让它发出 selectionChanged 信号，
        #    所以这一段把 switching 置上，让调用方忽略这次信号、也不会下标错位
        self.switching = True
        try:
            deleted_page["view"].scene.clear()
            deleted_page["nodes"] = []
            deleted_page["edges"] = []
            if deleted_page in self.pages:
                self.pages.remove(deleted_page)
            self._pages_by_key.pop(deleted_page["key"], None)
            self.tab_widget.removeTab(index)
        finally:
            self.switching = False

        # 3、removeTab 不会删除页面控件，这里手动销毁（view / label 都是它的子控件）
        deleted_page["widget"].setParent(None)
        deleted_page["widget"].deleteLater()

        # 4、兜底：万一 Qt 的下标变化没走到回调，这里补一次同步
        self._resync_current_page()
        return True

    def _on_tab_moved(self, from_index, to_index):
        """
        用户拖动标签换了顺序。

        - 真正的页面之间换序：把 self.pages 也跟着换，保持顺序一致；
        - 如果牵涉到"+"那个装饰标签：它不是一个页面，必须永远待在最后，
          所以安排一次把它移回最后（用单次定时器，避免在信号里再改序造成递归）。
        真正"按标签找页面"用的是 _page_at()（读标签里存的页面标识），
        所以即使 Qt 先发 currentChanged、后发 tabMoved，也不会把页面认错。
        """
        if self.add_tab_widget is not None and self.tab_widget is not None:
            try:
                if self.tab_widget.indexOf(self.add_tab_widget) != self.tab_widget.count() - 1:
                    QTimer.singleShot(0, self._ensure_add_tab_last)
            except RuntimeError:
                return
        # 只有"页面和页面之间"换序才需要动 self.pages（"+"标签本来就没有页面记录）
        if not (0 <= from_index < len(self.pages) and 0 <= to_index < len(self.pages)):
            return
        page = self.pages.pop(from_index)
        self.pages.insert(to_index, page)

    def rename_page(self, index=None):
        """
        就地重命名某一页（默认当前页）：标签文字原来的位置上直接出现一个小输入框，
        回车或者点到别处就保存，按 Esc 取消。
        双击标签、或右键菜单"重命名页面"都会调到这里。
        """
        if index is None:
            index = self.tab_widget.currentIndex()
        if index < 0 or index >= self.tab_widget.count():
            return False
        if self._page_at(index) is None:
            # 这是"+"那个装饰标签（不是真正的页面），不能改名
            return False

        # 如果已经有一个名字在改，先把它收掉（相当于回车保存）
        self._close_title_editor(commit=True)

        tab_bar = self.tab_widget.tabBar()
        rect = tab_bar.tabRect(index)   # 这一页标签在标签栏里的位置和大小
        if rect.isNull() or rect.isEmpty():
            return False

        # 把小输入框直接盖在标签原来的位置上（父控件设成标签栏，坐标就一致）
        editor = QLineEdit(tab_bar)
        editor.setText(tab_bar.tabText(index))   # 预填当前名字
        editor.selectAll()                      # 全选，直接打字就能替换
        editor.setGeometry(rect.adjusted(2, 2, -2, -2))   # 留 2 像素边，不完全盖住标签框
        editor.show()
        editor.setFocus()
        editor.installEventFilter(self)         # 用来接 Esc

        # 回车 / 失去焦点 → 保存
        editor.editingFinished.connect(lambda ed=editor: self._on_title_editor_finished(ed)) # type:ignore

        self._title_editor = editor
        self._title_editor_index = index
        return True

    def _on_title_editor_finished(self, editor=None):
        """就地改名的输入框：回车或者失去焦点，把名字写回去"""
        if editor is not None and editor is not self._title_editor:
            # 不是当前这个输入框发出来的信号，忽略
            return
        self._close_title_editor(commit=True)

    def _close_title_editor(self, commit=True):
        """收掉就地改名的小输入框；commit=True 保存新名字，False 取消（保持原名）"""
        editor = self._title_editor
        index = self._title_editor_index
        if editor is None:
            return

        # 先把引用清掉：下面 hide() / deleteLater() 可能再次触发 editingFinished，
        # 那时再进来会直接返回，不会重复处理
        self._title_editor = None
        self._title_editor_index = None

        try:
            new_title = editor.text().strip()
            editor.removeEventFilter(self)
            editor.hide()
            editor.deleteLater()
        except RuntimeError:
            # 输入框已经被销毁（窗口正在关闭），不用再收尾了
            return

        if not commit or not new_title or self.tab_widget is None:
            # 取消、名字为空、或者标签控件已经销毁：都保持原来的名字不改
            return
        try:
            if 0 <= index < self.tab_widget.count():
                self.tab_widget.setTabText(index, new_title)
        except RuntimeError:
            # 标签控件也已经销毁，忽略即可
            pass

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _register_page(self, widget, view, label):
        """登记一页流程图，返回这一页的记录"""
        page = {
            "key": self._seq,        # 稳定标识，用于"每页 × 每图"的检测结果缓存
            "widget": widget,        # 这一页所在的 QWidget
            "view": view,            # 这一页的画布 FlowchartView
            "label": label,          # 这一页底部提示"当前选中的节点"的 label
            "nodes": [],             # 这一页的方框
            "edges": [],             # 这一页的连线
            "selected_node": None,   # 这一页当前选中的节点
        }
        self._seq += 1
        self.pages.append(page)
        self._pages_by_key[page["key"]] = page
        # 把页面标识存进标签里：拖动标签换序之后，靠它来认"这个标签是哪一页"
        index = self.tab_widget.indexOf(widget)
        if index >= 0:
            self.tab_widget.tabBar().setTabData(index, page["key"])
        return page

    def _page_at(self, index):
        """
        按标签下标取页面记录。
        取的是"标签里存的页面标识"对应的记录，所以用户拖动标签换过顺序也不会认错页。
        """
        if self.tab_widget is None or index < 0 or index >= self.tab_widget.count():
            return None
        key = self.tab_widget.tabBar().tabData(index)
        return self._pages_by_key.get(key)

    def _create_view(self, parent_widget):
        """调用外部给的工厂创建一页画布，并设置好绘制刷新方式（防止拖尾残影）"""
        view = self.view_factory(parent_widget)
        view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        return view

    def _make_view(self, page_widget):
        """
        让一页里有一个自定义画布：
        main.ui 里的第一页已经有 QGraphicsView，用 replaceWidget 原地替换（拉伸比例、边距都会继承）；
        自己新建的空白页还没有 QGraphicsView，就直接建一个放进布局。
        """
        old_view = page_widget.findChild(QGraphicsView)
        if old_view is None:
            view = self._create_view(page_widget)
            layout = page_widget.layout()
            if layout is None:
                layout = QVBoxLayout(page_widget)
            layout.addWidget(view)
        else:
            parent_layout = old_view.parentWidget().layout()
            view = self._create_view(old_view.parentWidget())
            parent_layout.replaceWidget(old_view, view)
            # 彻底销毁旧控件，释放内存
            old_view.deleteLater()
        return view

    def _on_tab_context_menu(self, pos):
        """右键点击标签栏：弹出菜单，选择"添加页面 / 重命名页面 / 删除页面" """
        tab_bar = self.tab_widget.tabBar()
        click_index = tab_bar.tabAt(pos)   # 被右击的那一页；点在标签栏空白处会返回 -1

        # 右击的必须是一个真正的页面（"+"那个装饰标签不算），对应的菜单项才可用
        clicked_page = self._page_at(click_index)

        menu = QMenu(self.tab_widget)
        act_add = menu.addAction("添加页面")
        act_rename = menu.addAction("重命名页面")
        act_del = menu.addAction("删除页面")
        # 右击在标签栏空白处、或者右击在"+"标签上时，不知道该改哪一页，置灰
        act_rename.setEnabled(clicked_page is not None)
        # 只剩一个真页面时不允许删除，也置灰
        act_del.setEnabled(clicked_page is not None and len(self.pages) > 1)

        act = menu.exec_(tab_bar.mapToGlobal(pos))
        if act is None:
            # 用户点了菜单外面，取消操作
            return
        if act is act_add:
            self.add_page()
        elif act is act_rename and clicked_page is not None:
            self.rename_page(click_index)
        elif act is act_del and clicked_page is not None and len(self.pages) > 1:
            # 右击的是某一页就删那一页，右击空白处就删当前页
            self.delete_page(click_index if click_index >= 0 else self.tab_widget.currentIndex())

    def eventFilter(self, watched, event):
        """事件过滤器：双击标签 → 就地改名；改名输入框里按 Esc → 取消"""
        # 窗口 / 标签控件已经销毁时（程序退出阶段）不能再碰它，直接放行
        if self.tab_widget is None:
            return False

        try:
            # 1、就地改名的输入框里按 Esc：取消（回车由 editingFinished 处理）
            #    这一条只用 Python 身份比较，放在前面，尽量少去访问 C++ 对象
            if watched is self._title_editor and event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self._close_title_editor(commit=False)
                    return True

            # 2、双击标签栏上的标签（"+"那个装饰标签会被 rename_page 自己挡掉）
            if (watched is self.tab_widget.tabBar()
                    and event.type() == QEvent.MouseButtonDblClick):
                index = self.tab_widget.tabBar().tabAt(event.pos())
                if index >= 0:
                    self.rename_page(index)
                    # 这个双击已经处理掉了，不再传给标签栏
                    return True
        except RuntimeError:
            # 底层 C++ 对象已经被销毁（关窗口 / 退出程序时会出现），
            # 这时不用再处理事件，安静放行，避免往终端打印 Traceback
            return False

        return super().eventFilter(watched, event)

    def _on_tab_widget_destroyed(self, *args):
        """标签控件（连同整个窗口）被销毁时：把引用清掉，后续事件一律忽略"""
        self._title_editor = None
        self._title_editor_index = None
        self.add_button = None
        self.add_tab_widget = None
        self.current_page = None
        self.tab_widget = None

    def _unique_title(self, base):
        """给新页面起名字时避免和已有标签重名（用户可能手动改成过一样的名字）"""
        titles = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
        if base not in titles:
            return base
        n = 2
        while "{0}({1})".format(base, n) in titles:
            n += 1
        return "{0}({1})".format(base, n)

    def _on_tab_changed(self, index):
        """标签页切换：换掉 current_page，并通知调用方"""
        if self.switching:
            return
        page = self._page_at(index)
        if page is None:
            # 选中的不是真正的页面：说明用户点到了最后那个"+"装饰标签（例如点到它的空白处）。
            # 这种情况直接新建一页并切过去，效果和点 + 按钮一样。
            if index >= 0 and self.add_tab_widget is not None:
                try:
                    if index == self.tab_widget.indexOf(self.add_tab_widget):
                        self.add_page()
                except RuntimeError:
                    return
            return
        if page is self.current_page:
            # 已经就是这一页，不用重复处理
            return
        old_page = self.current_page
        self.current_page = page
        self._notify_switched(old_page)

    def _resync_current_page(self):
        """兜底同步：万一标签栏当前页和 current_page 对不上，这里纠正并通知调用方"""
        page = self._page_at(self.tab_widget.currentIndex())
        if page is not None and page is not self.current_page:
            old_page = self.current_page
            self.current_page = page
            self._notify_switched(old_page)

    def _notify_switched(self, old_page):
        """通知调用方：当前页换了（调用方在这里切换节点表、参数，并刷新画面）"""
        if self.on_page_switched is not None:
            self.on_page_switched(self.current_page, old_page)


# ---------- 独立测试：不启动主程序，单独试用多页面标签 ----------
if __name__ == '__main__':
    import sys
    from PySide2.QtWidgets import QApplication, QMainWindow
    from FlowChart import FlowchartView

    class MockHost:
        """最简宿主：只满足画布的少数回调，方便单独测试本模块"""
        def __init__(self):
            self.flow_nodes = []

        def on_node_selected(self, node):
            pass

        def on_node_double_clicked(self, node):
            pass

        def delete_flow_node(self, node):
            pass

        def add_flow_node(self, name, pos):
            pass

        def add_edge(self, start_node, end_node):
            pass

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.resize(900, 600)

    # 模拟 main.ui：一个 flowWidget，里面先放一页（标题 Flow）
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "Flow")
    window.setCentralWidget(tabs)

    host = MockHost()
    manager = FlowPageManager(tabs, lambda parent: FlowchartView(parent, main_window=host))
    manager.setup()
    print("初始页面数：", tabs.count(), " 当前页标识：", manager.page_key())

    manager.add_page()
    print("添加后页面数：", tabs.count(), " 当前页标识：", manager.page_key())
    print("提示：点最后面那个 + 标签可直接新建页面；右键标签栏可以添加 / 重命名 / 删除页面；"
          "双击标签可就地改名；拖动标签可换顺序；点标签右边的 × 可关闭这一页")

    window.show()
    sys.exit(app.exec_())
