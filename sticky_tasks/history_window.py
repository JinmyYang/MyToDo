"""历史任务窗口:批量恢复或永久删除已完成/已删除任务。"""

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QMessageBox, QAbstractItemView,
)


HISTORY_QSS = """
HistoryWindow { background: #1e1f24; }
QLabel { color: #c8c8d2; font-size: 12px; }
QLabel#title { color: #e4e4ea; font-size: 15px; font-weight: 600; }
QTreeWidget {
    background: #24252b;
    border: 1px solid rgba(255,255,255,18);
    border-radius: 6px;
    color: #dedee6;
    alternate-background-color: #212228;
    outline: none;
}
QTreeWidget::item { min-height: 30px; padding: 2px 4px; }
QTreeWidget::item:selected { background: #365c89; }
QHeaderView::section {
    background: #292a31;
    color: #9fa0aa;
    border: none;
    border-bottom: 1px solid rgba(255,255,255,18);
    padding: 7px 6px;
    font-size: 11px;
}
QPushButton {
    background: rgba(255,255,255,8);
    border: 1px solid rgba(255,255,255,18);
    border-radius: 6px;
    color: #d8d8e0;
    padding: 6px 14px;
}
QPushButton:hover { background: rgba(255,255,255,14); }
QPushButton#danger { color: #ff9c9c; }
QPushButton:disabled { color: #666872; }
"""


class HistoryWindow(QWidget):
    """展示历史任务，并执行批量恢复或永久删除。"""

    changed = Signal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("历史任务")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setStyleSheet(HISTORY_QSS)
        self.resize(620, 440)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("历史任务")
        title.setObjectName("title")
        title_row.addWidget(title)
        title_row.addStretch()
        self.count_label = QLabel()
        title_row.addWidget(self.count_label)
        root.addLayout(title_row)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["任务", "状态", "时间"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().resizeSection(0, 340)
        self.tree.header().resizeSection(1, 80)
        self.tree.header().resizeSection(2, 150)
        self.tree.itemChanged.connect(self._update_actions)
        root.addWidget(self.tree, 1)

        actions = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.select_all_btn.clicked.connect(self._toggle_all)
        actions.addWidget(self.select_all_btn)
        actions.addStretch()
        self.restore_btn = QPushButton("恢复到任务列表")
        self.restore_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.restore_btn.clicked.connect(self.restore_selected)
        actions.addWidget(self.restore_btn)
        self.delete_btn = QPushButton("永久删除")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.delete_btn.clicked.connect(self.delete_selected)
        actions.addWidget(self.delete_btn)
        root.addLayout(actions)

    def refresh(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        tasks = self.store.history_tasks()
        for task in tasks:
            status = "已删除" if task.deleted else "已完成"
            stamp = task.deleted_at or task.completed_at or task.created_at
            item = QTreeWidgetItem([
                task.text or "(空任务)",
                status,
                self._format_time(stamp),
            ])
            item.setData(0, Qt.UserRole, task.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Unchecked)
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        self.count_label.setText(f"共 {len(tasks)} 项")
        self._update_actions()

    def _checked_ids(self):
        return [
            self.tree.topLevelItem(index).data(0, Qt.UserRole)
            for index in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(index).checkState(0) == Qt.Checked
        ]

    def _toggle_all(self):
        items = [
            self.tree.topLevelItem(index)
            for index in range(self.tree.topLevelItemCount())
        ]
        check = Qt.Unchecked if items and all(
            item.checkState(0) == Qt.Checked for item in items
        ) else Qt.Checked
        self.tree.blockSignals(True)
        for item in items:
            item.setCheckState(0, check)
        self.tree.blockSignals(False)
        self._update_actions()

    def _update_actions(self):
        count = len(self._checked_ids())
        self.restore_btn.setEnabled(count > 0)
        self.delete_btn.setEnabled(count > 0)
        self.restore_btn.setText(f"恢复到任务列表 ({count})" if count else "恢复到任务列表")
        self.delete_btn.setText(f"永久删除 ({count})" if count else "永久删除")

    def restore_selected(self):
        ids = self._checked_ids()
        if not ids:
            return
        self.store.restore_many(ids)
        self.refresh()
        self.changed.emit()

    def delete_selected(self, confirm=True):
        ids = self._checked_ids()
        if not ids:
            return
        if confirm:
            answer = QMessageBox.question(
                self,
                "永久删除",
                f"确定永久删除选中的 {len(ids)} 个任务吗？此操作无法恢复。",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.store.permanent_delete(ids)
        self.refresh()
        self.changed.emit()

    @staticmethod
    def _format_time(value):
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError):
            return ""
