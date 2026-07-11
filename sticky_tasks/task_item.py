"""单个任务项:左侧圆点(点击完成)+ 可编辑文本。"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor


class TaskItem(QWidget):
    """一行任务。

    - 点圆点 → 发 completed(task_id)
    - 文本编辑完成且变化 → 发 text_changed(task_id, text)
    - 文本被清空 → 发 delete_requested(task_id)
    """

    completed = Signal(str)
    text_changed = Signal(str, str)
    delete_requested = Signal(str)

    def __init__(self, task):
        super().__init__()
        self.task = task

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(8)

        self.dot = QPushButton()
        self.dot.setObjectName("taskDot")
        self.dot.setFixedSize(18, 18)
        self.dot.setCursor(QCursor(Qt.PointingHandCursor))
        # 不抢焦点:点圆点时不会触发文本框失焦保存,避免完成与保存逻辑冲突
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

        self.edit = QLineEdit(task.text)
        self.edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #f1f3f4;
                font-size: 14px;
                padding: 2px 0px;
            }
            QLineEdit:focus { border-bottom: 1px solid #1a73e8; }
        """)
        self.edit.setPlaceholderText("输入任务…")
        self.edit.editingFinished.connect(self._on_editing_finished)

        lay.addWidget(self.dot)
        lay.addWidget(self.edit, 1)

    def _on_editing_finished(self):
        text = self.edit.text().strip()
        if text == "":
            self.delete_requested.emit(self.task.id)
        elif text != self.task.text:
            # 本地同步,避免重复触发时再次发信号
            self.task.text = text
            self.text_changed.emit(self.task.id, text)

    def focus_edit(self):
        self.edit.setFocus()
        self.edit.selectAll()
