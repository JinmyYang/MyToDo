"""GUI 冒烟测试:在 offscreen 平台验证核心交互流程,不弹真实窗口。"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QEvent, QPointF, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from sticky_tasks.main_window import MainWindow, build_qss
from sticky_tasks.app_settings import AppSettings
from sticky_tasks.completed_panel import build_panel_qss
from sticky_tasks.task_store import TaskStore


@pytest.fixture
def app():
    return QApplication.instance() or QApplication(sys.argv)


def test_task_scrollbars_share_wider_hover_handle():
    theme = AppSettings().to_theme()
    main_qss = build_qss(theme)
    completed_qss = build_panel_qss(theme)

    for qss in (main_qss, completed_qss):
        assert "width: 9px" in qss
        assert "margin: 0 3px" in qss
        assert "QScrollBar::handle:vertical:hover" in qss
        assert "margin: 0 1px" in qss


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
    """锁定后隐藏控件和滚动条，分隔线随文本左移，解锁恢复。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        for index in range(20):
            store.add(f"任务 {index}")
        w = MainWindow(store)
        w.show()
        app.processEvents()
        item = list(w._active_items.values())[0]
        bar = w.scroll.verticalScrollBar()
        unlocked_separator_left = item._separator_left()
        assert item.dot.isVisible()
        assert bar.isVisible()
        assert w.scroll.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded

        w.set_locked(True)
        app.processEvents()
        assert not item.dot.isVisible()
        assert item._separator_left() == item.stack.geometry().left()
        assert item._separator_left() < unlocked_separator_left
        assert not w._inline_add_btn.isVisible()
        assert w.header.lock_btn.isVisible()
        assert w.header.lock_btn._locked == True
        assert not w.footer_btn.isVisible()
        assert not bar.isVisible()
        assert w.scroll.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff

        w.unlock()
        app.processEvents()
        assert item.dot.isVisible()
        assert w.header.lock_btn.isVisible()
        assert w.header.lock_btn._locked == False
        assert bar.isVisible()
        assert w.scroll.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded


def test_click_lock_icon_toggles_lock_and_unlock(app):
    """回归:点击右上锁头图标可锁定,再点一次立即解锁并恢复全部控件。

    用 QTest.mouseClick 真实走一遍事件管线(含窗口 eventFilter),
    防止锁头点击被边缘缩放逻辑吞掉、或解锁后控件可见性不刷新。
    """
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        store.add("任务一")
        w = MainWindow(store)
        w.show()
        app.processEvents()
        item = list(w._active_items.values())[0]

        QTest.mouseClick(w.header.lock_btn, Qt.LeftButton, pos=QPoint(14, 14))
        app.processEvents()
        assert w._locked
        assert not item.dot.isVisible()
        assert not w._inline_add_btn.isVisible()
        assert not w.footer_btn.isVisible()

        QTest.mouseClick(w.header.lock_btn, Qt.LeftButton, pos=QPoint(14, 14))
        app.processEvents()
        assert not w._locked
        assert item.dot.isVisible()
        assert w._inline_add_btn.isVisible()
        assert w.footer_btn.isVisible()


