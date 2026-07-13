"""主窗口:半透明、无边框、置顶的桌面便签。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea, QFrame,
    QApplication, QMenu,
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
QPushButton#lockBtn { color: #9aa0a6; font-size: 15px; }
QPushButton#lockBtn:hover { color: #ffffff; }
QScrollArea#listScroll { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 4px 0; }
QScrollBar::handle:vertical { background: rgba(255,255,255,45); border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

EDGE = 8            # 边缘 resize 检测宽度
MIN_W, MIN_H = 220, 200
PANEL_H = 160       # 已完成面板展开时向下扩展的高度


class HeaderBar(QFrame):
    """上方栏:锁头按钮、空白可拖动、右键退出/解锁。"""

    def __init__(self, window):
        super().__init__()
        self._window = window

        hl = QHBoxLayout(self)
        hl.setContentsMargins(14, 12, 8, 8)
        hl.setSpacing(8)
        hl.addStretch()

        self.lock_btn = QPushButton("🔒")
        self.lock_btn.setObjectName("lockBtn")
        self.lock_btn.setFixedSize(26, 26)
        self.lock_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.lock_btn.setFocusPolicy(Qt.NoFocus)
        self.lock_btn.setToolTip("锁定")
        self.lock_btn.clicked.connect(lambda checked=False: window.set_locked(True))
        hl.addWidget(self.lock_btn)

    def contextMenuEvent(self, event):
        self._window.show_header_menu(event.globalPos())


class MainWindow(QWidget):
    def __init__(self, store: TaskStore):
        super().__init__()
        self.store = store
        self._drag_pos = None
        self._active_items = {}  # task_id -> TaskItem
        self._locked = False
        self._completed_expanded = False
        self._collapsed_h = None  # 已完成面板折叠时窗口高度
        self._resize_dir = None
        self._resize_start_geo = None
        self._resize_origin = None

        self.setWindowTitle("桌面便签")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(MIN_W, MIN_H)
        self.setMouseTracking(True)
        self.resize(300, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self.container = QFrame()
        self.container.setObjectName("container")
        self.container.setStyleSheet(QSS)
        # 容器内固定箭头光标,避免被窗口边缘的 resize 光标继承
        self.container.setCursor(QCursor(Qt.ArrowCursor))
        outer.addWidget(self.container)

        v = QVBoxLayout(self.container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # ---- 标题栏(空白处可拖动窗口,右键退出/解锁)----
        self.header = HeaderBar(self)
        v.addWidget(self.header)

        # ---- 加号行 ----
        self.add_row = QFrame()
        al = QHBoxLayout(self.add_row)
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
        v.addWidget(self.add_row)

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

        # ---- 底部:已完成按钮(触发面板向下展开)----
        self.footer_btn = QPushButton("已完成 (0)  >")
        self.footer_btn.setObjectName("footerBtn")
        self.footer_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.footer_btn.setFocusPolicy(Qt.NoFocus)
        self.footer_btn.clicked.connect(self.toggle_completed)
        v.addWidget(self.footer_btn)

        # ---- 已完成面板(在 footer 下方,默认隐藏)----
        self.completed_panel = CompletedPanel()
        self.completed_panel.restored.connect(self.on_restore)
        self.completed_panel.deleted.connect(self.on_delete)
        self.completed_panel.setVisible(False)
        v.addWidget(self.completed_panel)

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
        item.unlock_requested.connect(self.unlock)
        # 插到末尾 stretch 之前
        self.list_layout.insertWidget(self.list_layout.count() - 1, item)
        self._active_items[task.id] = item
        if focus:
            item.start_edit()
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
        # 已完成任务删除后也要刷新面板
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._update_footer()

    # ---- 已完成面板展开/折叠(向下扩展窗口高度,不挤压任务列表)----
    def toggle_completed(self):
        if not self._completed_expanded:
            self._collapsed_h = self.height()
            self._completed_expanded = True
            self.completed_panel.setVisible(True)
            self.resize(self.width(), self._collapsed_h + PANEL_H)
        else:
            self._completed_expanded = False
            self.completed_panel.setVisible(False)
            if self._collapsed_h is not None:
                self.resize(self.width(), self._collapsed_h)
        self._update_footer()

    def _footer_text(self):
        n = len(self.store.completed_tasks())
        arrow = "▽" if self._completed_expanded else ">"
        return f"已完成 ({n})  {arrow}"

    def _update_footer(self):
        self.footer_btn.setText(self._footer_text())

    # ---- 锁定/解锁 ----
    def set_locked(self, locked):
        self._locked = locked
        self.header.lock_btn.setVisible(not locked)
        self.add_row.setVisible(not locked)
        self.footer_btn.setVisible(not locked)
        if locked and self._completed_expanded:
            self.toggle_completed()  # 锁定时收起已完成面板
        for item in list(self._active_items.values()):
            item.set_locked(locked)

    def unlock(self):
        self.set_locked(False)

    def show_header_menu(self, global_pos):
        """上方栏右键菜单:锁定时可解锁,始终可退出。"""
        menu = QMenu(self)
        if self._locked:
            menu.addAction("解锁", self.unlock)
        menu.addAction("退出", QApplication.quit)
        menu.exec(global_pos)

    # ---- 边缘 8 方向 resize ----
    def _edge(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        left = x < EDGE
        right = x > w - EDGE
        top = y < EDGE
        bottom = y > h - EDGE
        if top and left:
            return "topleft"
        if top and right:
            return "topright"
        if bottom and left:
            return "bottomleft"
        if bottom and right:
            return "bottomright"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    def _cursor_for(self, direction):
        if direction in ("left", "right"):
            return Qt.SizeHorCursor
        if direction in ("top", "bottom"):
            return Qt.SizeVerCursor
        if direction in ("topleft", "bottomright"):
            return Qt.SizeFDiagCursor
        if direction in ("topright", "bottomleft"):
            return Qt.SizeBDiagCursor
        return Qt.ArrowCursor

    def _do_resize(self, global_pos):
        g = self._resize_start_geo
        dx = global_pos.x() - self._resize_origin.x()
        dy = global_pos.y() - self._resize_origin.y()
        d = self._resize_dir
        x, y, w, h = g.x(), g.y(), g.width(), g.height()
        if "left" in d:
            new_w = max(MIN_W, w - dx)
            x = g.x() + (w - new_w)
            w = new_w
        if "right" in d:
            w = max(MIN_W, w + dx)
        if "top" in d:
            new_h = max(MIN_H, h - dy)
            y = g.y() + (h - new_h)
            h = new_h
        if "bottom" in d:
            h = max(MIN_H, h + dy)
        self.setGeometry(x, y, w, h)

    # ---- 拖动窗口(点空白区域拖动) + 边缘 resize----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            direction = self._edge(event.position())
            if direction is not None:
                self._resize_dir = direction
                self._resize_start_geo = self.frameGeometry()
                self._resize_origin = event.globalPosition().toPoint()
                event.accept()
                return
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resize_dir is not None and (event.buttons() & Qt.LeftButton):
            self._do_resize(event.globalPosition().toPoint())
            event.accept()
            return
        if self._drag_pos is not None and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        # 无按键:按是否在边缘更新光标
        if not event.buttons():
            direction = self._edge(event.position())
            self.setCursor(QCursor(self._cursor_for(direction)))

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_dir = None
        self._resize_start_geo = None
        self._resize_origin = None
