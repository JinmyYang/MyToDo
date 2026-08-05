"""主窗口:半透明、无边框、普通层级的桌面便签。"""

import math
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea, QFrame,
    QApplication, QMenu, QGraphicsOpacityEffect, QAbstractButton,
)
from PySide6.QtCore import (
    Qt, QEvent, QSize, QPointF, Signal, QRectF, QPropertyAnimation, QEasingCurve,
    QTimer,
)
from PySide6.QtGui import (
    QCursor, QPixmap, QPainter, QPainterPath, QColor, QIcon, QFont, QPen,
    QShortcut, QKeySequence,
)

from . import APP_NAME
from .i18n import t
from .task_store import TaskStore
from .task_item import TaskItem
from .completed_panel import CompletedPanel
from .app_paths import SETTINGS_FILE
from .app_settings import AppSettings, Theme
from .settings_dialog import SettingsWindow
from .history_window import HistoryWindow

def build_qss(t: Theme) -> str:
    """根据主题动态生成 QSS。"""
    bg = t.bg_color
    # 背景用纯色:垂直渐变的色差只有约 22 个灰阶却要铺满整个窗口高度,
    # 8bit 量化下会出现一条条水平色带,中等透明度时尤其明显。
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
    background: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {op});
    border: none;
    border-radius: 8px;
}}
QFrame#sectionSep {{
    background: rgba({sep.red()}, {sep.green()}, {sep.blue()}, {sep.alpha()});
    border: none;
    max-height: 1px;
}}
QLabel {{ color: {txt.name()}; font-size: {t.font_size}px; font-family: "{t.font_family}"; }}
QStackedWidget#taskStack {{ background: transparent; }}
QLabel#taskText {{
    background: transparent;
    border: none;
    color: {txt.name()};
    font-size: {t.font_size}px;
    font-family: "{t.font_family}";
    padding: 0px;
}}
QPlainTextEdit#taskEdit {{
    background: rgba({hl.red()},{hl.green()},{hl.blue()},12);
    border: 1px solid rgba({acc.red()}, {acc.green()}, {acc.blue()}, 140);
    border-radius: 8px;
    color: {txt.name()};
    font-size: {t.font_size}px;
    font-family: "{t.font_family}";
    padding: 5px 7px;
}}
QLabel#titleLabel {{
    color: {t.fixed_title_color.name()};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2.5px;
    font-family: "Segoe UI Variable";
}}
QPushButton {{ color: {txt.name()}; background: transparent; border: none; }}
QPushButton#inlineAddBtn {{
    color: rgba({ico.red()}, {ico.green()}, {ico.blue()}, 215);
    background: transparent;
    border: none;
    border-radius: 9px;
    font-size: 20px;
    font-weight: 600;
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
QScrollArea#listScroll {{ border: none; background: transparent; }}
QScrollArea#listScroll viewport {{ background: transparent; }}
QWidget#listWidget {{ background: transparent; }}
QLabel#emptyHint {{
    color: rgba({ico.red()}, {ico.green()}, {ico.blue()}, 110);
    font-size: 11px;
    padding: 6px 16px 0 16px;
}}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 6px 0; }}
QScrollBar::handle:vertical {{
    background: rgba({sb.red()},{sb.green()},{sb.blue()},{sb.alpha()});
    border-radius: 2px;
    min-height: 24px;
    margin: 0 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba({sbh.red()},{sbh.green()},{sbh.blue()},{sbh.alpha()});
    border-radius: 3px;
    margin: 0 1px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""

EDGE = 10           # 边 resize 检测宽度(匹配 8px 外边距)
CORNER = 14         # 角 resize 检测范围(缩小避免与右下角设置按钮重叠)
MIN_W, MIN_H = 220, 200
PANEL_H = 160       # 已完成面板展开时向下扩展的高度


def _on_segment(a: QPointF, b: QPointF, dist: float) -> QPointF:
    """从 a 沿 a→b 方向取距离 dist 的点(螺母图标削角/凹曲线用)。"""
    dx, dy = b.x() - a.x(), b.y() - a.y()
    length = math.hypot(dx, dy)
    if length == 0:
        return QPointF(a)
    return QPointF(a.x() + dx / length * dist, a.y() + dy / length * dist)




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
        action = t("main.lock_action_on") if self._locked else t("main.lock_action_off")
        self.setToolTip(t("main.lock_tooltip", action=action))

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
        hl.setContentsMargins(16, 6, 12, 6)
        hl.setSpacing(7)
        # 固定高度:锁头隐藏(锁定+鼠标移出)时顶部栏不塌缩
        self.setFixedHeight(6 + 28 + 6)

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
        self._settings_path = settings_path or SETTINGS_FILE
        self.settings = AppSettings.load(self._settings_path)
        self.theme = self.settings.to_theme()
        self._drag_pos = None
        self._active_items = {}  # task_id -> TaskItem
        self._locked = False
        self._completed_expanded = False
        self._collapsed_h = None  # 已完成面板折叠时窗口高度
        self._expanded_panel_h = 0
        self._panel_lift = 0
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
        QApplication.instance().aboutToQuit.connect(self._save_settings_on_quit)
        self._dragged_task_id = None
        self._task_drag_global_pos = None
        self._task_drag_order_changed = False
        self._fade_pixmap = None   # 边缘羽化缓存,避免每次重绘都画 14 层矢量图形
        self._fade_key = None
        self._task_drag_scroll_timer = QTimer(self)
        self._task_drag_scroll_timer.setInterval(40)
        self._task_drag_scroll_timer.timeout.connect(self._auto_scroll_task_drag)

        self.setWindowTitle(APP_NAME)
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
        self._inline_add_btn.setFixedHeight(36)
        self._inline_add_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._inline_add_btn.setFocusPolicy(Qt.NoFocus)
        self._inline_add_btn.setToolTip(t("main.new_tooltip"))
        self._inline_add_btn.clicked.connect(self.add_task)
        self.list_layout.addWidget(self._inline_add_btn)

        # ---- 空列表引导提示(紧跟加号之后;不占用任务的索引空间)----
        self._empty_hint = QLabel(t("main.empty_hint"))
        self._empty_hint.setObjectName("emptyHint")
        self._empty_hint.setVisible(False)
        self.list_layout.addWidget(self._empty_hint)

        self.list_layout.addStretch()  # 末尾占位,任务顶对齐
        self.scroll.setWidget(self.list_widget)
        v.addWidget(self.scroll, 1)

        # ---- 底部:已完成按钮 + 设置齿轮(最右) ----
        self.footer_bar = QFrame()
        self.footer_bar.setObjectName("footerBar")
        footer_layout = QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(0, 0, 6, 0)
        footer_layout.setSpacing(0)

        self.footer_btn = QPushButton(t("main.completed_count", n=0))
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
        self.settings_btn.setToolTip(t("main.settings_tooltip"))
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
                # 角落区域与 footer 按钮重叠时,优先让按钮处理点击;
                # 边(非角)仍照常启动缩放。
                corners = ("topleft", "topright", "bottomleft", "bottomright")
                if isinstance(obj, QAbstractButton) and direction in corners:
                    return False
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

    # ---- 边缘虚化(缓存成位图,避免每次重绘都画 14 层矢量图形)----
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.width() <= 0 or self.height() <= 0:
            return
        p = QPainter(self)
        p.drawPixmap(0, 0, self._edge_fade_pixmap())
        p.end()

    def _screen_dpr(self):
        """窗口所在屏幕的设备像素比(副屏高DPI下图标不糊)。"""
        try:
            screen = (
                QApplication.screenAt(self.frameGeometry().center())
                or QApplication.primaryScreen()
            )
            return (screen.devicePixelRatio() if screen else None) or 1.0
        except Exception:
            return 1.0

    def _edge_fade_pixmap(self):
        """返回当前尺寸+主题下的羽化位图,命中缓存时直接复用。"""
        key = (self.width(), self.height(), id(self.theme))
        if self._fade_pixmap is not None and self._fade_key == key:
            return self._fade_pixmap
        dpr = self._screen_dpr()
        pm = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        self._paint_edge_fade(p)
        p.end()
        self._fade_pixmap = pm
        self._fade_key = key
        return pm

    def _paint_edge_fade(self, p):
        """容器边缘向外逐渐虚化(羽化),替代硬阴影。

        从容器边缘向外画多层同心圆角矩形的"环带"(外扩矩形减去容器矩形),
        越往外 alpha 越低,形成背景色→透明的柔和过渡。
        环带画法保证容器内部不被叠加任何颜色,透明度与滑杆值一致。
        """
        cr = QRectF(self.container.geometry())
        radius = 8.0
        fade = 7.0       # 虚化区域宽度(略小于 8px 外边距)
        layers = 14
        base = self.theme.edge_fade_color
        # 羽化强度随背景透明度等比缩放:低透明度时不再残留一圈可见薄雾
        fade_strength = self.theme.bg_opacity / 255.0
        p.setPen(Qt.NoPen)
        inner = QPainterPath()
        inner.addRoundedRect(cr, radius, radius)
        for i in range(layers, 0, -1):
            expand = fade * i / layers
            # 越贴近容器边缘越不透明,最外层趋近全透明
            alpha = int(56 * fade_strength * (1.0 - (i - 1) / layers))
            rect = cr.adjusted(-expand, -expand, expand, expand)
            r = radius + expand
            ring = QPainterPath()
            ring.addRoundedRect(rect, r, r)
            p.setBrush(QColor(base.red(), base.green(), base.blue(), alpha))
            p.drawPath(ring.subtracted(inner))  # 只画容器外的那圈环

    # ---- 加载 ----
    def _update_empty_hint(self):
        """无活跃任务时显示引导提示。"""
        self._empty_hint.setVisible(not self._active_items)

    def load_tasks(self):
        # 清理上次退出时残留的空任务(新建后未输入即退出所致)
        empty_ids = [t.id for t in self.store.active_tasks() if not t.text.strip()]
        if empty_ids:
            self.store.permanent_delete(empty_ids)
        for t in self.store.active_tasks():
            self._add_item_widget(t, focus=False, animate=False)
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._update_footer()
        self._update_empty_hint()

    def _add_item_widget(self, task, focus=True, animate=True, position=None):
        item = TaskItem(task)
        item.set_theme(self.theme)
        item.completed.connect(self.on_complete)
        item.text_changed.connect(self.on_text_changed)
        item.delete_requested.connect(self.on_delete)
        item.drag_started.connect(self._on_task_drag_started)
        item.drag_moved.connect(self._on_task_drag_moved)
        item.drag_finished.connect(self._on_task_drag_finished)
        # 插到加号按钮之前(加号始终紧跟最后一个任务)
        if position is None:
            position = self.list_layout.indexOf(self._inline_add_btn)
        self.list_layout.insertWidget(position, item)
        self._active_items[task.id] = item
        if self._edge_watch_ready:
            self._watch_widget(item)  # 新任务行也纳入边缘检测
        if animate:
            self._fade_in(item)
        if focus:
            item.start_edit()
        self._update_empty_hint()
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
            self.on_delete(task_id, permanent=True)
            return
        self.store.complete(task_id)
        item = self._active_items.pop(task_id, None)
        if item is not None:
            self.list_layout.removeWidget(item)
            item.deleteLater()
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._sync_expanded_panel_height()
        self._update_footer()
        self._update_empty_hint()

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

    def _ordered_task_items(self):
        return [
            self.list_layout.itemAt(index).widget()
            for index in range(self.list_layout.count())
            if isinstance(self.list_layout.itemAt(index).widget(), TaskItem)
        ]

    def _on_task_drag_started(self, task_id, global_pos):
        if self._locked or task_id not in self._active_items:
            return
        self._dragged_task_id = task_id
        self._task_drag_global_pos = global_pos
        self._task_drag_order_changed = False
        self._task_drag_scroll_timer.start()

    def _on_task_drag_moved(self, task_id, global_pos):
        if task_id != self._dragged_task_id:
            return
        self._task_drag_global_pos = global_pos
        self._reorder_dragged_task(global_pos)

    def _reorder_dragged_task(self, global_pos):
        dragged = self._active_items.get(self._dragged_task_id)
        if dragged is None:
            return
        items = self._ordered_task_items()
        if dragged not in items:
            return

        pointer_y = self.list_widget.mapFromGlobal(global_pos).y()
        others = [item for item in items if item is not dragged]
        target_index = len(others)
        for index, item in enumerate(others):
            if pointer_y < item.geometry().center().y():
                target_index = index
                break
        if target_index == items.index(dragged):
            return

        self.list_layout.removeWidget(dragged)
        self.list_layout.insertWidget(target_index, dragged)
        self.list_layout.activate()
        self._task_drag_order_changed = True

    def _auto_scroll_task_drag(self):
        if self._dragged_task_id is None or self._task_drag_global_pos is None:
            self._task_drag_scroll_timer.stop()
            return
        viewport = self.scroll.viewport()
        pos = viewport.mapFromGlobal(self._task_drag_global_pos)
        margin = 28
        delta = 0
        if pos.y() < margin:
            delta = -12
        elif pos.y() > viewport.height() - margin:
            delta = 12
        if delta == 0:
            return
        bar = self.scroll.verticalScrollBar()
        old_value = bar.value()
        bar.setValue(old_value + delta)
        if bar.value() != old_value:
            self._reorder_dragged_task(self._task_drag_global_pos)

    def _on_task_drag_finished(self, task_id):
        if task_id != self._dragged_task_id:
            return
        self._task_drag_scroll_timer.stop()
        if self._task_drag_order_changed:
            ordered_items = self._ordered_task_items()
            ordered_ids = [item.task.id for item in ordered_items]
            self.store.reorder_active(ordered_ids)
            self._active_items = {item.task.id: item for item in ordered_items}
        self._dragged_task_id = None
        self._task_drag_global_pos = None
        self._task_drag_order_changed = False

    def on_delete(self, task_id, permanent=False):
        if permanent:
            deleted = self.store.permanent_delete([task_id])
        else:
            deleted = [self.store.delete(task_id)]
        if not deleted or deleted[0] is None:
            return
        item = self._active_items.pop(task_id, None)
        if item is not None:
            self.list_layout.removeWidget(item)
            item.deleteLater()
        # 已完成任务删除后也要刷新面板
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._sync_expanded_panel_height()
        self._update_footer()
        self._update_empty_hint()

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
        return t("main.completed_count", n=n)

    def _update_footer(self):
        self.footer_btn.setText(self._footer_text())
        # chevron 图标:折叠朝右 >,展开朝下 v;颜色与 footer 字体一致
        self.footer_btn.setIcon(QIcon(self._chevron_pixmap(self._chevron_dir())))

    def _chevron_dir(self):
        return "down" if self._completed_expanded else "right"

    def _chevron_pixmap(self, direction, size=14, color=None):
        """用 QPainter 画矢量 chevron:浮点坐标严格对称 + 按所在屏幕 DPR 高清渲染,不糊。"""
        if color is None:
            color = self.theme.icon_color
        dpr = self._screen_dpr()
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
        """画设置图标:凹边削角螺母造型 + 中心小圆孔(定稿 nut3_B)。

        尖头六边形(上下为角),每条边用二次贝塞尔曲线向中心内凹,
        六个角各削去一小段平面,细线条 + 小圆孔。
        """
        if color is None:
            color = self.theme.icon_color
        dpr = self._screen_dpr()
        pm = QPixmap(int(size * dpr), int(size * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        cx = cy = size / 2.0
        center = QPointF(cx, cy)
        hex_r = size * 0.44          # 顶点半径
        stroke_w = max(1.0, size * 0.085)  # 细线条
        chamfer = size * 0.10        # 削角长度
        depth = size * 0.12          # 边中点向中心内凹的深度
        # 尖头六边形顶点(上下为角)
        verts = [
            QPointF(
                cx + math.cos(math.radians(90 + i * 60)) * hex_r,
                cy + math.sin(math.radians(90 + i * 60)) * hex_r,
            )
            for i in range(6)
        ]
        path = QPainterPath()
        path.moveTo(_on_segment(verts[0], verts[1], chamfer))
        for i in range(6):
            a = verts[i]
            b = verts[(i + 1) % 6]
            nxt = verts[(i + 2) % 6]
            # 边 a→b 的内凹曲线:控制点 = 边中点向中心拉 depth
            mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
            path.quadTo(_on_segment(mid, center, depth), _on_segment(b, a, chamfer))
            # 顶点 b 的削角小平面(微圆角由 RoundJoin 提供)
            path.lineTo(_on_segment(b, nxt, chamfer))
        path.closeSubpath()
        pen = QPen(color, stroke_w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        # 中心小圆孔
        p.drawEllipse(center, size * 0.11, size * 0.11)
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
        win.history_requested.connect(self.open_history)
        self._settings_win = win
        win.show()

    def open_history(self):
        win = getattr(self, "_history_win", None)
        if win is None:
            win = HistoryWindow(self.store, parent=self)
            win.changed.connect(self._reload_task_views)
            self._history_win = win
        win.refresh()
        win.show()
        win.raise_()
        win.activateWindow()

    def _reload_task_views(self):
        for item in self._active_items.values():
            self.list_layout.removeWidget(item)
            item.deleteLater()
        self._active_items.clear()
        for task in self.store.active_tasks():
            self._add_item_widget(task, focus=False, animate=False)
        self.completed_panel.set_tasks(self.store.completed_tasks())
        self._sync_expanded_panel_height()
        self._update_footer()
        self._update_empty_hint()

    def _on_settings_changed(self):
        """设置变动立即预览，短时间内的连续磁盘写入合并保存。"""
        self.apply_theme()
        self._settings_dirty = True
        self._settings_save_timer.start()

    def _snapshot_geometry(self):
        """把当前窗口位置/大小写入 settings(展开态折算回折叠态)。"""
        saved_height = self.height()
        saved_y = self.y()
        if self._completed_expanded:
            saved_height = max(MIN_H, saved_height - self._expanded_panel_h)
            saved_y += self._panel_lift
        self.settings.window_x = self.x()
        self.settings.window_y = saved_y
        self.settings.window_width = self.width()
        self.settings.window_height = saved_height

    def _flush_settings_save(self):
        if not self._settings_dirty:
            return
        self._settings_save_timer.stop()
        self.settings.save(self._settings_path)
        self._settings_dirty = False

    def _save_settings_on_quit(self):
        """退出前强制保存一次。

        菜单"退出"走 QApplication.quit(),不触发 closeEvent,
        若只依赖 closeEvent,窗口位置/大小会丢失。
        """
        self._snapshot_geometry()
        self._settings_dirty = True
        self._flush_settings_save()

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
        # 主题变了,羽化缓存失效
        self._fade_pixmap = None
        self._fade_key = None
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
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff if locked else Qt.ScrollBarAsNeeded,
        )
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
            menu.addAction(t("main.menu_unlock"), self.unlock)
        menu.addAction(t("main.menu_quit"), QApplication.quit)
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
        history_win = getattr(self, "_history_win", None)
        if history_win is not None:
            history_win.close()
        self._snapshot_geometry()
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