def test_macos_style_header_structure(app):
    """标题栏保留标语与锁头图标、底部保留行内加号。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        w = MainWindow(store)

        assert w.header.title_label.text() == "JUST DO IT."
        assert w.header.lock_btn.width() == 28
        assert w._inline_add_btn.height() == 36
        assert "font-size: 20px" in w.container.styleSheet()


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
        assert item.edit.verticalScrollBar().maximum() == 0
        assert item.edit.verticalScrollBar().value() == 0

        item._on_editing_finished()
        app.processEvents()
        assert item.stack.height() == item.label.height()
        assert item.height() >= item.dot.height() + 8

        item.start_edit()
        app.processEvents()
        assert item.edit.toPlainText() == "第一行\n第二行\n第三行"
        assert item.edit.height() > single_line_height
        assert not item.edit.textCursor().hasSelection()
        assert item.edit.verticalScrollBar().maximum() == 0
        assert item.edit.verticalScrollBar().value() == 0


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
        assert item.edit.verticalScrollBar().maximum() == 0
        assert item.edit.verticalScrollBar().value() == 0


def test_long_press_drag_reorders_tasks_and_persists(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        path = root / "tasks.json"
        store = TaskStore(path)
        first = store.add("第一")
        second = store.add("第二")
        third = store.add("第三")
        w = MainWindow(store, settings_path=root / "settings.json")
        w.show()
        app.processEvents()

        item = w._active_items[first.id]
        target = w._active_items[third.id]
        press_global = item.label.mapToGlobal(item.label.rect().center())
        target_global = target.mapToGlobal(QPoint(target.width() // 2, target.height() + 8))
        press = QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(item.label.rect().center()),
            QPointF(press_global),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        assert item.eventFilter(item.label, press) is True
        assert item._dragging is False
        QTest.qWait(item.LONG_PRESS_MS + 30)
        assert item._dragging is True

        move = QMouseEvent(
            QEvent.MouseMove,
            QPointF(item.label.mapFromGlobal(target_global)),
            QPointF(target_global),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        assert item.eventFilter(item.label, move) is True
        app.processEvents()
        assert [row.task.id for row in w._ordered_task_items()] == [second.id, third.id, first.id]

        release = QMouseEvent(
            QEvent.MouseButtonRelease,
            QPointF(item.label.mapFromGlobal(target_global)),
            QPointF(target_global),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
        assert item.eventFilter(item.label, release) is True
        app.processEvents()
        assert item._dragging is False
        assert [task.id for task in TaskStore(path).active_tasks()] == [second.id, third.id, first.id]


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
        assert store.get(t.id) is t
        assert t.deleted is True
        assert store.history_tasks() == [t]
        assert w.footer_btn.text().startswith("已完成  0")


def test_completed_text_is_always_plain_text(app):
    """HTML 形态的任务完成后仍按字面显示，不改变内容样式。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        task = store.add("<b>字面标签</b>")
        store.complete(task.id)
        w = MainWindow(store, settings_path=Path(d) / "settings.json")
        row = w.completed_panel._row_for[task.id]
        label = row.findChild(QLabel)

        assert label.textFormat() == Qt.PlainText
        assert label.text() == "<b>字面标签</b>"


def test_collapsing_completed_panel_keeps_manual_height_change(app):
    """展开状态下手动调整的高度，在折叠后继续保留。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        w = MainWindow(store, settings_path=Path(d) / "settings.json")
        w.show()
        app.processEvents()

        collapsed_h = w.height()
        w.toggle_completed()
        w.resize(w.width(), w.height() + 80)
        w.toggle_completed()

        assert w.height() == collapsed_h + 80


def test_settings_window_closes_with_main_window(app):
    """独立设置窗口不能在主窗口关闭后继续让应用驻留。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        w = MainWindow(store, settings_path=Path(d) / "settings.json")
        w.show()
        w.open_settings()
        app.processEvents()
        settings_win = w._settings_win
        assert settings_win.isVisible()

        w.close()
        app.processEvents()
        assert not settings_win.isVisible()


def test_dot_only_completes_when_released_inside(app):
    """在圆点按下后拖出再释放，不应误完成任务。"""
    with tempfile.TemporaryDirectory() as d:
        store = TaskStore(Path(d) / "tasks.json")
        task = store.add("任务")
        w = MainWindow(store, settings_path=Path(d) / "settings.json")
        w.show()
        app.processEvents()
        dot = w._active_items[task.id].dot

        QTest.mousePress(dot, Qt.LeftButton, pos=QPoint(9, 9))
        QTest.mouseRelease(dot, Qt.LeftButton, pos=QPoint(-2, -2))
        app.processEvents()
        assert store.get(task.id).completed is False

        QTest.mouseClick(dot, Qt.LeftButton, pos=QPoint(9, 9))
        app.processEvents()
        assert store.get(task.id).completed is True


def test_font_settings_apply_and_flush_on_immediate_close(app):
    """字体名称/字号立即生效，防抖期内退出也必须保存。"""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        settings_path = root / "settings.json"
        store = TaskStore(root / "tasks.json")
        task = store.add("带样式任务")
        w = MainWindow(store, settings_path=settings_path)
        w.show()
        w.settings.font_family = "Arial"
        w.settings.font_size = 16
        w._on_settings_changed()

        font = w._active_items[task.id].label.font()
        assert font.family() == "Arial"
        assert font.pixelSize() == 16

        w.close()
        loaded = AppSettings.load(settings_path)
        assert loaded.font_family == "Arial"
        assert loaded.font_size == 16


