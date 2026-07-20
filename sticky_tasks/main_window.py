"""主窗口:半透明、无边框、置顶的桌面便签。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea, QFrame,
    QApplication, QMenu,
)
from PySide6.QtCore import Qt, QEvent, QSize, QPointF, Signal, QRectF
from PySide6.QtGui import QCursor, QPixmap, QPainter, QColor, QIcon, QFont, QPen

from .task_store import TaskStore
from .task_item import TaskItem
from .completed_panel import CompletedPanel

QSS = """
QFrame#container {
    background: rgba(30, 31, 35, 238);
    border: 1px solid rgba(255, 255, 255, 28);
    border-radius: 18px;
}
QFrame#sectionSep {
    background: rgba(255, 255, 255, 14);
    border: none;
    max-height: 1px;
}
QLabel { color: #f5f5f7; font-size: 13px; }
QLabel#titleLabel {
    color: #f5f5f7;
    font-size: 15px;
    font-weight: 600;
    font-style: italic;
    letter-spacing: 0.5px;
}
QPushButton { color: #f5f5f7; background: transparent; border: none; }
QPushButton#inlineAddBtn {
    color: #7a7a82;
    background: rgba(255,255,255,5);
    border: 1px dashed rgba(255,255,255,10);
    border-radius: 8px;
    font-size: 16px; font-weight: 500;
    padding: 6px 0;
}
QPushButton#inlineAddBtn:hover {
    color: #c5c5cc;
    border-color: rgba(255,255,255,20);
    background: rgba(255,255,255,10);
}
QPushButton#footerBtn {
    color: #a1a1aa;
    text-align: left;
    border-top: 1px solid rgba(255, 255, 255, 14);
    padding: 10px 14px 11px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton#footerBtn:hover { color: #f5f5f7; background: rgba(255, 255, 255, 8); }
QScrollArea#listScroll { border: none; background: transparent; }
QScrollArea#listScroll viewport { background: transparent; }
QWidget#listWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 6px 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,55); border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

EDGE = 16           # 边 resize 检测宽度(覆盖到可见深色块最外沿,加宽便于命中)
CORNER = 26         # 角 resize 检测范围(比边更宽,抵消 8px 外边距 + 14px 圆角,便于命中对角缩放)
MIN_W, MIN_H = 220, 200
PANEL_H = 160       # 已完成面板展开时向下扩展的高度




class LockButton(QWidget):
    toggled = Signal(bool)

    def __init__(self, locked=False, parent=None):
        super().__init__(parent)
        self._locked = locked

    def set_locked(self, locked):
        self._locked = locked
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor("#f5f5f7") if self._locked else QColor("#8e8e93")
        pen = QPen(c, 1.5); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        w, h = self.width(), self.height()
        bw, bh = w * 0.55, h * 0.40
        body = QRectF((w - bw)/2, h*0.42, bw, bh)
        p.drawRoundedRect(body, 2.5, 2.5)
        sw, sh = w * 0.30, h * 0.38
        shackle = QRectF((w - sw)/2, h*0.10, sw, sh)
        p.drawArc(shackle, 0, 180 * 16)
        kx, ky = w/2, h*0.60
        p.drawEllipse(QPointF(kx, ky), 1.2, 1.2)
        p.drawLine(QPointF(kx, ky+1.2), QPointF(kx, ky+4))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggled.emit(not self._locked)

