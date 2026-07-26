"""主窗口:半透明、无边框、普通层级的桌面便签。"""

import math
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea, QFrame,
    QApplication, QMenu, QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt, QEvent, QSize, QPointF, Signal, QRectF, QPropertyAnimation, QEasingCurve,
    QTimer,
)
from PySide6.QtGui import (
    QCursor, QPixmap, QPainter, QPainterPath, QColor, QIcon, QFont, QPen,
    QShortcut, QKeySequence,
)

from .task_store import TaskStore
from .task_item import TaskItem
from .completed_panel import CompletedPanel
from .app_settings import AppSettings, Theme
from .settings_dialog import SettingsWindow

def build_qss(t: Theme) -> str:
    """根据主题动态生成 QSS。"""
    bg = t.bg_color
    # 背景渐变:顶部稍亮,底部稍暗
    top = QColor(min(bg.red() + 12, 255), min(bg.green() + 12, 255), min(bg.blue() + 12, 255))
    bot = QColor(max(bg.red() - 10, 0), max(bg.green() - 10, 0), max(bg.blue() - 10, 0))
    op = t.bg_opacity
    sep = t.sep_color
    sb = t.scrollbar_color
    sbh = t.scrollbar_hover_color
    txt = t.text_color
    ico = t.icon_color
    ico_h = t.icon_hover_color
    hl = t.highlight_color
    acc = t.accent_color

    return f"""
QFrame#container {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba({top.red()}, {top.green()}, {top.blue()}, {op}),
        stop:1 rgba({bot.red()}, {bot.green()}, {bot.blue()}, {min(op + 6, 255)}));
    border: none;
    border-radius: 8px;
}}
QFrame#sectionSep {{
    background: rgba({sep.red()}, {sep.green()}, {sep.blue()}, {sep.alpha()});
    border: none;
    max-height: 1px;
}}
QLabel {{ color: {txt.name()}; font-size: {t.font_size}px; font-family: "{t.font_family}"; }}
QLabel#titleLabel {{
    color: {t.fixed_title_color.name()};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2.5px;
    font-family: "Segoe UI Variable";
}}
QPushButton {{ color: {txt.name()}; background: transparent; border: none; }}
QPushButton#inlineAddBtn {{
    color: rgba({ico.red()}, {ico.green()}, {ico.blue()}, 190);
    background: transparent;
    border: none;
    border-radius: 9px;
    font-size: 17px;
    font-weight: 500;
    text-align: left;
    padding: 5px 0 5px 16px;
}}
QPushButton#inlineAddBtn:hover {{
    color: {acc.name()};
    background: rgba({hl.red()}, {hl.green()}, {hl.blue()}, {hl.alpha()});
}}
QPushButton#footerBtn {{
    color: {t.fixed_footer_color.name()};
    font-family: "Microsoft YaHei UI";
    text-align: left;
    border: none;
    padding: 9px 0 10px 14px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QPushButton#footerBtn:hover {{ color: #d0d0d8; }}
QPushButton#settingsBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px;
}}
QPushButton#settingsBtn:hover {{
    background: rgba({hl.red()}, {hl.green()}, {hl.blue()}, {hl.alpha() + 4});
}}
QFrame#footerBar {{
    border-top: 1px solid rgba({sep.red()}, {sep.green()}, {sep.blue()}, {sep.alpha()});
    background: transparent;
}}
QFrame#undoBar {{
    border-top: 1px solid rgba({sep.red()}, {sep.green()}, {sep.blue()}, {sep.alpha()});
    background: transparent;
}}
QLabel#undoLabel {{ color: {txt.name()}; font-size: 11px; }}
QPushButton#undoBtn {{
    color: {acc.name()};
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton#undoBtn:hover {{
    background: rgba({hl.red()}, {hl.green()}, {hl.blue()}, {hl.alpha() + 4});
    border-radius: 6px;
}}
QScrollArea#listScroll {{ border: none; background: transparent; }}
QScrollArea#listScroll viewport {{ background: transparent; }}
QWidget#listWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 5px; margin: 6px 3px 6px 0; }}
QScrollBar::handle:vertical {{ background: rgba({sb.red()},{sb.green()},{sb.blue()},{sb.alpha()}); border-radius: 2px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: rgba({sbh.red()},{sbh.green()},{sbh.blue()},{sbh.alpha()}); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""

EDGE = 10           # 边 resize 检测宽度(匹配 8px 外边距)
CORNER = 14         # 角 resize 检测范围(缩小避免与右下角设置按钮重叠)
MIN_W, MIN_H = 220, 200
PANEL_H = 160       # 已完成面板展开时向下扩展的高度




class LockButton(QWidget):
    toggled = Signal(bool)

    def __init__(self, locked=False, parent=None):
        super().__init__(parent)
        self._locked = locked
        self._color = QColor("#8e9099")
        self._sync_tooltip()

    def set_theme(self, theme: Theme):
        self._color = theme.icon_color
        self.update()

    def set_locked(self, locked):
        self._locked = locked
        self._sync_tooltip()
        self.update()

    def _sync_tooltip(self):
        action = "解锁窗口" if self._locked else "锁定窗口"
        self.setToolTip(f"{action} (Ctrl+L)")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        locked = self._locked
        color = self._color
        pen = QPen(color, 1.7)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        # 锁体:两态位置、尺寸完全一致
        body = QRectF(6.5, 14.0, 15.0, 10.5)
        p.drawRoundedRect(body, 2.5, 2.5)

        # 锁孔:圆点 + 短竖槽
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(14.0, 18.3), 1.4, 1.4)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)
        p.drawLine(QPointF(14.0, 20.1), QPointF(14.0, 21.8))

        # 锁梁:锁上=居中扣在锁体上;开锁=整体向右平移错开锁体。
        # (真实挂锁是锁梁绕腿轴前后甩开的三维动作,二维图标画不出深度旋转,
        #  用左右平移来表现这个"甩出"——锁梁错开锁体即表示已开。)
        shift = 0.0 if locked else 5.0
        shackle = QPainterPath()
        shackle.moveTo(10.0 + shift, 14.0)
        shackle.lineTo(10.0 + shift, 10.2)
        shackle.arcTo(QRectF(10.0 + shift, 6.2, 8.0, 8.0), 180.0, -180.0)
        shackle.lineTo(18.0 + shift, 14.0)
        p.drawPath(shackle)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggled.emit(not self._locked)

class HeaderBar(QFrame):
    """上方栏:标题、锁头、空白拖动区域及右键菜单。"""

    def __init__(self, window):
        super().__init__()
        self._window = window

        hl = QHBoxLayout(self)
        hl.setContentsMargins(16, 12, 12, 8)
        hl.setSpacing(7)
        # 固定高度:锁头隐藏(锁定+鼠标移出)时顶部栏不塌缩
        self.setFixedHeight(12 + 28 + 8)

        self.title_label = QLabel("JUST DO IT.")
        self.title_label.setObjectName("titleLabel")
        hl.addWidget(self.title_label)
        hl.addStretch()

        # 锁头:锁定/解锁窗口(提示文案随状态切换)
        self.lock_btn = LockButton(parent=self)
        self.lock_btn.setFixedSize(28, 28)
        self.lock_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.lock_btn.toggled.connect(lambda l: window.set_locked(l))
        hl.addWidget(self.lock_btn)

    def contextMenuEvent(self, event):
        self._window.show_header_menu(event.globalPos())


class MainWindow(QWidget):
    def __init__(self, store: TaskStore, settings_path: Path = None):
        super().__init__()
        self.store = store
        self._settings_path = settings_path or (Path.home() / ".sticky_tasks" / "settings.json")
        self.settings = AppSettings.load(self._settings_path)
        self.theme = self.settings.to_theme()
        self._drag_pos = None
        self._active_items = {}  # task_id -> TaskItem
        self._locked = False
        self._completed_expanded = False
        self._collapsed_h = None  # 已完成面板折叠时窗口高度
        self._expanded_panel_h = 0
        self._panel_lift = 0
        self._deleted_snapshot = None
        self._resize_dir = None
        self._resize_start_geo = None
        self._resize_origin = None
        self._edge_watch_ready = False
        self._cursor_overriding = False  # 是否已压入应用级 resize 光标
        self._settings_dirty = False
        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(180)
        self._settings_save_timer.timeout.connect(self._flush_settings_save)
        self._undo_timer = QTimer(self)
        self._undo_timer.setSingleShot(True)
        self._undo_timer.setInterval(5000)
        self._undo_timer.timeout.connect(self._clear_undo)
        QApplication.instance().aboutToQuit.connect(self._flush_settings_save)

        self.setWindowTitle("桌面便签")
        self.setFont(QFont(self.theme.font_family, 10))
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
        self.container.setStyleSheet(build_qss(self.theme))
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

        # ---- 行内加号:放进列表里,始终紧跟最后一个任务 ----
        self._inline_add_btn = QPushButton("+")
        self._inline_add_btn.setObjectName("inlineAddBtn")
        self._inline_add_btn.setFixedHeight(32)
        self._inline_add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._inline_add_btn.setFocusPolicy(Qt.NoFocus)
        self._inline_add_btn.setToolTip("新建任务 (Ctrl+N)")
        self._inline_add_btn.clicked.connect(self.add_task)
        self.list_layout.addWidget(self._inline_add_btn)

        self.list_layout.addStretch()  # 末尾占位,任务顶对齐
        self.scroll.setWidget(self.list_widget)
        v.addWidget(self.scroll, 1)

        # ---- 底部:已完成按钮 + 设置齿轮(最右) ----
        self.footer_bar = QFrame()
        self.footer_bar.setObjectName("footerBar")
        footer_layout = QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(0, 0, 6, 0)
        footer_layout.setSpacing(0)

        self.footer_btn = QPushButton("已完成 (0)")
        self.footer_btn.setObjectName("footerBtn")
        self.footer_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.footer_btn.setFocusPolicy(Qt.NoFocus)
        self.footer_btn.setIconSize(QSize(14, 14))
        self.footer_btn.setIcon(QIcon(self._chevron_pixmap("right")))
        self.footer_btn.clicked.connect(self.toggle_completed)
        footer_layout.addWidget(self.footer_btn, 1)

        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setFixedSize(28, 28)
        self.settings_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.settings_btn.setFocusPolicy(Qt.NoFocus)
        self.settings_btn.setToolTip("外观设置")
        self.settings_btn.setIcon(QIcon(self._gear_pixmap()))
        self.settings_btn.setIconSize(QSize(16, 16))
        self.settings_btn.clicked.connect(self.open_settings)
        footer_layout.addWidget(self.settings_btn)

        v.addWidget(self.footer_bar)

        # ---- 已完成面板(在 footer 下方,默认隐藏)----
        self.completed_panel = CompletedPanel()
        self.completed_panel.set_theme(self.theme)
        self.completed_panel.restored.connect(self.on_restore)
        self.completed_panel.deleted.connect(self.on_delete)
        self.completed_panel.setVisible(False)
        v.addWidget(self.completed_panel)

        self.undo_bar = QFrame()
        self.undo_bar.setObjectName("undoBar")
        undo_layout = QHBoxLayout(self.undo_bar)
        undo_layout.setContentsMargins(14, 2, 6, 2)
        self.undo_label = QLabel("已删除任务")
        self.undo_label.setObjectName("undoLabel")
        undo_layout.addWidget(self.undo_label)
        undo_layout.addStretch()
        self.undo_btn = QPushButton("撤销")
        self.undo_btn.setObjectName("undoBtn")
        self.undo_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.undo_btn.setFocusPolicy(Qt.NoFocus)
        self.undo_btn.clicked.connect(self.undo_delete)
        undo_layout.addWidget(self.undo_btn)
        self.undo_bar.setVisible(False)
        v.addWidget(self.undo_bar)

        self.load_tasks()
        self._restore_window_geometry()

        self._new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self._new_shortcut.activated.connect(self.add_task)
        self._lock_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        self._lock_shortcut.activated.connect(self.toggle_locked)

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
        # footer 图标颜色随主题:hover 提亮
        if obj is self.footer_btn and not self._locked:
            if et == QEvent.Enter:
                self.footer_btn.setIcon(
                    QIcon(self._chevron_pixmap(self._chevron_dir(), color=self.theme.icon_hover_color)))
                return False
            elif et == QEvent.Leave:
                self.footer_btn.setIcon(
                    QIcon(self._chevron_pixmap(self._chevron_dir(), color=self.theme.icon_color)))
                return False
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

    # ---- 边缘虚化 ----
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._draw_edge_fade(p)
        p.end()

    def _draw_edge_fade(self, p):
        """容器边缘向外逐渐虚化(羽化),替代硬阴影。

        从容器边缘向外画多层同心圆角矩形,越往外 alpha 越低,
        形成背景色→透明的柔和过渡,让窗口边缘自然融入桌面。
        """
        cr = QRectF(self.container.geometry())
        radius = 8.0
        fade = 7.0       # 虚化区域宽度(略小于 8px 外边距)
        layers = 14
        base = self.theme.edge_fade_color
        p.setPen(Qt.NoPen)
        for i in range(layers, 0, -1):
            expand = fade * i / layers
            # 越贴近容器边缘越不透明,最外层趋近全透明
            alpha = int(56 * (1.0 - (i - 1) / layers))
            rect = cr.adjusted(-expand, -expand, expand, expand)
            r = radius + expand
            p.setBrush(QColor(base.red(), base.green(), base.blue(), alpha))
            p.drawRoundedRect(rect, r, r)

    # ---- 加载 ----
    def load_tasks(self):
        for t in self.store.active_tasks():
            self._add_item_widget(t, focus=False, animate=False)
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._update_footer()

    def _add_item_widget(self, task, focus=True, animate=True, position=None):
        item = TaskItem(task)
        item.set_theme(self.theme)
        item.completed.connect(self.on_complete)
        item.text_changed.connect(self.on_text_changed)
        item.delete_requested.connect(self.on_delete)
        # 插到加号按钮之前(加号始终紧跟最后一个任务,其后才是末尾 stretch)
        if position is None:
            position = self.list_layout.count() - 2
        self.list_layout.insertWidget(position, item)
        self._active_items[task.id] = item
        if self._edge_watch_ready:
            self._watch_widget(item)  # 新任务行也纳入边缘检测
        if animate:
            self._fade_in(item)
        if focus:
            item.start_edit()
        return item

    def _fade_in(self, item):
        """新任务行淡入,完成后移除特效减少渲染开销。"""
        effect = QGraphicsOpacityEffect(item)
        effect.setOpacity(0)
        item.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: item.setGraphicsEffect(None))
        item._fade_anim = anim  # 持有引用,防止动画被提前回收
        anim.start()

    # ---- 操作 ----
    def add_task(self):
        if self._locked:
            return
        task = self.store.add("")
        self._add_item_widget(task, focus=True)

    def on_complete(self, task_id):
        task = self.store.get(task_id)
        if task is None:
            return
        if task.text.strip() == "":
            # 空任务:直接删除,不进已完成栏
            self.on_delete(task_id, offer_undo=False)
            return
        self.store.complete(task_id)
        item = self._active_items.pop(task_id, None)
        if item is not None:
            self.list_layout.removeWidget(item)
            item.deleteLater()
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._sync_expanded_panel_height()
        self._update_footer()

    def on_restore(self, task_id):
        self.store.restore(task_id)
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._sync_expanded_panel_height()
        task = self.store.get(task_id)
        if task is not None:
            self._add_item_widget(task, focus=False)
        self._update_footer()

    def on_text_changed(self, task_id, text):
        self.store.update_text(task_id, text)

    def on_delete(self, task_id, offer_undo=True):
        deleted = self.store.delete(task_id)
        if deleted is None:
            return
        item = self._active_items.pop(task_id, None)
        if item is not None:
            self.list_layout.removeWidget(item)
            item.deleteLater()
        # 已完成任务删除后也要刷新面板
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._sync_expanded_panel_height()
        self._update_footer()
        if offer_undo:
            self._deleted_snapshot = deleted
            self.undo_bar.setVisible(True)
            self._undo_timer.start()

    def undo_delete(self):
        if self._deleted_snapshot is None:
            return
        task, index = self._deleted_snapshot
        self.store.reinstate(task, index)
        if task.completed:
            self.completed_panel.set_tasks(self.store.completed_tasks())
            self._sync_expanded_panel_height()
        else:
            position = self.store.active_tasks().index(task)
            self._add_item_widget(task, focus=False, position=position)
        self._update_footer()
        self._clear_undo()

    def _clear_undo(self):
        self._undo_timer.stop()
        self._deleted_snapshot = None
        self.undo_bar.setVisible(False)

    # ---- 已完成面板展开/折叠(向下扩展窗口高度,不挤压任务列表)----
    def toggle_completed(self):
        if not self._completed_expanded:
            self._collapsed_h = self.height()
            self._completed_expanded = True
            self.completed_panel.setVisible(True)
            self._expanded_panel_h = min(PANEL_H, self.completed_panel.content_height())
            self.completed_panel.setFixedHeight(self._expanded_panel_h)
            self.resize(self.width(), self._collapsed_h + self._expanded_panel_h)
            self._keep_expanded_panel_on_screen()
        else:
            self._completed_expanded = False
            self.completed_panel.setVisible(False)
            # 用户可能在展开状态下调整过高度，应保留这次调整。
            self._collapsed_h = max(MIN_H, self.height() - self._expanded_panel_h)
            self.resize(self.width(), self._collapsed_h)
            if self._panel_lift:
                self.move(self.x(), self.y() + self._panel_lift)
            self._panel_lift = 0
            self.completed_panel.setMinimumHeight(0)
            self.completed_panel.setMaximumHeight(PANEL_H)
        self._update_footer()

    def _sync_expanded_panel_height(self):
        if not self._completed_expanded:
            return
        old_height = self._expanded_panel_h
        self._expanded_panel_h = min(PANEL_H, self.completed_panel.content_height())
        self.completed_panel.setFixedHeight(self._expanded_panel_h)
        self.resize(
            self.width(),
            max(MIN_H, self.height() + self._expanded_panel_h - old_height),
        )
        if self._expanded_panel_h < old_height and self._panel_lift:
            drop = min(self._panel_lift, old_height - self._expanded_panel_h)
            self.move(self.x(), self.y() + drop)
            self._panel_lift -= drop
        self._keep_expanded_panel_on_screen()

    def _keep_expanded_panel_on_screen(self):
        screen = (
            QApplication.screenAt(self.frameGeometry().center())
            or QApplication.primaryScreen()
        )
        if screen is None:
            return
        available = screen.availableGeometry()
        overflow = max(0, self.frameGeometry().bottom() - available.bottom())
        if overflow:
            lift = min(overflow, max(0, self.y() - available.top()))
            self.move(self.x(), self.y() - lift)
            self._panel_lift += lift

    def _restore_window_geometry(self):
        width = self.settings.window_width or 320
        height = self.settings.window_height or 460
        x = self.settings.window_x
        y = self.settings.window_y
        if x is None or y is None:
            self.resize(width, height)
            return
        primary = QApplication.primaryScreen()
        target = next(
            (screen for screen in QApplication.screens()
             if screen.availableGeometry().contains(x, y)),
            primary,
        )
        if target is None:
            self.setGeometry(x, y, width, height)
            return
        available = target.availableGeometry()
        width = min(max(MIN_W, width), available.width())
        height = min(max(MIN_H, height), available.height())
        x = min(max(x, available.left()), available.right() - width + 1)
        y = min(max(y, available.top()), available.bottom() - height + 1)
        self.setGeometry(x, y, width, height)

    def _footer_text(self):
        n = len(self.store.completed_tasks())
        return f"已完成  {n}"

    def _update_footer(self):
        self.footer_btn.setText(self._footer_text())
        # chevron 图标:折叠朝右 >,展开朝下 v;颜色与 footer 字体一致
        self.footer_btn.setIcon(QIcon(self._chevron_pixmap(self._chevron_dir())))

    def _chevron_dir(self):
        return "down" if self._completed_expanded else "right"

    def _chevron_pixmap(self, direction, size=14, color=None):
        """用 QPainter 画矢量 chevron:浮点坐标严格对称 + 按设备像素比(DPR)高清渲染,不糊。"""
        if color is None:
            color = self.theme.icon_color
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

    def _gear_pixmap(self, size=16, color=None):
        """画矢量齿轮图标。"""
        if color is None:
            color = self.theme.icon_color
        try:
            dpr = QApplication.primaryScreen().devicePixelRatio() or 1.0
        except Exception:
            dpr = 1.0
        pm = QPixmap(int(size * dpr), int(size * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        cx = cy = size / 2.0
        # 外圈
        p.drawEllipse(QPointF(cx, cy), size * 0.28, size * 0.28)
        # 内圈
        p.drawEllipse(QPointF(cx, cy), size * 0.12, size * 0.12)
        # 齿:6 条短线从外圈向外辐射
        for i in range(6):
            angle = math.radians(i * 60)
            x1 = cx + math.cos(angle) * size * 0.30
            y1 = cy + math.sin(angle) * size * 0.30
            x2 = cx + math.cos(angle) * size * 0.44
            y2 = cy + math.sin(angle) * size * 0.44
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        p.end()
        return pm

    # ---- 设置 ----
    def open_settings(self):
        win = getattr(self, "_settings_win", None)
        if win is not None:
            # 窗口已存在(可能只是被关闭隐藏),直接显示
            win.show()
            win.raise_()
            win.activateWindow()
            return
        win = SettingsWindow(self.settings, parent=self)
        win.changed.connect(self._on_settings_changed)
        self._settings_win = win
        win.show()

    def _on_settings_changed(self):
        """设置变动立即预览，短时间内的连续磁盘写入合并保存。"""
        self.apply_theme()
        self._settings_dirty = True
        self._settings_save_timer.start()

    def _flush_settings_save(self):
        if not self._settings_dirty:
            return
        self._settings_save_timer.stop()
        self.settings.save(self._settings_path)
        self._settings_dirty = False

    def apply_theme(self):
        """重新从 settings 生成主题并刷新所有 UI。"""
        self.theme = self.settings.to_theme()
        t = self.theme
        # 容器 QSS
        self.container.setStyleSheet(build_qss(t))
        # 全局字体
        self.setFont(QFont(t.font_family, 10))
        # 锁头
        self.header.lock_btn.set_theme(t)
        # 齿轮图标
        self.settings_btn.setIcon(QIcon(self._gear_pixmap()))
        # chevron
        self._update_footer()
        # 任务项
        for item in self._active_items.values():
            item.set_theme(t)
        # 已完成面板
        self.completed_panel.set_theme(t)
        # 边缘虚化重画
        self.update()

    # ---- 锁定/解锁 ----
    def set_locked(self, locked):
        self._locked = locked
        # 锁头位置固定在右上角;锁上时先显示,鼠标移出窗口再隐藏(见 leaveEvent)
        self.header.lock_btn.set_locked(locked)
        self.header.lock_btn.setVisible(True)
        self._inline_add_btn.setVisible(not locked)
        self.footer_bar.setVisible(not locked)
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
        if self._locked:          # 锁定后不允许调整窗口大小
            return None
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

    def closeEvent(self, event):
        """主窗口关闭时同步关闭独立设置窗口并清理全局光标。"""
        win = getattr(self, "_settings_win", None)
        if win is not None:
            win.close()
        saved_height = self.height()
        saved_y = self.y()
        if self._completed_expanded:
            saved_height = max(MIN_H, saved_height - self._expanded_panel_h)
            saved_y += self._panel_lift
        self.settings.window_x = self.x()
        self.settings.window_y = saved_y
        self.settings.window_width = self.width()
        self.settings.window_height = saved_height
        self._settings_dirty = True
        self._flush_settings_save()
        self._apply_edge_cursor(None)
        super().closeEvent(event)

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
        if self._locked:
            self.header.lock_btn.setVisible(True)


    def leaveEvent(self, event):
        super().leaveEvent(event)
        # 锁定时鼠标移出窗口即隐藏锁头(移入时 enterEvent 再显示)
        if self._locked:
            self.header.lock_btn.setVisible(False)
        # 鼠标真正离开窗口且不在缩放中时,复位 resize 光标
        if self._resize_dir is None:
            self._apply_edge_cursor(None)

