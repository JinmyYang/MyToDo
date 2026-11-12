"""已完成任务面板:列出已完成任务,可恢复或右键删除。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame, QScrollArea,
    QMenu, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCursor, QColor, QFont

from .app_settings import Theme
from .task_item import TEXT_MASK, wrap_for_label


def _elide(text, limit=6):
    """面板很窄,上级任务名太长就截断(完整内容挂在 tooltip 上)。"""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


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
QLabel#doneHint {
    color: #6e6e78;
    font-size: 11px;
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
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px 0; }
QScrollBar::handle:vertical {
    background: rgba(255,255,255,36);
    border-radius: 2px;
    min-height: 20px;
    margin: 0 3px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,68);
    border-radius: 3px;
    margin: 0 1px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def build_panel_qss(t: Theme) -> str:
    """根据主题生成已完成面板 QSS。"""
    hl = t.highlight_color
    ico = t.icon_color
    acc = t.accent_color
    sb = t.scrollbar_color
    sbh = t.scrollbar_hover_color
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
QLabel#doneText {{
    color: rgba({ico.red()},{ico.green()},{ico.blue()},180);
    font-family: "{t.font_family}";
    font-size: {max(9, t.font_size - 1)}px;
}}
QLabel#doneTextDone {{
    color: rgba({ico.red()},{ico.green()},{ico.blue()},200);
    font-family: "{t.font_family}";
    font-size: {max(9, t.font_size - 1)}px;
    text-decoration: line-through;
}}
QLabel#doneHint {{
    color: rgba({ico.red()},{ico.green()},{ico.blue()},175);
    font-family: "{t.font_family}";
    font-size: {max(9, t.font_size - 2)}px;
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
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px 0; }}
QScrollBar::handle:vertical {{
    background: rgba({sb.red()},{sb.green()},{sb.blue()},{sb.alpha()});
    border-radius: 2px;
    min-height: 20px;
    margin: 0 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba({sbh.red()},{sbh.green()},{sbh.blue()},{sbh.alpha()});
    border-radius: 3px;
    margin: 0 1px;
}}
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
        self.label = None        # 任务文本
        self.hint = None         # 行尾说明:「↳ 上级任务」
        self.parent_text = ""    # 上级任务名(用来提示归属)
        self.with_parent = False # 恢复时是否要连带把上级也恢复

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
        self._text_for = {}  # task_id -> 任务原文(隐私模式切换时重新填充行文本)
        self._text_hidden = False
        self._theme = None

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
        self._theme = theme
        self.setStyleSheet(build_panel_qss(theme))

    def set_tasks(self, entries):
        """entries: [(task, 上级任务名, 是否连带恢复上级)]。"""
        # 清空旧行(保留末尾 stretch)
        while self.body.count() > 1:
            item = self.body.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._row_for.clear()
        self._text_for.clear()
        for task, parent_text, with_parent in entries:
            self._text_for[task.id] = task.text or ""
            row = self._make_row(task, parent_text, with_parent)
            self.body.insertWidget(self.body.count() - 1, row)
            self._row_for[task.id] = row
        self.body.activate()

    def set_text_hidden(self, hidden):
        """隐私模式:行文本与上级名称统一换掩码/还原。"""
        self._text_hidden = hidden
        for tid, row in self._row_for.items():
            if row.label is not None:
                row.label.setText(self._display_text(self._text_for.get(tid, "")))
            if row.hint is not None:
                row.hint.setText(self._hint_text(row))

    def _mask(self, text):
        if self._text_hidden and text:
            return TEXT_MASK
        return text

    def _display_text(self, text):
        if self._text_hidden and text:
            return TEXT_MASK      # 掩码不需要断行点,保持原样
        return wrap_for_label(text if text else "(空任务)")

    def _hint_text(self, row):
        """行尾说明:子项标出它属于哪一组。"""
        if row.parent_text:
            return f"↳ {_elide(self._mask(row.parent_text))}"
        return ""

    def content_height(self):
        """返回完整展示当前内容所需的面板高度。

        按每行 label 在当前实际宽度下换行后的 heightForWidth 计算,
        不依赖 sizeHint(长串/多行文本下 sizeHint 不可靠)。
        """
        margins = self.layout().contentsMargins()
        rows = list(self._row_for.values())
        heights = []
        for row in rows:
            lm = row.layout().contentsMargins()
            # 刚创建的行可能尚未布局(width 为 0),回退到面板宽度估算
            row_w = row.width() if row.width() > 0 else self.width()
            # label 可用宽度 = 行宽 - 左右内边距 - 恢复按钮(22) - 间距(8) - 行尾说明 - 行尾说明
            hint_w = 0
            if row.hint is not None:
                hint_w = row.hint.sizeHint().width() + row.layout().spacing()
            text_w = max(
                40,
                row_w - lm.left() - lm.right() - 22 - 8 - hint_w,
            )
            lbl = row.label
            if lbl is None:
                heights.append(34 + lm.top() + lm.bottom())
                continue
            line_h = max(34, lbl.fontMetrics().lineSpacing() + 2)
            if lbl.text():
                text_h = lbl.heightForWidth(text_w)
                heights.append(max(line_h, text_h + lm.top() + lm.bottom()))
            else:
                heights.append(line_h + lm.top() + lm.bottom())
        spacing = self.body.spacing() * max(0, len(rows) - 1)
        return max(42, sum(heights) + spacing + margins.top() + margins.bottom())


    def _make_row(self, task, parent_text="", with_parent=False):
        row = _CompletedRow(task.id)
        row.parent_text = parent_text
        row.with_parent = with_parent
        h = QHBoxLayout(row)
        h.setContentsMargins(10, 5, 6, 5)
        h.setSpacing(8)
        # 注入零宽空格提供断行点:与主列表一致,连续数字/无空格长串也能换行
        lbl = QLabel(self._display_text(task.text or ""))
        lbl.setTextFormat(Qt.PlainText)
        lbl.setObjectName("doneTextDone" if task.text else "doneText")
        if self._theme is not None:
            font = QFont(self._theme.font_family)
            font.setPixelSize(max(9, self._theme.font_size - 1))
            font.setStrikeOut(True)
            lbl.setFont(font)
        lbl.setWordWrap(True)            # 长文本触碰框边自动换行
        # Ignored 使 label 的 minimumSizeHint(长串时为整行宽度)不参与布局,
        # 否则 sizeHint 会被长串撑爆,导致行高和面板 content_height 算错。
        lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        lbl.setMinimumWidth(0)
        lbl.setMaximumWidth(16777215)
        h.addWidget(lbl, 1)
        row.label = lbl

        hint_text = self._hint_text(row)
        if hint_text:
            hint = QLabel(hint_text)
            hint.setObjectName("doneHint")
            hint.setTextFormat(Qt.PlainText)
            hint.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            if self._theme is not None:
                font = QFont(self._theme.font_family)
                font.setPixelSize(max(9, self._theme.font_size - 2))
                hint.setFont(font)
            hint.setToolTip(parent_text)   # 名字被截断时看完整内容
            h.addWidget(hint)
            row.hint = hint

        btn = QPushButton("↩")
        btn.setObjectName("restoreBtn")
        btn.setFixedSize(22, 22)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setToolTip("连同上级一起恢复" if with_parent else "恢复到任务列表")
        btn.clicked.connect(lambda checked=False, tid=task.id: self.restored.emit(tid))
        h.addWidget(btn)
        row.delete_requested.connect(self.deleted)
        return row
