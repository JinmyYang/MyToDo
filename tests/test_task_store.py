"""TaskStore 数据层单元测试。"""

import json
from pathlib import Path

from sticky_tasks.task_store import TaskStore


def test_add_and_get(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    t = store.add("买牛奶")
    assert t.text == "买牛奶"
    assert t.completed is False
    assert store.get(t.id) is t
    assert len(store.active_tasks()) == 1


def test_complete_moves_to_completed(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    t = store.add("任务")
    store.complete(t.id)
    assert t.completed is True
    assert store.active_tasks() == []
    assert len(store.completed_tasks()) == 1


def test_restore_moves_back_to_active(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    t = store.add("任务")
    store.complete(t.id)
    store.restore(t.id)
    assert t.completed is False
    assert len(store.active_tasks()) == 1
    assert store.completed_tasks() == []
    assert t.completed_at is None


def test_completed_tasks_are_newest_first_and_timestamp_persists(tmp_path):
    p = tmp_path / "tasks.json"
    store = TaskStore(p)
    older = store.add("先完成")
    newer = store.add("后完成")
    store.complete(older.id)
    older.completed_at = "2026-01-01T10:00:00"
    store.complete(newer.id)
    newer.completed_at = "2026-01-02T10:00:00"
    store.save()

    reloaded = TaskStore(p)
    assert [task.text for task in reloaded.completed_tasks()] == ["后完成", "先完成"]
    assert reloaded.get(newer.id).completed_at == "2026-01-02T10:00:00"


def test_old_json_without_completed_at_remains_compatible(tmp_path):
    p = tmp_path / "tasks.json"
    p.write_text(json.dumps([
        {"id": "old", "text": "旧任务", "completed": True,
         "created_at": "2025-01-01T00:00:00"},
    ]), encoding="utf-8")

    store = TaskStore(p)
    assert store.completed_tasks()[0].completed_at is None


def test_update_text(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    t = store.add("旧文本")
    store.update_text(t.id, "新文本")
    assert store.get(t.id).text == "新文本"


def test_delete(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    t = store.add("任务")
    store.delete(t.id)
    assert store.get(t.id) is None
    assert store.active_tasks() == []


def test_deleted_task_can_be_reinstated_at_original_position(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    first = store.add("第一")
    second = store.add("第二")

    task, index = store.delete(first.id)
    store.reinstate(task, index)

    assert [item.id for item in store.tasks] == [first.id, second.id]


def test_persistence_roundtrip(tmp_path):
    p = tmp_path / "tasks.json"
    s1 = TaskStore(p)
    a = s1.add("任务A")
    s1.add("任务B")
    s1.complete(a.id)

    s2 = TaskStore(p)  # 重新加载
    assert len(s2.tasks) == 2
    assert {t.text for t in s2.tasks} == {"任务A", "任务B"}
    assert len(s2.active_tasks()) == 1
    assert len(s2.completed_tasks()) == 1


def test_empty_text_allowed(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    t = store.add("")
    assert t.text == ""
    assert store.get(t.id) is not None  # 空文本任务可以存在(UI 层负责删除)


def test_load_missing_file_is_empty(tmp_path):
    store = TaskStore(tmp_path / "does_not_exist.json")
    assert store.tasks == []


def test_load_corrupt_file_is_empty(tmp_path):
    p = tmp_path / "tasks.json"
    p.write_text("not valid json {{{", encoding="utf-8")
    store = TaskStore(p)
    assert store.tasks == []  # 损坏文件不崩溃
    assert store.load_warning is not None
    assert store.corrupt_backup_path is not None
    assert store.corrupt_backup_path.read_text(encoding="utf-8") == "not valid json {{{"
    assert not p.exists()

    # 后续保存使用新文件，不能覆盖唯一的损坏文件备份。
    store.add("恢复后的任务")
    assert p.exists()
    assert store.corrupt_backup_path.exists()


def test_load_skips_bad_records(tmp_path):
    p = tmp_path / "tasks.json"
    p.write_text(
        '[{"id": "1", "text": "好任务"}, {"no_id": "坏数据"}, {"id": "2", "text": "另一好"}]',
        encoding="utf-8",
    )
    store = TaskStore(p)
    assert len(store.tasks) == 2  # 跳过坏记录,保留好的
