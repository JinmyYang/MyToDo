"""单个任务项:圆点(点击完成)+ 文字(右键编辑/删除)+ 行尾加号/折叠箭头。"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QStackedWidget,
    QMenu, QFrame, QPlainTextEdit, QSizePolicy, QApplication,
)
from PySide6.QtCore import Signal, Qt, QEvent, QTimer, QPoint, QPointF
from PySide6.QtGui import (
    QCursor, QTextCursor, QTextLayout, QTextOption, QPainter, QColor, QPen,
    QFont,
)

from .app_settings import Theme
from .i18n import t

ZWSP = "​"  # 零宽空格 U+200B,提供 QLabel 任意字符处的断行点

TEXT_MASK = "•••"  # 隐藏任务内容时的固定掩码:不泄露字数与行数

CHILD_INDENT = 16  # 子项相对父项的缩进宽度(与父项圆点直径同量级)


def wrap_for_label(text):
    """在文本的每个字符后插入零宽空格(U+200B),作为 QLabel 的断行点。

    QLabel.wordWrap 只在词边界换行;连续数字/英文等无空格长串没有
    断行点,会被当成一个词不换行、横向溢出。零宽空格提供"任意字符处
    可断行"的断点,但它零宽,渲染完全不可见,复制文本也不受影响。
    仅用于展示用的 label;store 里始终存原始文本。
    """
    # 逐字符拼接,跳过空白字符:空格/制表符本身就是断行点,不再在其后插 ZWSP。
    return "".join(
        ch if ch.isspace() else ch + ZWSP
        for ch in text
    )




class DotButton(QWidget):
    """自绘圆形完成按钮:悬停时圈内浮现对勾预览。"""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(t("task.mark_done"))
        self._hovered = False
        self._normal_color = QColor("#55555f")
        self._accent_color = QColor("#5ea0ff")
        self._pressed = False
        self.setMouseTracking(True)

    def set_theme(self, theme: Theme):
        self._normal_color = theme.icon_color
        self._accent_color = theme.accent_color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(2, 2, -2, -2)
        if self._hovered:
            p.setPen(QPen(self._accent_color, 1.8))
            acc = self._accent_color
            p.setBrush(QColor(acc.red(), acc.green(), acc.blue(), 42))
        else:
            p.setPen(QPen(self._normal_color, 1.5))
            p.setBrush(Qt.NoBrush)
        p.drawEllipse(r)
        if self._hovered:
            pen = QPen(self._accent_color, 1.6)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            cx, cy = self.width() / 2, self.height() / 2
            p.drawLine(QPointF(cx - 3.2, cy + 0.2), QPointF(cx - 0.8, cy + 2.6))
            p.drawLine(QPointF(cx - 0.8, cy + 2.6), QPointF(cx + 3.4, cy - 2.2))
        p.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            if self.rect().contains(event.position().toPoint()):
                self.clicked.emit()
            event.accept()
            return
        self._pressed = False
        super().mouseReleaseEvent(event)

class ChevronButton(QWidget):
    """折叠/展开子项的小箭头:展开朝下,折叠朝右。"""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFocusPolicy(Qt.NoFocus)
        self._expanded = True
        self._hovered = False
        self._color = QColor("#8e9099")
        self._accent_color = QColor("#5ea0ff")
        self.setMouseTracking(True)
        self._sync_tooltip()

    def set_theme(self, theme: Theme):
        self._color = theme.icon_color
        self._accent_color = theme.accent_color
        self.update()

    def set_expanded(self, expanded):
        if self._expanded != bool(expanded):
            self._expanded = bool(expanded)
            self._sync_tooltip()
            self.update()

    def _sync_tooltip(self):
        key = "task.collapse" if self._expanded else "task.expand"
        self.setToolTip(t(key))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = self._accent_color if self._hovered else self._color
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        if self._expanded:
            p.drawLine(QPointF(cx - 3.1, cy - 1.5), QPointF(cx, cy + 1.6))
            p.drawLine(QPointF(cx, cy + 1.6), QPointF(cx + 3.1, cy - 1.5))
        else:
            p.drawLine(QPointF(cx - 1.5, cy - 3.1), QPointF(cx + 1.6, cy))
            p.drawLine(QPointF(cx + 1.6, cy), QPointF(cx - 1.5, cy + 3.1))
        p.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class PlusButton(QWidget):
    """行尾的小加号:给这条任务新建一个子项。

    鼠标停在整行上时才显形(平时只占位、不绘制,避免每行尾巴都挂一个符号),
    所以是否画出来由 TaskItem 的悬停状态驱动,而不是它自己的 hover。
    """
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setFocusPolicy(Qt.NoFocus)
        self._available = True      # 这一行能不能加子项(子项行/锁定态不能)
        self._active = False        # 行被悬停时显形
        self._color = QColor("#8e9099")
        self.setToolTip(t("task.add_subtask"))
        self._sync_cursor()

    def set_theme(self, theme: Theme):
        self._color = theme.icon_color
        self.update()

    def set_available(self, available):
        available = bool(available)
        if available == self._available:
            return
        self._available = available
        self.setVisible(available)      # 不可用时彻底不占位,把宽度还给文字
        if not available:
            self._active = False
        self._sync_cursor()
        self.update()

    def set_active(self, active):
        active = bool(active) and self._available
        if active == self._active:
            return
        self._active = active
        self._sync_cursor()
        self.update()

    def _sync_cursor(self):
        shape = Qt.PointingHandCursor if self._active else Qt.ArrowCursor
        self.setCursor(QCursor(shape))

    def paintEvent(self, event):
        if not self._active:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self._color, 1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        r = 3.6
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._available:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class TaskItem(QWidget):
    """一行任务。

    - 点圆点 → completed(task_id)
    - 点右侧箭头 → collapse_toggled(task_id)
    - 鼠标停在行上时行尾出现小加号,点它 → subtask_requested(task_id)
    - 右键 → 编辑/折叠/删除 菜单;编辑提交且变化 → text_changed(task_id, text)
    - 编辑后文本被清空 → delete_requested(task_id)
    """

    completed = Signal(str)
    text_changed = Signal(str, str)
    delete_requested = Signal(str)
    collapse_toggled = Signal(str)
    subtask_requested = Signal(str)
    drag_started = Signal(str, QPoint)
    drag_moved = Signal(str, QPoint)
    drag_finished = Signal(str)

    _LABEL_PAGE, _EDIT_PAGE = 0, 1
    LONG_PRESS_MS = 450

    def __init__(self, task):
        super().__init__()
        self.task = task
        self._locked = False
        self._text_hidden = False  # 隐私模式:展示层用掩码替换任务文本
        self._hovered = False
        self._level = task.level          # 0 = 顶层,1 = 子项
        self._has_children = False
        self._collapsed = False
        self._fit_pending = False
        self._reset_edit_scroll_pending = False
        self._press_global_pos = None
        self._dragging = False
        self._sep_color = QColor(255, 255, 255, 8)
        self._hover_color = QColor(255, 255, 255, 6)
        self._guide_color = QColor(255, 255, 255, 26)
        self._drag_color = QColor(94, 160, 255, 110)
        self._text_color = QColor("#e9e9ef")
        self._font_family = "Segoe UI Variable"
        self._font_size = 13
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(self.LONG_PRESS_MS)
        self._long_press_timer.timeout.connect(self._activate_drag)

        lay = QHBoxLayout(self)
        self._layout = lay
        lay.setContentsMargins(12 + self._level * CHILD_INDENT, 7, 12, 7)
        lay.setSpacing(10)

        # 圆点:QPainter 手绘正圆
        self.dot = DotButton()
        self.dot.clicked.connect(lambda: self.completed.emit(self.task.id))
        lay.addWidget(self.dot)

        # 文字:展示用 QLabel;编辑用 QPlainTextEdit 懒创建(首次进入编辑才实例化,
        # 避免每行都背一个重量级文本编辑器)。样式统一由容器级 QSS 提供。
        self.stack = QStackedWidget()
        self.stack.setObjectName("taskStack")
        self.stack.setFrameShape(QFrame.NoFrame)
        self.stack.setMinimumWidth(0)
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.label = QLabel(self._display_text())
        self.label.setObjectName("taskText")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setTextInteractionFlags(Qt.NoTextInteraction)
        # Ignored 使 label 的 minimumSizeHint(长串时为整行宽度)不参与布局。
        # 连续数字/英文等无空格长串之所以能换行,靠 wrap_for_label 注入的
        # 零宽空格(U+200B)提供断行点——QLabel.wordWrap 只在词边界换行,
        # 没有断行点的纯数字串会被当成一个整体词,撑到内容宽度。
        self.label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.label.setMinimumWidth(0)
        self.label.setMaximumWidth(16777215)
        self.label.setCursor(QCursor(Qt.IBeamCursor))
        self.label.installEventFilter(self)

        self.edit = None  # 懒创建,见 _ensure_edit()

        self.stack.addWidget(self.label)
        self.stack.setCurrentIndex(self._LABEL_PAGE)
        lay.addWidget(self.stack, 1)

        # 新建子项的加号:常驻占位,鼠标停在行上才画出来
        self.plus = PlusButton()
        self.plus.clicked.connect(lambda: self.subtask_requested.emit(self.task.id))
        lay.addWidget(self.plus)

        # 折叠箭头:只有父项才显示,放在加号右侧(隐藏时不占位)
        self.chev = ChevronButton()
        self.chev.clicked.connect(lambda: self.collapse_toggled.emit(self.task.id))
        self.chev.setVisible(False)
        lay.addWidget(self.chev)
        self._sync_plus()   # 子项建出来就没有下一层,先按初始层级定好占位

    # ---- 隐藏文本(隐私模式) ----
    def _display_text(self):
        """展示层文本:隐藏态用固定掩码,否则原文+断行零宽空格。"""
        if self._text_hidden:
            return TEXT_MASK
        return wrap_for_label(self.task.text or "")

    def set_text_hidden(self, hidden):
        self._text_hidden = hidden
        self.label.setText(self._display_text())
        self._schedule_fit_height()

    # ---- 层级(父项 / 子项)----
    @property
    def level(self):
        return self._level

    def set_tree_state(self, level, has_children, collapsed):
        """更新缩进、折叠箭头与父项字重。

        缩进只改左边距,子项因此共享父项的行高逻辑;父项加粗让"标题行"
        在一屏任务里能被一眼区分出来。
        """
        level = 1 if level else 0
        has_children = bool(has_children)
        collapsed = bool(collapsed)
        if (
            level == self._level
            and has_children == self._has_children
            and collapsed == self._collapsed
        ):
            return
        self._level = level
        self._has_children = has_children
        self._collapsed = collapsed
        m = self._layout.contentsMargins()
        left = 12 + level * CHILD_INDENT
        if m.left() != left:
            self._layout.setContentsMargins(left, m.top(), m.right(), m.bottom())
        self._apply_label_weight()
        self.chev.set_expanded(not self._collapsed)
        self.chev.setVisible(self._has_children and not self._locked)
        self._sync_plus()
        # 缩进、箭头、加号都会改变文字可用宽度,必须重新按宽度算一次行高:
        # 否则"刚变成父项"那一下箭头挤掉 26px,长文本会被裁掉最后一行。
        self._schedule_fit_height()
        self.update()

    def set_level(self, level):
        """拖拽时实时预览缩进层级,其余树状态保持不变。"""
        self.set_tree_state(level, self._has_children, self._collapsed)

    def _sync_plus(self):
        """行尾加号:子项行没有下一层,锁定态不可编辑,这两种情况都不占位。"""
        available = self._level == 0 and not self._locked
        self.plus.set_available(available)
        self.plus.set_active(available and self._hovered)

    def _apply_label_weight(self):
        font = QFont(self._font_family)
        font.setPixelSize(self._font_size)
        if self._has_children:
            font.setWeight(QFont.DemiBold)
        self.label.setFont(font)
        if self.edit is not None:
            self.edit.setFont(font)

    # ---- 分隔线 + 悬停 ----
    def _highlight_rect(self):
        """悬停/拖拽底框:子项跟着内容一起缩进,否则左边会多出一截对不齐。"""
        left = 4 + self._level * CHILD_INDENT
        return self.rect().adjusted(left, 0, -4, 0)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._level > 0:
            # 子项左侧的竖线:窗口滚动到看不见父项时,仍能看出这段是同一个分组
            x = self._layout.contentsMargins().left() - CHILD_INDENT / 2
            p.setPen(self._guide_color)
            p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        if self._dragging:
            fill = QColor(
                self._drag_color.red(), self._drag_color.green(),
                self._drag_color.blue(), 34,
            )
            p.setPen(QPen(self._drag_color, 1))
            p.setBrush(fill)
            p.drawRoundedRect(self._highlight_rect(), 9, 9)
        elif self._hovered and self.stack.currentIndex() == self._LABEL_PAGE:
            p.setPen(Qt.NoPen)
            p.setBrush(self._hover_color)
            # 从 y=0 开始绘制:分隔线画在上一项的底部,若高亮顶部内缩
            # 会与上方分隔线之间露出缝隙。
            p.drawRoundedRect(self._highlight_rect(), 9, 9)
        p.setPen(self._sep_color)
        p.drawLine(
            self._separator_left(), self.height() - 1,
            self.width() - 12, self.height() - 1,
        )
        p.end()

    def _separator_left(self):
        """分隔线跟随文本区域，圆点隐藏后自动向左延伸。"""
        return self.stack.geometry().left()

    def enterEvent(self, event):
        self._hovered = True
        self._sync_plus()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # 只按 Qt 的 Enter/Leave 判悬停:光标移到圆点/箭头/加号这些子控件上时,
        # Qt 不会给整行发 Leave,所以这里可以放心无条件清掉。
        # (曾经在这里用 QCursor.pos() 做二次判断——鼠标贴着行边界缓慢移动时,
        #  取到的位置往往还在旧行里,Leave 被吞掉,结果一路划过去每行都亮着。)
        self._hovered = False
        self._sync_plus()
        self.update()
        super().leaveEvent(event)

    # ---- 主题 ----
    def set_theme(self, theme: Theme):
        self._sep_color = theme.sep_color
        self._hover_color = theme.highlight_color
        self._guide_color = QColor(
            theme.icon_color.red(), theme.icon_color.green(),
            theme.icon_color.blue(), 26,
        )
        self._drag_color = QColor(
            theme.accent_color.red(), theme.accent_color.green(),
            theme.accent_color.blue(), 110,
        )
        self._text_color = theme.text_color
        self._font_family = theme.font_family
        self._font_size = theme.font_size
        self.dot.set_theme(theme)
        self.chev.set_theme(theme)
        self.plus.set_theme(theme)
        self._apply_label_weight()
        self._schedule_fit_height()
        self.update()

    # ---- 编辑 ----
    def _ensure_edit(self):
        """懒创建编辑框:首次进入编辑才实例化。

        大量任务行通常只有少数会被编辑,平时不背重量级的
        QPlainTextEdit(含独立文档模型),显著降低内存占用。
        """
        if self.edit is not None:
            return self.edit
        edit = QPlainTextEdit(self.task.text)
        edit.setObjectName("taskEdit")
        edit.setPlaceholderText(t("task.edit_placeholder"))
        edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        edit.setMinimumWidth(0)
        edit.setFixedHeight(edit.fontMetrics().lineSpacing() + 14)
        edit.installEventFilter(self)
        edit.textChanged.connect(self._fit_edit_height)
        self.stack.addWidget(edit)
        self.edit = edit
        self._apply_label_weight()  # 父项编辑时保持同样的加粗观感
        return edit

    def start_edit(self):
        """进入编辑态(右键菜单/新建任务/测试均调用)。"""
        if self._locked:
            return
        if self._dragging:
            self._finish_drag_gesture()
        else:
            self._cancel_drag_gesture()
        self._ensure_edit()
        self._reset_edit_scroll_pending = True
        self.stack.setCurrentIndex(self._EDIT_PAGE)
        self.edit.setPlainText(self.task.text)
        self.edit.setFocus()
        self.edit.moveCursor(QTextCursor.End)
        self._fit_edit_height()
        self._schedule_fit_height()

    def focus_edit(self):
        """兼容旧调用。"""
        self.start_edit()

    def _on_editing_finished(self):
        if self.stack.currentIndex() != self._EDIT_PAGE:
            return
        text = self.edit.toPlainText().strip()
        if text == "":
            self._exit_edit()
            self.delete_requested.emit(self.task.id)
        elif text != self.task.text:
            self.task.text = text
            self.label.setText(self._display_text())
            self._exit_edit()
            self.text_changed.emit(self.task.id, text)
        else:
            self._exit_edit()

    def _exit_edit(self):
        self._reset_edit_scroll_pending = False
        self.stack.setCurrentIndex(self._LABEL_PAGE)
        self.stack.setMinimumHeight(0)
        self.stack.setMaximumHeight(16777215)
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self._fit_label_height()
        self._schedule_fit_height()

    def _side_space(self):
        """圆点/折叠箭头/加号占用的横向空间;隐藏后布局不再为它们留位。

        用状态位而非 isVisible() 判断:窗口还没显示时子控件的 isVisible()
        一律为 False,会让行高算少、文本被裁。
        """
        if self._locked:
            return 0
        space = self.dot.width() + self._layout.spacing()
        if self._has_children:
            space += self.chev.width() + self._layout.spacing()
        if self._level == 0:
            space += self.plus.width() + self._layout.spacing()
        return space

    def _fit_label_height(self):
        """展示态按当前宽度换行，避免缩窄窗口时裁掉任务文本。"""
        m = self._layout.contentsMargins()
        w = self.width() - m.left() - m.right() - self._side_space()
        text_width = max(w, 40)
        # 重置高度约束(setFixedHeight 会污染 heightForWidth 的返回值!)
        self.label.setMinimumHeight(0)
        self.label.setMaximumHeight(16777215)
        label_h = max(
            self.label.heightForWidth(text_width),
            self.label.fontMetrics().lineSpacing() + 4,
        )
        row_h = max(label_h, self.dot.height()) + m.top() + m.bottom()
        self.label.setFixedHeight(label_h)
        self.stack.setFixedHeight(label_h)
        self.setFixedHeight(row_h)
        self.updateGeometry()

    def _fit_edit_height(self):
        """编辑框按当前宽度自动换行，并完整容纳全部文本。"""
        line_h = self.edit.fontMetrics().lineSpacing()
        m = self._layout.contentsMargins()
        w = self.width() - m.left() - m.right() - self._side_space()
        viewport_w = self.edit.viewport().width()
        if viewport_w < 40:
            viewport_w = max(self.stack.width() - 16, w - 16, 40)
        document_margin = self.edit.document().documentMargin()
        text_width = max(viewport_w - int(document_margin * 2), 40)
        self.edit.setMinimumHeight(0)
        self.edit.setMaximumHeight(16777215)
        text_h = self._wrapped_text_height(text_width)
        chrome_h = max(12, self.edit.height() - self.edit.viewport().height())
        new_h = max(
            text_h + int(document_margin * 2) + chrome_h,
            line_h + int(document_margin * 2) + chrome_h,
        ) + 1
        row_h = max(new_h, self.dot.height()) + m.top() + m.bottom()
        self.edit.setMinimumHeight(new_h)
        self.edit.setMaximumHeight(new_h)
        self.stack.setMinimumHeight(new_h)
        self.stack.setMaximumHeight(new_h)
        self.setMinimumHeight(row_h)
        self.setMaximumHeight(row_h)
        self.updateGeometry()

    def _wrapped_text_height(self, text_width):
        """按编辑器实际字体和换行规则计算所有可视文本行高度。"""
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        line_h = self.edit.fontMetrics().lineSpacing()
        total = 0
        for block_text in self.edit.toPlainText().split("\n"):
            layout = QTextLayout(block_text or " ", self.edit.font())
            layout.setTextOption(option)
            layout.beginLayout()
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(text_width)
                total += max(line_h, int(line.height() + 0.999))
            layout.endLayout()
        return max(total, line_h)

    def _schedule_fit_height(self):
        if self._fit_pending:
            return
        self._fit_pending = True
        QTimer.singleShot(0, self._run_scheduled_fit)

    def _run_scheduled_fit(self):
        self._fit_pending = False
        if self.stack.currentIndex() == self._EDIT_PAGE:
            self._fit_edit_height()
            if self._reset_edit_scroll_pending:
                self.edit.verticalScrollBar().setValue(0)
                self._reset_edit_scroll_pending = False
        else:
            self._fit_label_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._schedule_fit_height()

    def eventFilter(self, obj, event):
        if obj is self.label:
            et = event.type()
            if et == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self._cancel_drag_gesture()
                self.start_edit()
                return True
            if (
                et == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
                and not self._locked
                and self.stack.currentIndex() == self._LABEL_PAGE
            ):
                self._press_global_pos = event.globalPosition().toPoint()
                self._long_press_timer.start()
                return True
            if et == QEvent.MouseMove and self._press_global_pos is not None:
                global_pos = event.globalPosition().toPoint()
                if self._dragging and event.buttons() & Qt.LeftButton:
                    self.drag_moved.emit(self.task.id, global_pos)
                    return True
                distance = (global_pos - self._press_global_pos).manhattanLength()
                if distance > QApplication.startDragDistance():
                    self._cancel_drag_gesture()
                return True
            if et == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                if self._press_global_pos is not None or self._dragging:
                    self._finish_drag_gesture()
                    return True
        if obj is getattr(self, "edit", None):
            if event.type() == QEvent.FocusOut:
                self._on_editing_finished()
                return False
            if event.type() == QEvent.KeyPress:
                if event.key() in (Qt.Key_Enter, Qt.Key_Return):
                    if event.modifiers() & Qt.ShiftModifier:
                        return False
                    self._on_editing_finished()
                    return True
                if event.key() == Qt.Key_Escape:
                    self._exit_edit()
                    return True
        return super().eventFilter(obj, event)

    def _activate_drag(self):
        if self._press_global_pos is None or self._locked:
            return
        self._dragging = True
        self.label.setCursor(QCursor(Qt.ClosedHandCursor))
        self.drag_started.emit(self.task.id, self._press_global_pos)
        self.update()

    def _cancel_drag_gesture(self):
        self._long_press_timer.stop()
        self._press_global_pos = None

    def _finish_drag_gesture(self):
        was_dragging = self._dragging
        self._dragging = False
        self._cancel_drag_gesture()
        self.label.setCursor(QCursor(Qt.ArrowCursor if self._locked else Qt.IBeamCursor))
        self.update()
        if was_dragging:
            self.drag_finished.emit(self.task.id)

    # ---- 右键菜单(仅展示态;编辑态让 QPlainTextEdit 自带菜单处理)----
    def contextMenuEvent(self, event):
        if self._locked:
            event.ignore()
            return
        if self.stack.currentIndex() == self._EDIT_PAGE:
            event.ignore()
            return
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(40, 41, 46, 245);
                border: 1px solid rgba(255,255,255,16);
                border-radius: 9px;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 22px;
                color: #e9e9ef;
                font-size: 12px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background: rgba(94, 160, 255, 60);
                color: #ffffff;
            }
        """)
        act_edit = menu.addAction(t("task.edit"))
        act_collapse = None
        if self._has_children:
            act_collapse = menu.addAction(
                t("task.expand") if self._collapsed else t("task.collapse")
            )
        menu.addSeparator()
        act_del = menu.addAction(t("task.delete"))
        chosen = menu.exec(event.globalPos())
        if chosen is act_edit:
            self.start_edit()
        elif act_collapse is not None and chosen is act_collapse:
            self.collapse_toggled.emit(self.task.id)
        elif chosen is act_del:
            self.delete_requested.emit(self.task.id)
        event.accept()

    # ---- 锁定 ----
    def set_locked(self, locked):
        if locked and self._dragging:
            self._finish_drag_gesture()
        else:
            self._cancel_drag_gesture()
        self._locked = locked
        self.dot.setVisible(not locked)
        self.chev.setVisible(self._has_children and not locked)
        self._sync_plus()
        self.label.setCursor(QCursor(Qt.ArrowCursor if locked else Qt.IBeamCursor))
        if locked and self.stack.currentIndex() == self._EDIT_PAGE:
            self._on_editing_finished()  # 提交而非丢弃已输入的文本
        self._schedule_fit_height()  # 圆点显隐后重算文本宽度与行高
        self.update()