def test_double_click_task_text_starts_edit_unless_locked(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        store = TaskStore(root / "tasks.json")
        task = store.add("点我编辑")
        w = MainWindow(store, settings_path=root / "settings.json")
        w.show()
        app.processEvents()
        item = w._active_items[task.id]

        QTest.mouseClick(item.label, Qt.LeftButton)
        app.processEvents()
        assert item.stack.currentIndex() == item._LABEL_PAGE

        QTest.mouseDClick(item.label, Qt.LeftButton)
        app.processEvents()
        assert item.stack.currentIndex() == item._EDIT_PAGE

        item._exit_edit()
        w.set_locked(True)
        QTest.mouseDClick(item.label, Qt.LeftButton)
        app.processEvents()
        assert item.stack.currentIndex() == item._LABEL_PAGE


def test_keyboard_shortcuts_create_and_toggle_lock(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        store = TaskStore(root / "tasks.json")
        w = MainWindow(store, settings_path=root / "settings.json")
        w.show()
        w.activateWindow()
        app.processEvents()

        QTest.keyClick(w, Qt.Key_N, Qt.ControlModifier)
        app.processEvents()
        assert len(store.active_tasks()) == 1
        new_item = list(w._active_items.values())[-1]
        new_item.edit.setPlainText("快捷键任务")
        new_item._on_editing_finished()

        QTest.keyClick(w, Qt.Key_L, Qt.ControlModifier)
        app.processEvents()
        assert w._locked
        QTest.keyClick(w, Qt.Key_N, Qt.ControlModifier)
        app.processEvents()
        assert len(store.active_tasks()) == 1


def test_deleted_task_can_be_restored_from_history_window(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        store = TaskStore(root / "tasks.json")
        task = store.add("不要删我")
        second = store.add("第二个任务")
        w = MainWindow(store, settings_path=root / "settings.json")
        w.show()
        app.processEvents()

        w.on_delete(task.id)
        app.processEvents()
        assert task.deleted is True
        assert task.id not in w._active_items

        w.open_history()
        history = w._history_win
        item = history.tree.topLevelItem(0)
        assert item.data(0, Qt.UserRole) == task.id
        item.setCheckState(0, Qt.Checked)
        history.restore_selected()
        app.processEvents()
        assert store.get(task.id) is task
        assert task.deleted is False
        assert task.id in w._active_items
        visible_ids = [
            w.list_layout.itemAt(index).widget().task.id
            for index in range(2)
        ]
        assert visible_ids == [task.id, second.id]


def test_history_window_batch_permanently_deletes_selected(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        store = TaskStore(root / "tasks.json")
        completed = store.add("完成项")
        deleted = store.add("删除项")
        store.complete(completed.id)
        store.delete(deleted.id)
        w = MainWindow(store, settings_path=root / "settings.json")
        w.open_history()
        history = w._history_win

        history._toggle_all()
        history.delete_selected(confirm=False)
        app.processEvents()

        assert store.history_tasks() == []
        assert history.tree.topLevelItemCount() == 0


def test_loaded_rows_do_not_animate_but_new_rows_do(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        store = TaskStore(root / "tasks.json")
        existing = store.add("已有任务")
        w = MainWindow(store, settings_path=root / "settings.json")
        w.show()
        app.processEvents()

        assert w._active_items[existing.id].graphicsEffect() is None
        w.add_task()
        new_item = list(w._active_items.values())[-1]
        assert new_item.graphicsEffect() is not None


def test_completed_panel_uses_content_height_and_stays_on_screen(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        store = TaskStore(root / "tasks.json")
        task = store.add("已完成")
        store.complete(task.id)
        w = MainWindow(store, settings_path=root / "settings.json")
        screen = QApplication.primaryScreen().availableGeometry()
        w.resize(320, 300)
        w.move(screen.left() + 20, screen.bottom() - w.height() + 1)
        w.show()
        app.processEvents()

        w.toggle_completed()
        app.processEvents()
        assert 42 <= w._expanded_panel_h < 160
        assert w.frameGeometry().bottom() <= screen.bottom()


def test_completed_panel_keeps_height_after_complete_restore_and_delete(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        store = TaskStore(root / "tasks.json")
        active = store.add("待完成")
        completed = []
        for index in range(5):
            task = store.add(f"完成任务 {index}")
            store.complete(task.id)
            completed.append(task)
        w = MainWindow(store, settings_path=root / "settings.json")
        w.show()
        w.toggle_completed()
        app.processEvents()
        initial_height = w.completed_panel.height()
        assert initial_height > 80

        w.on_complete(active.id)
        app.processEvents()
        assert w.completed_panel.height() > 80

        w.on_restore(completed[0].id)
        app.processEvents()
        assert w.completed_panel.height() > 80

        w.on_delete(completed[1].id)
        app.processEvents()
        assert w.completed_panel.height() > 80


def test_window_geometry_is_restored_and_clamped_to_screen(app):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        settings_path = root / "settings.json"
        settings = AppSettings(
            window_x=100000,
            window_y=100000,
            window_width=360,
            window_height=500,
        )
        settings.save(settings_path)
        w = MainWindow(TaskStore(root / "tasks.json"), settings_path=settings_path)
        screen = QApplication.primaryScreen().availableGeometry()

        assert screen.contains(w.frameGeometry().topLeft())
        assert w.width() == 360
        assert w.height() == 500
