"""已完成任务面板:列出已完成任务,可恢复或右键删除。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QScrollArea,
    QMenu, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor

PANEL_QSS = """
CompletedPanel { background: transparent; }
QFrame#completedItem {
    background: transparent;
    border-radius: 6px;
    margin: 2px 10px;
}
QFrame#completedItem:hover {
    background: rgba(255,255,255,12);
}
QLabel#doneText { color: #9aa0a6; font-size: 12px; }
QLabel#doneTextDone { color: #9aa0a6; font-size: 12px; text-decoration: line-through; }
QPushButton#restoreBtn {
    color: #9aa0a6; background: transparent; border: none;
    padding: 2px 6px; font-size: 14px;
}
QPushButton#restoreBtn:hover { color: #1a73e8; }
QScrollArea { border: none; background: transparent; }
QScrollArea viewport { background: transparent; }
QWidget#bodyContainer { background: transparent; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,50); border-radius: 3px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class _CompletedRow(QFrame):
    """已完成任务行:右键弹出删除菜单。"""

    delete_requested = Signal(str)

    def __init__(self, task_id):
        super().__init__()
        self.setObjectName("completedItem")
        self._task_id = task_id

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_del = menu.addAction("删除")
        if menu.exec(event.globalPos()) is act_del:
            self.delete_requested.emit(self._task_id)


class CompletedPanel(QWidget):
    restored = Signal(str)  # task_id
    deleted = Signal(str)   # task_id

    def __init__(self):
        super().__init__()
        self.setStyleSheet(PANEL_QSS)
        self.setMaximumHeight(160)
        self._row_for = {}

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 8, 0, 4)
        v.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body_container = QWidget()
        self.body_container.setObjectName("bodyContainer")
        self.body = QVBoxLayout(self.body_container)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        self.body.addStretch()  # 末尾占位,任务顶对齐
        self.scroll.setWidget(self.body_container)
        v.addWidget(self.scroll, 1)

    def set_tasks(self, tasks):
        # 清空旧行(保留末尾 stretch)
        while self.body.count() > 1:
            item = self.body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._row_for.clear()
        for t in tasks:
            row = self._make_row(t)
            self.body.insertWidget(self.body.count() - 1, row)
            self._row_for[t.id] = row


    def _make_row(self, task):
        row = _CompletedRow(task.id)
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 4, 6, 4)
        h.setSpacing(6)
        text = task.text if task.text else "(空任务)"
        lbl = QLabel(text)
        lbl.setObjectName("doneTextDone" if task.text else "doneText")
        lbl.setWordWrap(True)            # 长文本触碰框边自动换行
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        h.addWidget(lbl, 1)
        btn = QPushButton("↩")
        btn.setObjectName("restoreBtn")
        btn.setFixedSize(24, 24)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setToolTip("恢复到任务列表")
        btn.clicked.connect(lambda checked=False, tid=task.id: self.restored.emit(tid))
        h.addWidget(btn)
        row.delete_requested.connect(self.deleted)
        return row
