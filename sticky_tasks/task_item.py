"""单个任务项:圆点(点击完成)+ 文字(右键编辑/删除)+ 锁定开锁。"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel, QStackedWidget,
    QMenu, QFrame,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor


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

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(8)

        # 圆点:点击完成(NoFocus,不抢文本框焦点,避免完成与保存逻辑冲突)
        self.dot = QPushButton()
        self.dot.setObjectName("taskDot")
        self.dot.setFixedSize(18, 18)
        self.dot.setCursor(QCursor(Qt.PointingHandCursor))
        self.dot.setFocusPolicy(Qt.NoFocus)
        self.dot.setToolTip("标记为完成")
        self.dot.setStyleSheet("""
            QPushButton#taskDot {
                border: 2px solid #9aa0a6;
                border-radius: 9px;
                background: transparent;
            }
            QPushButton#taskDot:hover {
                border-color: #1a73e8;
                background: rgba(26,115,232,40);
            }
        """)
        self.dot.clicked.connect(lambda checked=False: self.completed.emit(self.task.id))
        lay.addWidget(self.dot)

        # 文字:展示用 QLabel + 编辑用 QLineEdit,同位置切换避免布局抖动
        self.stack = QStackedWidget()
        self.stack.setObjectName("taskStack")
        self.stack.setFrameShape(QFrame.NoFrame)
        # 透明背景,透出容器深色(避免 Windows 下 QStackedWidget 默认白底)
        self.stack.setStyleSheet("QStackedWidget#taskStack { background: transparent; }")

        self.label = QLabel(task.text or "")
        self.label.setObjectName("taskText")
        self.label.setWordWrap(False)
        self.label.setTextFormat(Qt.PlainText)
        self.label.setTextInteractionFlags(Qt.NoTextInteraction)
        # 透明背景,继承容器深色(解决纯白底问题)
        self.label.setStyleSheet("""
            QLabel#taskText {
                background: transparent;
                border: none;
                color: #f1f3f4;
                font-size: 14px;
                padding: 2px 0px;
            }
        """)

        self.edit = QLineEdit(task.text)
        self.edit.setObjectName("taskEdit")
        self.edit.setPlaceholderText("输入任务…")
        # 编辑态用深色叠加底,绕开 Windows 透明 QLineEdit 渲染白底的问题
        self.edit.setStyleSheet("""
            QLineEdit#taskEdit {
                background: rgba(255,255,255,20);
                border: 1px solid #1a73e8;
                border-radius: 4px;
                color: #f1f3f4;
                font-size: 14px;
                padding: 2px 4px;
            }
        """)
        self.edit.editingFinished.connect(self._on_editing_finished)

        self.stack.addWidget(self.label)
        self.stack.addWidget(self.edit)
        self.stack.setCurrentIndex(self._LABEL_PAGE)
        lay.addWidget(self.stack, 1)

    # ---- 编辑 ----
    def start_edit(self):
        """进入编辑态(右键菜单/新建任务/测试均调用)。"""
        if self._locked:
            return
        self.stack.setCurrentIndex(self._EDIT_PAGE)
        self.edit.setText(self.task.text)
        self.edit.setFocus()
        self.edit.selectAll()

    def focus_edit(self):
        """兼容旧调用。"""
        self.start_edit()

    def _on_editing_finished(self):
        # 重入守卫:切回 label 会隐藏 edit 触发失焦,再次进入此槽
        if self.stack.currentIndex() != self._EDIT_PAGE:
            return
        text = self.edit.text().strip()
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

    # ---- 右键菜单(仅展示态;编辑态让 QLineEdit 自带菜单处理)----
    def contextMenuEvent(self, event):
        if self._locked:
            event.ignore()
            return
        if self.stack.currentIndex() == self._EDIT_PAGE:
            event.ignore()
            return
        menu = QMenu(self)
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
