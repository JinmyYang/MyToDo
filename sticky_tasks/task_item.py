"""单个任务项:圆点(点击完成)+ 文字(右键编辑/删除)+ 锁定开锁。"""

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

ZWSP = "​"  # 零宽空格 U+200B,提供 QLabel 任意字符处的断行点


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
        self.setToolTip("标记为完成")
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

class TaskItem(QWidget):
    """一行任务。

    - 点圆点 → completed(task_id)
    - 右键 → 编辑/删除 菜单;编辑提交且变化 → text_changed(task_id, text)
    - 编辑后文本被清空 → delete_requested(task_id)
    """

    completed = Signal(str)
    text_changed = Signal(str, str)
    delete_requested = Signal(str)
    drag_started = Signal(str, QPoint)
    drag_moved = Signal(str, QPoint)
    drag_finished = Signal(str)

    _LABEL_PAGE, _EDIT_PAGE = 0, 1
    LONG_PRESS_MS = 450

    def __init__(self, task):
        super().__init__()
        self.task = task
        self._locked = False
        self._hovered = False
        self._fit_pending = False
        self._reset_edit_scroll_pending = False
        self._press_global_pos = None
        self._dragging = False
        self._sep_color = QColor(255, 255, 255, 8)
        self._hover_color = QColor(255, 255, 255, 6)
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
        lay.setContentsMargins(12, 7, 12, 7)
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

        self.label = QLabel(wrap_for_label(task.text or ""))
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

    # ---- 分隔线 + 悬停 ----
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._dragging:
            fill = QColor(
                self._drag_color.red(), self._drag_color.green(),
                self._drag_color.blue(), 34,
            )
            p.setPen(QPen(self._drag_color, 1))
            p.setBrush(fill)
            p.drawRoundedRect(self.rect().adjusted(4, 0, -4, 0), 9, 9)
        elif self._hovered and self.stack.currentIndex() == self._LABEL_PAGE:
            p.setPen(Qt.NoPen)
            p.setBrush(self._hover_color)
            # 从 y=0 开始绘制:分隔线画在上一项的底部,若高亮顶部内缩
            # 会与上方分隔线之间露出缝隙。
            p.drawRoundedRect(self.rect().adjusted(4, 0, -4, 0), 9, 9)
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
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    # ---- 主题 ----
    def set_theme(self, theme: Theme):
        self._sep_color = theme.sep_color
        self._hover_color = theme.highlight_color
        self._drag_color = QColor(
            theme.accent_color.red(), theme.accent_color.green(),
            theme.accent_color.blue(), 110,
        )
        self._text_color = theme.text_color
        self._font_family = theme.font_family
        self._font_size = theme.font_size
        self.dot.set_theme(theme)
        font = QFont(theme.font_family)
        font.setPixelSize(theme.font_size)
        self.label.setFont(font)
        if self.edit is not None:
            self.edit.setFont(font)
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
        edit.setPlaceholderText("输入任务…")
        edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        edit.setMinimumWidth(0)
        edit.setFixedHeight(edit.fontMetrics().lineSpacing() + 14)
        edit.installEventFilter(self)
        edit.textChanged.connect(self._fit_edit_height)
        font = QFont(self._font_family)
        font.setPixelSize(self._font_size)
        edit.setFont(font)
        self.stack.addWidget(edit)
        self.edit = edit
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
            self.label.setText(wrap_for_label(text))
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

    def _dot_space(self):
        """圆点占用的横向空间;锁定后圆点隐藏,布局不再为它留位。"""
        return 0 if self._locked else self.dot.width() + self._layout.spacing()

    def _fit_label_height(self):
        """展示态按当前宽度换行，避免缩窄窗口时裁掉任务文本。"""
        m = self._layout.contentsMargins()
        w = self.width() - m.left() - m.right() - self._dot_space()
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
        w = self.width() - m.left() - m.right() - self._dot_space()
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
        act_edit = menu.addAction("编辑")
        act_del = menu.addAction("删除")
        chosen = menu.exec(event.globalPos())
        if chosen is act_edit:
            self.start_edit()
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
        self.label.setCursor(QCursor(Qt.ArrowCursor if locked else Qt.IBeamCursor))
        if locked and self.stack.currentIndex() == self._EDIT_PAGE:
            self._on_editing_finished()  # 提交而非丢弃已输入的文本
        self._schedule_fit_height()  # 圆点显隐后重算文本宽度与行高
        self.update()
