"""已完成任务面板:列出已完成任务,可恢复或右键删除。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QScrollArea,
    QMenu, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor, QColor

from .app_settings import Theme

PANEL_QSS = """
CompletedPanel { background: transparent; }
QFrame#completedItem {
    background: rgba(255, 255, 255, 4);
    border-radius: 9px;
    margin: 1px 10px;
}
QFrame#completedItem:hover {
    background: rgba(255, 255, 255, 9);
}
QLabel#doneText { color: #6e6e78; font-size: 12px; }
QLabel#doneTextDone {
    color: #8a8a94;
    font-size: 12px;
    text-decoration: line-through;
}
QPushButton#restoreBtn {
    color: #8a8a94;
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 7px;
    padding: 1px 4px;
    font-size: 12px;
}
QPushButton#restoreBtn:hover {
    color: #ffffff;
    background: rgba(94, 160, 255, 90);
    border-color: rgba(94, 160, 255, 150);
}
QScrollArea { border: none; background: transparent; }
QScrollArea viewport { background: transparent; }
QWidget#bodyContainer { background: transparent; }
QScrollBar:vertical { background: transparent; width: 5px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,36); border-radius: 2px; min-height: 20px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def build_panel_qss(t: Theme) -> str:
    """根据主题生成已完成面板 QSS。"""
    hl = t.highlight_color
    ico = t.icon_color
    acc = t.accent_color
    sb = t.scrollbar_color
    return f"""
CompletedPanel {{ background: transparent; }}
QFrame#completedItem {{
    background: rgba({hl.red()}, {hl.green()}, {hl.blue()}, {max(hl.alpha() - 3, 2)});
    border-radius: 9px;
    margin: 1px 10px;
}}
QFrame#completedItem:hover {{
    background: rgba({hl.red()}, {hl.green()}, {hl.blue()}, {hl.alpha() + 3});
}}
QLabel#doneText {{ color: rgba({ico.red()},{ico.green()},{ico.blue()},180); font-size: 12px; }}
QLabel#doneTextDone {{
    color: rgba({ico.red()},{ico.green()},{ico.blue()},200);
    font-size: 12px;
    text-decoration: line-through;
}}
QPushButton#restoreBtn {{
    color: rgba({ico.red()},{ico.green()},{ico.blue()},200);
    background: transparent;
    border: 1px solid rgba({ico.red()},{ico.green()},{ico.blue()},40);
    border-radius: 7px;
    padding: 1px 4px;
    font-size: 12px;
}}
QPushButton#restoreBtn:hover {{
    color: #ffffff;
    background: rgba({acc.red()}, {acc.green()}, {acc.blue()}, 90);
    border-color: rgba({acc.red()}, {acc.green()}, {acc.blue()}, 150);
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea viewport {{ background: transparent; }}
QWidget#bodyContainer {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 5px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: rgba({sb.red()},{sb.green()},{sb.blue()},{sb.alpha()}); border-radius: 2px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


class _CompletedRow(QFrame):
    """已完成任务行:右键弹出删除菜单。"""

    delete_requested = Signal(str)

    def __init__(self, task_id):
        super().__init__()
        self.setObjectName("completedItem")
        self.setAttribute(Qt.WA_StyledBackground)
        self._task_id = task_id

    def contextMenuEvent(self, event):
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
        act_del = menu.addAction("\u5220\u9664")
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
        v.setContentsMargins(0, 7, 0, 6)
        v.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body_container = QWidget()
        self.body_container.setObjectName("bodyContainer")
        self.body = QVBoxLayout(self.body_container)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(4)
        self.body.addStretch()  # 末尾占位,任务顶对齐
        self.scroll.setWidget(self.body_container)
        v.addWidget(self.scroll, 1)

    def set_theme(self, theme: Theme):
        self.setStyleSheet(build_panel_qss(theme))

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
        h.setContentsMargins(10, 5, 6, 5)
        h.setSpacing(8)
        text = task.text if task.text else "(空任务)"
        lbl = QLabel(text)
        lbl.setObjectName("doneTextDone" if task.text else "doneText")
        lbl.setWordWrap(True)            # 长文本触碰框边自动换行
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        h.addWidget(lbl, 1)
        btn = QPushButton("↩")
        btn.setObjectName("restoreBtn")
        btn.setFixedSize(22, 22)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setToolTip("恢复到任务列表")
        btn.clicked.connect(lambda checked=False, tid=task.id: self.restored.emit(tid))
        h.addWidget(btn)
        row.delete_requested.connect(self.deleted)
        return row
