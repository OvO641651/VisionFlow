import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QLabel
)
from PySide6.QtCore import Qt, QPoint, QMimeData  # ✅ QDrag 和 QMimeData 在这里
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QMouseEvent, QDrag

'''
鼠标长按移动label
'''

class DragLabel(QLabel):
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"background-color: {color}; color: white; font-size: 24px; font-weight: bold; border: 2px solid #333;")
        self.setFixedSize(200, 150)
        self.drag_start_position = QPoint()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return

        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        # ✅ 从 QtCore 导入的 QDrag 和 QMimeData
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.text())
        drag.setMimeData(mime_data)

        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent):
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        source = event.source()
        if source is None or source == self:
            return

        source_text = source.text()
        source_style = source.styleSheet()
        target_text = self.text()
        target_style = self.styleSheet()

        source.setText(target_text)
        source.setStyleSheet(target_style)
        self.setText(source_text)
        self.setStyleSheet(source_style)

        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("拖拽式控件布局 Demo")
        self.resize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QGridLayout(central)

        labels = [
            ("摄像头 1", "#e74c3c"),
            ("摄像头 2", "#3498db"),
            ("摄像头 3", "#2ecc71"),
            ("摄像头 4", "#f1c40f")
        ]

        for i, (text, color) in enumerate(labels):
            label = DragLabel(text, color)
            row, col = divmod(i, 2)
            layout.addWidget(label, row, col)

        for label in central.findChildren(DragLabel):
            label.setAcceptDrops(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())