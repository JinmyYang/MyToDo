"""主窗口:半透明、无边框、置顶的桌面便签。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea, QFrame,
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

from .task_store import TaskStore
from .task_item import TaskItem
from .completed_panel import CompletedPanel

QSS = """
QFrame#container {
    background: rgba(38, 40, 46, 215);
    border-radius: 14px;
}
QLabel { color: #f1f3f4; font-size: 13px; }
#title { font-size: 14px; font-weight: 600; padding-left: 2px; }
QPushButton { color: #e8eaed; background: transparent; border: none; }
QPushButton#addBtn {
    background: rgba(26,115,232,210);
    border-radius: 11px;
    font-size: 18px; font-weight: bold;
    min-width: 22px; min-height: 22px;
}
QPushButton#addBtn:hover { background: rgba(58,132,255,255); }
QPushButton#footerBtn {
    color: #9aa0a6; text-align: left;
    padding: 8px 14px; font-size: 12px;
}
QPushButton#footerBtn:hover { color: #ffffff; }
QPushButton#closeBtn { font-size: 14px; }
QPushButton#closeBtn:hover { color: #ff5f56; }
QScrollArea#listScroll { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 4px 0; }
QScrollBar::handle:vertical { background: rgba(255,255,255,45); border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""


class MainWindow(QWidget):
    def __init__(self, store: TaskStore):
        super().__init__()
        self.store = store
        self._drag_pos = None
        self._active_items = {}  # task_id -> TaskItem

        self.setWindowTitle("桌面便签")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(300, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self.container = QFrame()
        self.container.setObjectName("container")
        self.setStyleSheet(QSS)
        outer.addWidget(self.container)

        v = QVBoxLayout(self.container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ---- 标题栏(空白处可拖动窗口)----
        header = QFrame()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 12, 8, 8)
        hl.setSpacing(8)
        title = QLabel("便签")
        title.setObjectName("title")
        hl.addWidget(title)
        hl.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(QCursor(Qt.PointingHandCursor))
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(QApplication.quit)
        hl.addWidget(close_btn)
        v.addWidget(header)

        # ---- 加号行 ----
        add_row = QFrame()
        al = QHBoxLayout(add_row)
        al.setContentsMargins(10, 0, 10, 6)
        al.addStretch()
        add_btn = QPushButton("+")
        add_btn.setObjectName("addBtn")
        add_btn.setFixedSize(24, 24)
        add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        add_btn.setFocusPolicy(Qt.NoFocus)
        add_btn.setToolTip("新建任务")
        add_btn.clicked.connect(self.add_task)
        al.addWidget(add_btn)
        v.addWidget(add_row)

        # ---- 任务列表(可滚动)----
        self.scroll = QScrollArea()
        self.scroll.setObjectName("listScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch()  # 末尾占位,任务顶对齐
        self.scroll.setWidget(self.list_widget)
        v.addWidget(self.scroll, 1)

        # ---- 已完成面板(默认隐藏)----
        self.completed_panel = CompletedPanel()
        self.completed_panel.restored.connect(self.on_restore)
        self.completed_panel.setVisible(False)
        v.addWidget(self.completed_panel)

        # ---- 底部:已完成按钮 ----
        self.footer_btn = QPushButton("已完成 (0)")
        self.footer_btn.setObjectName("footerBtn")
        self.footer_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.footer_btn.setFocusPolicy(Qt.NoFocus)
        self.footer_btn.clicked.connect(self.toggle_completed)
        v.addWidget(self.footer_btn)

        self.load_tasks()

    # ---- 加载 ----
    def load_tasks(self):
        for t in self.store.active_tasks():
            self._add_item_widget(t, focus=False)
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._update_footer()

    def _add_item_widget(self, task, focus=True):
        item = TaskItem(task)
        item.completed.connect(self.on_complete)
        item.text_changed.connect(self.on_text_changed)
        item.delete_requested.connect(self.on_delete)
        # 插到末尾 stretch 之前
        self.list_layout.insertWidget(self.list_layout.count() - 1, item)
        self._active_items[task.id] = item
        if focus:
            item.focus_edit()
        return item

    # ---- 操作 ----
    def add_task(self):
        task = self.store.add("")
        self._add_item_widget(task, focus=True)

    def on_complete(self, task_id):
        task = self.store.get(task_id)
        if task is None:
            return
        if task.text.strip() == "":
            # 空任务:直接删除,不进已完成栏
            self.on_delete(task_id)
            return
        self.store.complete(task_id)
        item = self._active_items.pop(task_id, None)
        if item is not None:
            self.list_layout.removeWidget(item)
            item.deleteLater()
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._update_footer()

    def on_restore(self, task_id):
        self.store.restore(task_id)
        self.completed_panel.set_tasks(self.store.completed_tasks())
        task = self.store.get(task_id)
        if task is not None:
            self._add_item_widget(task, focus=False)
        self._update_footer()

    def on_text_changed(self, task_id, text):
        self.store.update_text(task_id, text)

    def on_delete(self, task_id):
        self.store.delete(task_id)
        item = self._active_items.pop(task_id, None)
        if item is not None:
            self.list_layout.removeWidget(item)
            item.deleteLater()
        self._update_footer()

    def toggle_completed(self):
        self.completed_panel.setVisible(not self.completed_panel.isVisible())

    def _update_footer(self):
        n = len(self.store.completed_tasks())
        self.footer_btn.setText(f"已完成 ({n})")

    # ---- 拖动窗口(点空白区域拖动)----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
