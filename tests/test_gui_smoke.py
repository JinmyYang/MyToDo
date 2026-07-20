"""GUI 冒烟测试:在 offscreen 平台验证核心交互流程,不弹真实窗口。"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QMouseEvent
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
        assert w.footer_btn.text().startswith("已完成  1")

        # 展开已完成面板并恢复
        w.toggle_completed()
        assert w.completed_panel.isVisible()
        w.on_restore(first)
        app.processEvents()
        assert len(w._active_items) == 3
        assert len(store.completed_tasks()) == 0
        assert w.footer_btn.text().startswith("已完成  0")

        # 新建任务并填文本(默认展示 label,需先进入编辑态)
        w.add_task()
        app.processEvents()
        new_item = list(w._active_items.values())[-1]
        new_item.start_edit()
        new_item.edit.setPlainText("新任务")
        new_item._on_editing_finished()
        app.processEvents()
        assert len(w._active_items) == 4
        new_id = list(w._active_items.keys())[-1]
        assert store.get(new_id).text == "新任务"

        # 空任务失焦应被删除
        w.add_task()
        app.processEvents()
        empty_item = list(w._active_items.values())[-1]
        empty_item.start_edit()
        empty_item.edit.setPlainText("")
        empty_item._on_editing_finished()
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
        assert w.footer_btn.text().startswith("已完成  1")


def test_lock_hides_controls_and_unlock_restores(app):
    """锁定后隐藏圆点/加号/锁头按钮,解锁恢复。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        store.add("任务一")
        w = MainWindow(store)
        w.show()
        app.processEvents()
        item = list(w._active_items.values())[0]
        assert item.dot.isVisible()

        w.set_locked(True)
        app.processEvents()
        assert not item.dot.isVisible()
        assert not w.header.add_btn.isVisible()
        assert w.header.lock_btn.isVisible()
        assert w.header.lock_btn._locked == True
        assert not w.footer_btn.isVisible()

        w.unlock()
        app.processEvents()
        assert item.dot.isVisible()
        assert w.header.add_btn.isVisible()
        assert w.header.lock_btn.isVisible()
        assert w.header.lock_btn._locked == False


def test_macos_style_header_structure(app):
    """主窗口保留简洁标语与圆形操作按钮的视觉结构。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        w = MainWindow(store)

        assert w.header.title_label.text() == "JUST DO IT."
        assert w.header.add_btn.size() == w.header.lock_btn.size()
        assert w.header.add_btn.width() == 28


def test_task_rows_stay_compact_when_window_grows(app):
    """窗口变高时，任务行保持紧凑，额外空间留在列表底部。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        store.add("任务一")
        store.add("任务二")
        w = MainWindow(store)
        w.show()
        app.processEvents()

        heights_before = [item.height() for item in w._active_items.values()]
        assert max(heights_before) <= 48
        w.resize(w.width(), w.height() + 240)
        app.processEvents()
        heights_after = [item.height() for item in w._active_items.values()]

        assert heights_after == heights_before


def test_edit_height_follows_task_text(app):
    """编辑框只占文本所需高度，多行内容再相应增长。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        task = store.add("短任务")
        w = MainWindow(store)
        w.show()
        app.processEvents()

        item = w._active_items[task.id]
        item.start_edit()
        app.processEvents()
        single_line_height = item.edit.height()
        assert not item.edit.textCursor().hasSelection()
        assert item.edit.minimumHeight() == item.edit.maximumHeight()
        assert single_line_height >= item.edit.fontMetrics().lineSpacing() + 14

        item.edit.setPlainText("第一行\n第二行\n第三行")
        app.processEvents()
        assert item.edit.height() > single_line_height
        assert item.edit.height() == item.stack.height()

        item._on_editing_finished()
        app.processEvents()
        assert item.stack.height() == item.label.height()
        assert item.height() >= item.dot.height() + 8

        item.start_edit()
        app.processEvents()
        assert item.edit.toPlainText() == "第一行\n第二行\n第三行"
        assert item.edit.height() > single_line_height
        assert not item.edit.textCursor().hasSelection()


def test_long_text_stays_visible_after_reopening_and_resizing(app):
    """长文本重新编辑和缩窄窗口后，编辑框仍完整容纳文本。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        text = "这是一段用于验证自动换行和重新编辑的较长任务文本。" * 4
        task = store.add(text)
        w = MainWindow(store)
        w.show()
        app.processEvents()

        item = w._active_items[task.id]
        item.start_edit()
        app.processEvents()
        first_height = item.edit.height()
        assert item.edit.textCursor().position() == len(text)
        assert not item.edit.textCursor().hasSelection()

        item._on_editing_finished()
        w.resize(220, w.height())
        app.processEvents()
        assert item.label.height() >= item.label.heightForWidth(item.label.width())

        item.start_edit()
        app.processEvents()
        assert item.edit.toPlainText() == text
        assert item.edit.textCursor().position() == len(text)
        assert item.edit.height() >= first_height


