"""单个任务项:圆点(点击完成)+ 文字(右键编辑/删除)+ 锁定开锁。"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QStackedWidget,
    QMenu, QFrame, QPlainTextEdit, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QEvent, QTimer, QRect
from PySide6.QtGui import QCursor, QTextCursor, QPainter, QColor


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
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        lay = QHBoxLayout(self)
        self._layout = lay
        lay.setContentsMargins(14, 6, 14, 6)
        lay.setSpacing(10)

        # 圆点:点击完成(NoFocus,不抢文本框焦点,避免完成与保存逻辑冲突)
        self.dot = QPushButton()
        self.dot.setObjectName("taskDot")
        self.dot.setFixedSize(19, 19)
        self.dot.setCursor(QCursor(Qt.PointingHandCursor))
        self.dot.setFocusPolicy(Qt.NoFocus)
        self.dot.setToolTip("标记为完成")
        self.dot.setStyleSheet("""
    QPushButton#taskDot {
        border: 1.5px solid #63636b;
        border-radius: 9px;
        background: transparent;
    }
    QPushButton#taskDot:hover {
        border-color: #0a84ff;
        background: rgba(10,132,255,60);
    }
    QPushButton#taskDot:pressed { background: #0a84ff; }
""")
        self.dot.clicked.connect(lambda checked=False: self.completed.emit(self.task.id))
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
        color: #f1f3f4;
        font-size: 14px;
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
        background: rgba(255,255,255,16);
        border: 1px solid #0a84ff;
        border-radius: 8px;
        color: #f1f3f4;
        font-size: 14px;
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
            p.fillRect(self.rect(), QColor(255, 255, 255, 7))
        p.setPen(QColor(255, 255, 255, 10))
        p.drawLine(14, self.height() - 1, self.width() - 14, self.height() - 1)
        p.end()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

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
                background: rgba(45, 46, 50, 240);
                border: 1px solid rgba(255,255,255,18);
                border-radius: 8px;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 24px;
                color: #f1f3f4;
                font-size: 13px;
            }
            QMenu::item:selected {
                background: #0a84ff;
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
