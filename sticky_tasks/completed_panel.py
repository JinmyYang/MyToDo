"""已完成任务面板:列出已完成任务,可一键恢复。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QScrollArea,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor

PANEL_QSS = """
QFrame#completedItem {
    background: rgba(255,255,255,18);
    border-radius: 6px;
    margin: 2px 10px;
}
QLabel#doneText { color: #9aa0a6; font-size: 12px; }
QLabel#doneTextDone { color: #9aa0a6; font-size: 12px; text-decoration: line-through; }
QPushButton#restoreBtn {
    color: #9aa0a6; background: transparent; border: none;
    padding: 2px 6px; font-size: 14px;
}
QPushButton#restoreBtn:hover { color: #1a73e8; }
QLabel#panelTitle { color: #80868b; font-size: 11px; padding: 6px 14px 2px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,50); border-radius: 3px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class CompletedPanel(QWidget):
    restored = Signal(str)  # task_id

    def __init__(self):
        super().__init__()
        self.setStyleSheet(PANEL_QSS)
        self.setMaximumHeight(200)
        self._row_for = {}

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(0)

        self.title = QLabel("已完成")
        self.title.setObjectName("panelTitle")
        v.addWidget(self.title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body_container = QWidget()
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
        count = len(tasks)
        self.title.setText(f"已完成 ({count})" if count else "已完成")

    def _make_row(self, task):
        row = QFrame()
        row.setObjectName("completedItem")
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 4, 6, 4)
        h.setSpacing(6)
        text = task.text if task.text else "(空任务)"
        lbl = QLabel(text)
        lbl.setObjectName("doneTextDone" if task.text else "doneText")
        h.addWidget(lbl, 1)
        btn = QPushButton("↩")
        btn.setObjectName("restoreBtn")
        btn.setFixedSize(24, 24)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setToolTip("恢复到任务列表")
        btn.clicked.connect(lambda checked=False, tid=task.id: self.restored.emit(tid))
        h.addWidget(btn)
        return row