class HeaderBar(QFrame):
    """上方栏:加号与锁头横向排列、空白可拖动、右键退出/解锁。"""

    def __init__(self, window):
        super().__init__()
        self._window = window

        hl = QHBoxLayout(self)
        hl.setContentsMargins(16, 12, 12, 8)
        hl.setSpacing(7)

        self.title_label = QLabel("JUST DO IT.")
        self.title_label.setObjectName("titleLabel")
        hl.addWidget(self.title_label)
        hl.addStretch()

        # 加号:新建任务(与锁头同一行)
        self.lock_btn = LockButton(parent=self)
        self.lock_btn.setFixedSize(28, 28)
        self.lock_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.lock_btn.setToolTip("锁定")
        self.lock_btn.toggled.connect(lambda l: window.set_locked(l))
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
        self._edge_watch_ready = False
        self._cursor_overriding = False  # 是否已压入应用级 resize 光标

        self.setWindowTitle("桌面便签")
        self.setFont(QFont("Segoe UI Variable", 10))
        # 普通窗口层级(不再置顶),仅无边框
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(MIN_W, MIN_H)
        self.setMouseTracking(True)
        self.resize(320, 460)

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

        # ---- 标题栏(加号 + 锁头横向排列;空白处可拖动窗口,右键退出/解锁)----
        self.header = HeaderBar(self)
        v.addWidget(self.header)

        # ---- 顶部分隔线 ----
        self.top_sep = QFrame()
        self.top_sep.setObjectName("sectionSep")
        self.top_sep.setFrameShape(QFrame.NoFrame)
        self.top_sep.setFixedHeight(1)
        v.addWidget(self.top_sep)

        # ---- 任务列表(可滚动)----
        self.scroll = QScrollArea()
        self.scroll.setObjectName("listScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget = QWidget()
        self.list_widget.setObjectName("listWidget")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.addStretch()  # 末尾占位,任务顶对齐
        self.scroll.setWidget(self.list_widget)
        v.addWidget(self.scroll, 1)

        # ---- 行内加号(任务列表下方)----
        self._inline_add_btn = QPushButton("+")
        self._inline_add_btn.setObjectName("inlineAddBtn")
        self._inline_add_btn.setFixedHeight(32)
        self._inline_add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._inline_add_btn.setFocusPolicy(Qt.NoFocus)
        self._inline_add_btn.setToolTip("新建任务")
        self._inline_add_btn.clicked.connect(self.add_task)
        v.addWidget(self._inline_add_btn)

        # ---- 底部:已完成按钮(触发面板向下展开,chevron 图标表示展开/收起)----
        self.footer_btn = QPushButton("已完成 (0)")
        self.footer_btn.setObjectName("footerBtn")
        self.footer_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.footer_btn.setFocusPolicy(Qt.NoFocus)
        self.footer_btn.setIconSize(QSize(14, 14))
        self.footer_btn.setIcon(QIcon(self._chevron_pixmap("right")))
        self.footer_btn.clicked.connect(self.toggle_completed)
        v.addWidget(self.footer_btn)

        # ---- 已完成面板(在 footer 下方,默认隐藏)----
        self.completed_panel = CompletedPanel()
        self.completed_panel.restored.connect(self.on_restore)
        self.completed_panel.deleted.connect(self.on_delete)
        self.completed_panel.setVisible(False)
        v.addWidget(self.completed_panel)

        self.load_tasks()

        # 让边缘缩放对"可见深色块边缘"生效:给容器及所有子控件开鼠标追踪 + 事件过滤
        self._install_edge_watch(self.container)
        self._edge_watch_ready = True

    # ---- 边缘缩放:让 container 及子控件把鼠标事件转给窗口做边缘检测 ----
    def _watch_widget(self, w):
        w.setMouseTracking(True)
        w.installEventFilter(self)
        for c in w.findChildren(QWidget):
            c.setMouseTracking(True)
            c.installEventFilter(self)

    def _install_edge_watch(self, root):
        self._watch_widget(root)

    def eventFilter(self, obj, event):
        et = event.type()
        # footer 图标颜色随字体:通常灰(#9aa0a6),hover 变白(#ffffff)
        if obj is self.footer_btn and not self._locked:
            if et == QEvent.Enter:
                self.footer_btn.setIcon(
                    QIcon(self._chevron_pixmap(self._chevron_dir(), color=QColor("#ffffff"))))
                return False  # 不拦截,让默认 hover 样式继续生效
            elif et == QEvent.Leave:
                self.footer_btn.setIcon(
                    QIcon(self._chevron_pixmap(self._chevron_dir(), color=QColor("#9aa0a6"))))
                return False  # 不拦截,让默认 hover 样式继续生效
        if et == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            pos = self.mapFromGlobal(event.globalPosition().toPoint())
            direction = self._edge(pos)
            if direction is not None:
                self._resize_dir = direction
                self._resize_start_geo = self.frameGeometry()
                self._resize_origin = event.globalPosition().toPoint()
                return True  # 消费,防止子控件把它当普通点击
        elif et == QEvent.MouseMove:
            if self._resize_dir is not None and (event.buttons() & Qt.LeftButton):
                self._do_resize(event.globalPosition().toPoint())
                return True
            if not event.buttons():
                pos = self.mapFromGlobal(event.globalPosition().toPoint())
                direction = self._edge(pos)
                self._apply_edge_cursor(direction)
        elif et == QEvent.MouseButtonRelease:
            if self._resize_dir is not None:
                self._resize_dir = None
                self._resize_start_geo = None
                self._resize_origin = None
                self._apply_edge_cursor(None)
                return True
        return super().eventFilter(obj, event)

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
        if self._edge_watch_ready:
            self._watch_widget(item)  # 新任务行也纳入边缘检测
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
        return f"已完成  {n}"

    def _update_footer(self):
        self.footer_btn.setText(self._footer_text())
        # chevron 图标:折叠朝右 >,展开朝下 v;颜色与 footer 字体一致
        self.footer_btn.setIcon(QIcon(self._chevron_pixmap(self._chevron_dir())))

    def _chevron_dir(self):
        return "down" if self._completed_expanded else "right"

    def _chevron_pixmap(self, direction, size=14, color=QColor("#9aa0a6")):
        """用 QPainter 画矢量 chevron:浮点坐标严格对称 + 按设备像素比(DPR)高清渲染,不糊。"""
        try:
            dpr = QApplication.primaryScreen().devicePixelRatio() or 1.0
        except Exception:
            dpr = 1.0
        pm = QPixmap(int(size * dpr), int(size * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = p.pen()
        pen.setColor(color)
        pen.setWidthF(max(1.5, size * 0.16))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)

        cx = cy = size / 2.0
        off = size * 0.20    # 顶点相对中心的横向偏移
        off2 = size * 0.32   # 两臂展开的纵向偏移
        if direction == "down":
            p.drawLine(QPointF(cx - off2, cy - off), QPointF(cx, cy + off))
            p.drawLine(QPointF(cx, cy + off), QPointF(cx + off2, cy - off))
        else:  # right
            p.drawLine(QPointF(cx - off, cy - off2), QPointF(cx + off, cy))
            p.drawLine(QPointF(cx + off, cy), QPointF(cx - off, cy + off2))
        p.end()
        return pm

    # ---- 锁定/解锁 ----
    def set_locked(self, locked):
        self._locked = locked
        # 锁头按钮始终保留在右上角原处,仅切换图标与提示
        self.header.lock_btn.set_locked(locked)
        self.header.lock_btn.setVisible(True)
        self._inline_add_btn.setVisible(not locked)
        self.footer_btn.setVisible(not locked)
        if locked and self._completed_expanded:
            self.toggle_completed()  # 锁定时收起已完成面板
        for item in list(self._active_items.values()):
            item.set_locked(locked)

    def unlock(self):
        self.set_locked(False)

    def toggle_locked(self):
        self.set_locked(not self._locked)

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
        # 角:用更大的 CORNER 范围优先判定,便于命中对角缩放
        left_c = x < CORNER
        right_c = x > w - CORNER
        top_c = y < CORNER
        bottom_c = y > h - CORNER
        if top_c and left_c:
            return "topleft"
        if top_c and right_c:
            return "topright"
        if bottom_c and left_c:
            return "bottomleft"
        if bottom_c and right_c:
            return "bottomright"
        # 边:用较窄的 EDGE 范围
        if x < EDGE:
            return "left"
        if x > w - EDGE:
            return "right"
        if y < EDGE:
            return "top"
        if y > h - EDGE:
            return "bottom"
        return None

    def _apply_edge_cursor(self, direction):
        """用应用级 override 光标,确保能盖过 footer 等子控件自带的光标。"""
        if direction is not None:
            cur = QCursor(self._cursor_for(direction))
            if self._cursor_overriding:
                QApplication.changeOverrideCursor(cur)
            else:
                QApplication.setOverrideCursor(cur)
                self._cursor_overriding = True
        elif self._cursor_overriding:
            QApplication.restoreOverrideCursor()
            self._cursor_overriding = False

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
            self._apply_edge_cursor(direction)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_dir = None
        self._resize_start_geo = None
        self._resize_origin = None
        self._apply_edge_cursor(None)

    # ---- 锁定态:鼠标移出窗口隐藏锁头,移入再显示 ----
    def enterEvent(self, event):
        super().enterEvent(event)


    def leaveEvent(self, event):
        super().leaveEvent(event)
        # 鼠标真正离开窗口且不在缩放中时,复位 resize 光标
        if self._resize_dir is None:
            self._apply_edge_cursor(None)

