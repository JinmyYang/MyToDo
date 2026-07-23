"""单个任务项:圆点(点击完成)+ 文字(右键编辑/删除)+ 锁定开锁。"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QStackedWidget,
    QMenu, QFrame, QPlainTextEdit, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QEvent, QTimer, QRect, QPointF
from PySide6.QtGui import QCursor, QTextCursor, QPainter, QColor, QPen

from .app_settings import Theme




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
            self.clicked.emit()

class TaskItem(QWidget):
    """一行任务。

    - 点圆点 → completed(task_id)
    - 右键 → 编辑/删除 菜单;编辑提交且变化 → text_changed(task_id, text)
    - 编辑后文本被清空 → delete_requested(task_id)
    """

    completed = Signal(str)
    text_changed = Signal(str, str)
    delete_requested = Signal(str)

    _LABEL_PAGE, _EDIT_PAGE = 0, 1

    def __init__(self, task):
        super().__init__()
        self.task = task
        self._locked = False
        self._hovered = False
        self._fit_pending = False
        self._sep_color = QColor(255, 255, 255, 8)
        self._hover_color = QColor(255, 255, 255, 6)
        self._text_color = QColor("#e9e9ef")
        self._font_family = "Segoe UI Variable"
        self._font_size = 13
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        lay = QHBoxLayout(self)
        self._layout = lay
        lay.setContentsMargins(12, 7, 12, 7)
        lay.setSpacing(10)

        # 圆点:QPainter 手绘正圆
        self.dot = DotButton()
        self.dot.clicked.connect(lambda: self.completed.emit(self.task.id))
        lay.addWidget(self.dot)

        # 文字:展示用 QLabel + 编辑用 QPlainTextEdit,同位置切换避免布局抖动
        self.stack = QStackedWidget()
        self.stack.setObjectName("taskStack")
        self.stack.setFrameShape(QFrame.NoFrame)
        self.stack.setMinimumWidth(0)
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        # 透明背景,透出容器深色(避免 Windows 下 QStackedWidget 默认白底)
        self.stack.setStyleSheet("QStackedWidget#taskStack { background: transparent; }")

        self.label = QLabel(task.text or "")
        self.label.setObjectName("taskText")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setTextInteractionFlags(Qt.NoTextInteraction)
        self.label.setMinimumWidth(0)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.label.setStyleSheet("""
    QLabel#taskText {
        background: transparent;
        border: none;
        color: #e9e9ef;
        font-size: 13px;
        padding: 0px;
    }
""")

        self.edit = QPlainTextEdit(task.text)
        self.edit.setObjectName("taskEdit")
        self.edit.setPlaceholderText("输入任务…")
        self.edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.edit.setMinimumWidth(0)
        self.edit.setStyleSheet("""
    QPlainTextEdit#taskEdit {
        background: rgba(255,255,255,12);
        border: 1px solid rgba(94, 160, 255, 140);
        border-radius: 8px;
        color: #f2f2f6;
        font-size: 13px;
        padding: 5px 7px;
    }
""")
        initial_edit_h = self.edit.fontMetrics().lineSpacing() + 14
        self.edit.setFixedHeight(initial_edit_h)
        self.edit.installEventFilter(self)
        self.edit.textChanged.connect(self._fit_edit_height)

        self.stack.addWidget(self.label)
        self.stack.addWidget(self.edit)
        self.stack.setCurrentIndex(self._LABEL_PAGE)
        lay.addWidget(self.stack, 1)

    # ---- 分隔线 + 悬停 ----
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._hovered and self.stack.currentIndex() == self._LABEL_PAGE:
            p.setPen(Qt.NoPen)
            p.setBrush(self._hover_color)
            p.drawRoundedRect(self.rect().adjusted(4, 1, -4, 0), 9, 9)
        p.setPen(self._sep_color)
        p.drawLine(40, self.height() - 1, self.width() - 12, self.height() - 1)
        p.end()

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
        self._text_color = theme.text_color
        self._font_family = theme.font_family
        self._font_size = theme.font_size
        self.dot.set_theme(theme)
        fs = theme.font_size
        ff = theme.font_family
        tc = theme.text_color.name()
        self.label.setStyleSheet(f"""
    QLabel#taskText {{
        background: transparent;
        border: none;
        color: {tc};
        font-size: {fs}px;
        font-family: "{ff}";
        padding: 0px;
    }}
""")
        acc = theme.accent_color
        self.edit.setStyleSheet(f"""
    QPlainTextEdit#taskEdit {{
        background: rgba({theme.highlight_color.red()},{theme.highlight_color.green()},{theme.highlight_color.blue()},12);
        border: 1px solid rgba({acc.red()}, {acc.green()}, {acc.blue()}, 140);
        border-radius: 8px;
        color: {tc};
        font-size: {fs}px;
        font-family: "{ff}";
        padding: 5px 7px;
    }}
""")
        self._schedule_fit_height()
        self.update()

    # ---- 编辑 ----
    def start_edit(self):
        """进入编辑态(右键菜单/新建任务/测试均调用)。"""
        if self._locked:
            return
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
            self.label.setText(text)
            self._exit_edit()
            self.text_changed.emit(self.task.id, text)
        else:
            self._exit_edit()

    def _exit_edit(self):
        self.stack.setCurrentIndex(self._LABEL_PAGE)
        self.stack.setMinimumHeight(0)
        self.stack.setMaximumHeight(16777215)
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self._fit_label_height()
        self._schedule_fit_height()

    def _fit_label_height(self):
        """展示态按当前宽度换行，避免缩窄窗口时裁掉任务文本。"""
        m = self._layout.contentsMargins()
        w = self.width() - m.left() - m.right() - self._layout.spacing() - self.dot.width()
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
        w = self.width() - m.left() - m.right() - self._layout.spacing() - self.dot.width()
        text_width = max(self.edit.viewport().width() - 2, self.stack.width() - 14, w - 14, 40)
        self.edit.setMinimumHeight(0)
        self.edit.setMaximumHeight(16777215)
        flags = Qt.TextWordWrap | Qt.TextWrapAnywhere
        text = self.edit.toPlainText() or " "
        wrapped_h = self.edit.fontMetrics().boundingRect(
            QRect(0, 0, text_width, 0), flags, text,
        ).height()
        doc_h = self.edit.document().size().height()
        block_count = self.edit.document().blockCount()
        text_h = max(wrapped_h, int(doc_h), block_count * line_h)
        new_h = max(text_h + 14, line_h + 14)
        row_h = max(new_h, self.dot.height()) + m.top() + m.bottom()
        self.edit.setMinimumHeight(new_h)
        self.edit.setMaximumHeight(new_h)
        self.stack.setMinimumHeight(new_h)
        self.stack.setMaximumHeight(new_h)
        self.setMinimumHeight(row_h)
        self.setMaximumHeight(row_h)
        self.updateGeometry()

    def _schedule_fit_height(self):
        if self._fit_pending:
            return
        self._fit_pending = True
        QTimer.singleShot(0, self._run_scheduled_fit)

    def _run_scheduled_fit(self):
        self._fit_pending = False
        if self.stack.currentIndex() == self._EDIT_PAGE:
            self._fit_edit_height()
        else:
            self._fit_label_height()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._schedule_fit_height()

    def eventFilter(self, obj, event):
        if obj is self.edit:
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
        self._locked = locked
        self.dot.setVisible(not locked)
        if locked and self.stack.currentIndex() == self._EDIT_PAGE:
            self._exit_edit()
        self.update()
