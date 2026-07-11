"""GUI 冒烟测试:在 offscreen 平台验证核心交互流程,不弹真实窗口。"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from sticky_tasks.main_window import MainWindow
from sticky_tasks.task_store import TaskStore


@pytest.fixture
def app():
    return QApplication.instance() or QApplication(sys.argv)


def test_core_flow(app):
    """创建 → 完成 → 恢复 → 编辑 → 空任务删除 → 持久化。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        store.add("买牛奶")
        store.add("写报告")
        store.add("回邮件")
        w = MainWindow(store)
        w.show()
        app.processEvents()

        # 3 个活跃任务显示在列表
        assert len(w._active_items) == 3

        # 完成第一个
        first = list(w._active_items.keys())[0]
        w.on_complete(first)
        app.processEvents()
        assert len(w._active_items) == 2
        assert len(store.completed_tasks()) == 1
        assert w.footer_btn.text().startswith("已完成 (1)")

        # 展开已完成面板并恢复
        w.toggle_completed()
        assert w.completed_panel.isVisible()
        w.on_restore(first)
        app.processEvents()
        assert len(w._active_items) == 3
        assert len(store.completed_tasks()) == 0
        assert w.footer_btn.text().startswith("已完成 (0)")

        # 新建任务并填文本
        w.add_task()
        app.processEvents()
        new_item = list(w._active_items.values())[-1]
        new_item.edit.setText("新任务")
        new_item.edit.editingFinished.emit()
        app.processEvents()
        assert len(w._active_items) == 4
        new_id = list(w._active_items.keys())[-1]
        assert store.get(new_id).text == "新任务"

        # 空任务失焦应被删除
        w.add_task()
        app.processEvents()
        empty_item = list(w._active_items.values())[-1]
        empty_item.edit.setText("")
        empty_item.edit.editingFinished.emit()
        app.processEvents()
        assert len(w._active_items) == 4  # 空的被删,回到 4

        # 持久化:重开后活跃任务数一致
        store2 = TaskStore(Path(d) / "tasks.json")
        assert len(store2.active_tasks()) == len(store.active_tasks())


def test_empty_task_completed_is_deleted(app):
    """空任务被点完成时直接删除,不进已完成栏。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        w = MainWindow(store)
        w.show()
        w.add_task()
        app.processEvents()
        empty_id = list(w._active_items.keys())[-1]
        w.on_complete(empty_id)
        app.processEvents()
        assert len(w._active_items) == 0
        assert len(store.completed_tasks()) == 0
        assert store.get(empty_id) is None


def test_persistence_reload_restores_ui(app):
    """重开后 UI 正确恢复活跃/已完成任务。"""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "tasks.json"
        s1 = TaskStore(p)
        s1.add("活跃任务")
        done = s1.add("已完成任务")
        s1.complete(done.id)

        s2 = TaskStore(p)
        w = MainWindow(s2)
        w.show()
        app.processEvents()
        assert len(w._active_items) == 1
        assert w.footer_btn.text().startswith("已完成 (1)")
