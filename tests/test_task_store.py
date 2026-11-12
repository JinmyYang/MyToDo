"""TaskStore 数据层单元测试。"""

import json
from pathlib import Path

from sticky_tasks.task_store import TaskStore


def _group(store):
    """建一个"父项 + 两个子项"的结构,返回 (父, 子1, 子2)。"""
    parent = store.add("本周")
    first = store.add("写周报", parent_id=parent.id)
    second = store.add("回邮件", parent_id=parent.id)
    return parent, first, second


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


def test_apply_tree_layout_persists_and_preserves_history_slots(tmp_path):
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    first = store.add("第一")
    completed = store.add("已完成")
    second = store.add("第二")
    third = store.add("第三")
    store.complete(completed.id)

    assert store.apply_tree_layout([
        (third.id, 0), (first.id, 0), (second.id, 0),
    ]) is True
    # 历史任务在原位置占位,活跃任务按新顺序填进剩下的槽位
    assert [task.id for task in store.tasks] == [third.id, completed.id, first.id, second.id]

    loaded = TaskStore(path)
    assert [task.id for task in loaded.active_tasks()] == [third.id, first.id, second.id]


def test_delete(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    t = store.add("任务")
    store.delete(t.id)
    assert store.get(t.id) is t
    assert t.deleted is True
    assert store.active_tasks() == []
    assert store.history_tasks() == [t]


def test_deleted_task_can_be_restored_from_history(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    first = store.add("第一")
    second = store.add("第二")

    store.delete(first.id)
    restored = store.restore_many([first.id])

    assert restored == [first]
    assert [item.id for item in store.tasks] == [first.id, second.id]
    assert [item.id for item in store.active_tasks()] == [first.id, second.id]


def test_history_can_be_permanently_deleted_in_batch(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    completed = store.add("已完成")
    deleted = store.add("已删除")
    active = store.add("保留")
    store.complete(completed.id)
    store.delete(deleted.id)

    removed = store.permanent_delete([completed.id, deleted.id])

    assert {task.id for task in removed} == {completed.id, deleted.id}
    assert store.tasks == [active]


def test_deleted_state_persists_roundtrip(tmp_path):
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    task = store.add("历史任务")
    store.delete(task.id)

    reloaded = TaskStore(path)
    loaded = reloaded.get(task.id)
    assert loaded.deleted is True
    assert loaded.deleted_at is not None
    assert reloaded.history_tasks() == [loaded]


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


# ---- 层级(父项 / 子项)----

def test_task_defaults_to_top_level(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    task = store.add("顶层任务")
    assert task.parent_id is None
    assert task.level == 0
    assert task.collapsed is False


def test_add_child_attaches_to_parent(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    assert first.parent_id == parent.id
    assert second.parent_id == parent.id
    assert first.level == 1 and second.level == 1
    assert [t.id for t in store.ordered_active()] == [parent.id, first.id, second.id]
    assert [t.id for t in store.active_children(parent.id)] == [first.id, second.id]


def test_add_child_stops_at_two_levels(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    third = store.add("第三层", parent_id=first.id)   # first 自己已经是子项
    assert third.parent_id is None
    assert third.level == 0
    # 父项也不能被塞到别人下面
    other = store.add("新顶层")
    assert store.add("第四层", parent_id=parent.id).parent_id == parent.id
    assert other.parent_id is None


def test_add_child_expands_collapsed_parent(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    store.toggle_collapse(parent.id)
    assert parent.collapsed is True

    later = store.add("后加的", parent_id=parent.id)

    assert parent.collapsed is False   # 新建的子项要能立刻看见
    assert store.active_children(parent.id)[-1].id == later.id
    assert [t.id for t in store.ordered_active()] == [
        parent.id, first.id, second.id, later.id,
    ]


def test_tree_structure_survives_reload(tmp_path):
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    parent, first, second = _group(store)
    store.toggle_collapse(parent.id)

    loaded = TaskStore(path)
    assert loaded.get(first.id).parent_id == parent.id
    assert loaded.get(parent.id).collapsed is True
    assert [t.id for t in loaded.active_children(parent.id)] == [first.id, second.id]


def test_collapsed_parent_hides_children_from_visible_list(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    other = store.add("别的")

    assert [t.id for t in store.visible_active()] == [
        parent.id, first.id, second.id, other.id,
    ]
    store.toggle_collapse(parent.id)
    assert [t.id for t in store.visible_active()] == [parent.id, other.id]
    # 折叠只是显示层的事,数据顺序不变
    assert [t.id for t in store.ordered_active()] == [
        parent.id, first.id, second.id, other.id,
    ]


def test_completing_parent_completes_children(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    store.complete(parent.id)

    assert store.active_tasks() == []
    assert {t.id for t in store.completed_tasks()} == {
        parent.id, first.id, second.id,
    }
    assert len({t.completed_at for t in store.completed_tasks()}) == 1


def test_restoring_parent_restores_cascaded_children(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    store.complete(parent.id)

    store.restore(parent.id)

    assert [t.id for t in store.ordered_active()] == [
        parent.id, first.id, second.id,
    ]


def test_restore_keeps_child_completed_before_the_group(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    store.complete(first.id)          # 子项早就单独完成
    first.completed_at = "2026-01-01T09:00:00"
    store.save()
    store.complete(parent.id)         # 之后整组完成

    store.restore(parent.id)

    assert [t.id for t in store.active_tasks()] == [parent.id, second.id]
    assert store.get(first.id).completed is True


def test_deleting_parent_moves_children_to_history(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    other = store.add("保留")

    store.delete(parent.id)

    assert [t.id for t in store.active_tasks()] == [other.id]
    assert {t.id for t in store.history_tasks()} == {
        parent.id, first.id, second.id,
    }


def test_permanent_delete_removes_children_too(tmp_path):
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    parent, first, second = _group(store)
    other = store.add("保留")

    store.permanent_delete([parent.id])

    assert [t.id for t in store.tasks] == [other.id]
    assert TaskStore(path).get(first.id) is None


def test_restoring_child_whose_parent_is_completed_promotes_it(tmp_path):
    store = TaskStore(path := tmp_path / "tasks.json")
    parent, first, second = _group(store)
    store.complete(parent.id)

    store.restore(first.id)          # 父项还在已完成里,子项得提升为顶层

    assert store.get(first.id).parent_id is None
    assert [t.id for t in store.active_tasks()] == [first.id]
    assert TaskStore(path).get(first.id).parent_id is None


def test_load_promotes_child_of_completed_parent(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps([
        {"id": "p", "text": "父", "completed": True},
        {"id": "c", "text": "子", "parent_id": "p"},
        {"id": "x", "text": "孤儿", "parent_id": "missing"},
    ]), encoding="utf-8")

    store = TaskStore(path)

    assert store.get("c").parent_id is None
    assert store.get("x").parent_id is None


def test_load_drops_third_level(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps([
        {"id": "a", "text": "一"},
        {"id": "b", "text": "二", "parent_id": "a"},
        {"id": "c", "text": "三", "parent_id": "b"},
    ]), encoding="utf-8")

    store = TaskStore(path)

    assert store.get("c").parent_id is None


def test_apply_tree_layout_derives_parents_from_levels(tmp_path):
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    first = store.add("第一")
    second = store.add("第二")
    third = store.add("第三")

    assert store.apply_tree_layout([
        (second.id, 0),
        (first.id, 1),
        (third.id, 1),
    ]) is True

    assert second.parent_id is None
    assert first.parent_id == second.id
    assert third.parent_id == second.id
    assert [t.id for t in store.ordered_active()] == [
        second.id, first.id, third.id,
    ]
    assert [t.id for t in TaskStore(path).ordered_active()] == [
        second.id, first.id, third.id,
    ]


def test_apply_tree_layout_rejects_unknown_ids(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    first = store.add("第一")
    assert store.apply_tree_layout([(first.id, 0), ("ghost", 0)]) is False


def test_apply_tree_layout_clears_stale_collapse(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    store.toggle_collapse(parent.id)
    assert parent.collapsed is True

    # 子项全部移走,父项不再是父项,折叠标记应失效
    store.apply_tree_layout([
        (parent.id, 0), (first.id, 0), (second.id, 0),
    ])

    assert parent.collapsed is False


def test_old_json_without_parent_id_still_loads(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps([
        {"id": "old", "text": "旧任务", "created_at": "2025-01-01T00:00:00"},
    ]), encoding="utf-8")

    store = TaskStore(path)
    assert store.tasks[0].parent_id is None
    assert store.tasks[0].collapsed is False


def test_apply_tree_layout_keeps_parents_at_top_level(tmp_path):
    """带着子项的行不会被排成子项,否则会冒出第三层。"""
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    other = store.add("另一个")

    store.apply_tree_layout([
        (other.id, 0), (parent.id, 1), (first.id, 1), (second.id, 1),
    ])

    assert parent.parent_id is None
    assert first.parent_id == parent.id
    assert store.get(first.id).level == 1


def test_apply_tree_layout_keeps_parents_at_top_level(tmp_path):
    """带着子项的行不会被排成子项,否则会冒出第三层。"""
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    other = store.add("另一个")

    store.apply_tree_layout([
        (other.id, 0), (parent.id, 1), (first.id, 1), (second.id, 1),
    ])

    assert parent.parent_id is None
    assert first.parent_id == parent.id
    assert store.get(first.id).level == 1


def test_history_child_keeps_parent_link_after_reload(tmp_path):
    """历史项要能一直标出上级,重启后不能把这条线索洗掉。"""
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    parent, first, second = _group(store)

    store.complete(first.id)     # 子项先单独完成
    store.complete(parent.id)    # 之后整组完成

    loaded = TaskStore(path)
    assert loaded.get(first.id).parent_id == parent.id
    assert loaded.get(second.id).parent_id == parent.id

    # 但活跃子项挂在不可见的父项下仍要被提升,否则列表里根本看不到它
    orphan = TaskStore(tmp_path / "other.json")
    p = orphan.add("父项")
    c = orphan.add("子项", parent_id=p.id)
    orphan.complete(p.id)
    c.completed = False          # 人为造出"父项已完成、子项还活跃"
    c.completed_at = None
    orphan.save()

    reloaded = TaskStore(tmp_path / "other.json")
    assert reloaded.get(c.id).parent_id is None


def test_history_child_keeps_parent_link_after_reload(tmp_path):
    """历史项要能一直标出上级,重启后不能把这条线索洗掉。"""
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    parent, first, second = _group(store)

    store.complete(first.id)     # 子项先单独完成
    store.complete(parent.id)    # 之后整组完成

    loaded = TaskStore(path)
    assert loaded.get(first.id).parent_id == parent.id
    assert loaded.get(second.id).parent_id == parent.id

    # 但活跃子项挂在不可见的父项下仍要被提升,否则列表里根本看不到它
    orphan = TaskStore(tmp_path / "other.json")
    p = orphan.add("父项")
    c = orphan.add("子项", parent_id=p.id)
    orphan.complete(p.id)
    c.completed = False          # 人为造出"父项已完成、子项还活跃"
    c.completed_at = None
    orphan.save()

    reloaded = TaskStore(tmp_path / "other.json")
    assert reloaded.get(c.id).parent_id is None


def test_completed_entries_merge_cascade_children(tmp_path):
    """整组完成时,子项并进父项那一行,只附一个子项数。"""
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    store.complete(parent.id)

    entries = store.completed_entries()
    assert len(entries) == 1
    task, child_count, parent_text = entries[0]
    assert task.id == parent.id
    assert child_count == 2
    assert parent_text == ""
    assert store.is_batch_child(first) is True


def test_completed_entries_keep_child_completed_alone(tmp_path):
    """单独完成的子项仍占一行,并带上上级任务名。"""
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    store.complete(first.id)                 # 子项先单独完成
    first.completed_at = "2026-01-01T09:00:00"
    store.save()
    store.complete(parent.id)                # 之后整组完成

    entries = store.completed_entries()
    by_id = {task.id: (task, count, parent_text) for task, count, parent_text in entries}
    assert by_id[parent.id][1] == 1          # 只剩 second 是连带完成的
    assert by_id[first.id][2] == "本周"       # 单独完成的子项标出上级
    assert by_id[first.id][1] == 0
    assert store.is_batch_child(first) is False


def test_completed_entries_skip_deleted_children(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    store.complete(parent.id)
    store.delete(first.id)                   # 连带完成后再删掉其中一个子项

    entries = store.completed_entries()

    assert [task.id for task, _, _ in entries] == [parent.id]
    assert entries[0][1] == 1


def test_completed_entries_merge_cascade_children(tmp_path):
    """整组完成时,子项并进父项那一行,只附一个子项数。"""
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    store.complete(parent.id)

    entries = store.completed_entries()
    assert len(entries) == 1
    task, child_count, parent_text = entries[0]
    assert task.id == parent.id
    assert child_count == 2
    assert parent_text == ""
    assert store.is_batch_child(first) is True


def test_completed_entries_keep_child_completed_alone(tmp_path):
    """单独完成的子项仍占一行,并带上上级任务名。"""
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    store.complete(first.id)                 # 子项先单独完成
    first.completed_at = "2026-01-01T09:00:00"
    store.save()
    store.complete(parent.id)                # 之后整组完成

    entries = store.completed_entries()
    by_id = {task.id: (task, count, parent_text) for task, count, parent_text in entries}
    assert by_id[parent.id][1] == 1          # 只剩 second 是连带完成的
    assert by_id[first.id][2] == "本周"       # 单独完成的子项标出上级
    assert by_id[first.id][1] == 0
    assert store.is_batch_child(first) is False


def test_completed_entries_skip_deleted_children(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    store.complete(parent.id)
    store.delete(first.id)                   # 连带完成后再删掉其中一个子项

    entries = store.completed_entries()

    assert [task.id for task, _, _ in entries] == [parent.id]
    assert entries[0][1] == 1