def test_edge_hover_sets_resize_cursor(app):
    """鼠标悬停到窗口边缘/角落时,容器光标变为对应的缩放光标。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        store.add("任务一")
        w = MainWindow(store)
        w.move(0, 0)
        w.resize(300, 440)
        w.show()
        app.processEvents()

        def hover(gx, gy):
            ev = QMouseEvent(
                QEvent.MouseMove, QPointF(1, 1), QPointF(gx, gy),
                Qt.NoButton, Qt.NoButton, Qt.NoModifier,
            )
            w.eventFilter(w.container, ev)
            oc = QApplication.overrideCursor()
            return oc.shape() if oc is not None else Qt.ArrowCursor

        wd, ht = w.width(), w.height()
        assert hover(wd - 1, ht // 2) == Qt.SizeHorCursor      # 右边 → ↔
        assert hover(wd // 2, ht - 1) == Qt.SizeVerCursor      # 下边 → ↕
        assert hover(wd - 1, ht - 1) == Qt.SizeFDiagCursor     # 右下角 → ↖↘
        assert hover(1, ht - 1) == Qt.SizeBDiagCursor          # 左下角 → ↗↙
        assert hover(wd - 1, 1) == Qt.SizeBDiagCursor          # 右上角 → ↗↙
        assert hover(wd // 2, ht // 2) == Qt.ArrowCursor       # 中间 → 箭头
        w._apply_edge_cursor(None)  # 复位,避免污染后续测试


def test_collapsed_footer_bottom_edge_can_resize(app):
    """已完成栏折叠时,footer 底边仍能拖拽缩放窗口。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        store.add("任务一")
        w = MainWindow(store)
        w.move(0, 0)
        w.resize(300, 440)
        w.show()
        app.processEvents()

        old_h = w.height()
        x = w.width() // 2
        y = old_h - 1
        press = QMouseEvent(
            QEvent.MouseButtonPress, QPointF(x, y), QPointF(x, y),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
        )
        assert w.eventFilter(w.footer_btn, press) is True

        move = QMouseEvent(
            QEvent.MouseMove, QPointF(x, y + 30), QPointF(x, y + 30),
            Qt.NoButton, Qt.LeftButton, Qt.NoModifier,
        )
        assert w.eventFilter(w.footer_btn, move) is True

        release = QMouseEvent(
            QEvent.MouseButtonRelease, QPointF(x, y + 30), QPointF(x, y + 30),
            Qt.LeftButton, Qt.NoButton, Qt.NoModifier,
        )
        assert w.eventFilter(w.footer_btn, release) is True
        assert w.height() > old_h
        w._apply_edge_cursor(None)


def test_completed_right_click_delete(app):
    """已完成任务通过右键删除信号删除后,store 与面板同步。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        t = store.add("做完的")
        store.complete(t.id)
        w = MainWindow(store)
        w.show()
        app.processEvents()
        assert len(store.completed_tasks()) == 1

        # 模拟已完成行右键 → 删除
        w.completed_panel.deleted.emit(t.id)
        app.processEvents()
        assert len(store.completed_tasks()) == 0
        assert store.get(t.id) is None
        assert w.footer_btn.text().startswith("已完成  0")
