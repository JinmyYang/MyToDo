"""TaskStore 数据层单元测试。"""

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


def test_load_skips_bad_records(tmp_path):
    p = tmp_path / "tasks.json"
    p.write_text(
        '[{"id": "1", "text": "好任务"}, {"no_id": "坏数据"}, {"id": "2", "text": "另一好"}]',
        encoding="utf-8",
    )
    store = TaskStore(p)
    assert len(store.tasks) == 2  # 跳过坏记录,保留好的
