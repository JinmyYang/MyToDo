"""TaskStore 数据层单元测试。"""

import json
from pathlib import Path

from sticky_tasks.task_store import TaskStore


def _group(store):
    """建一个"父项 + 两个子项"的结构,返回 (父, 子1, 子2)。"""
    parent = store.add("本周")
    first = store.add("写周报")
    second = store.add("回邮件")
    assert store.indent(first.id) is True
    assert store.indent(second.id) is True
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


def test_reorder_active_tasks_persists_and_preserves_history_slots(tmp_path):
    path = tmp_path / "tasks.json"
    store = TaskStore(path)
    first = store.add("第一")
    completed = store.add("已完成")
    second = store.add("第二")
    third = store.add("第三")
    store.complete(completed.id)

    assert store.reorder_active([third.id, first.id, second.id]) is True
    assert [task.id for task in store.tasks] == [third.id, completed.id, first.id, second.id]

    loaded = TaskStore(path)
    assert [task.id for task in loaded.active_tasks()] == [third.id, first.id, second.id]
    assert loaded.reorder_active([third.id, first.id]) is False


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


def test_indent_attaches_to_previous_top_level_task(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    assert first.parent_id == parent.id
    assert second.parent_id == parent.id
    assert first.level == 1 and second.level == 1
    assert [t.id for t in store.ordered_active()] == [parent.id, first.id, second.id]
    assert [t.id for t in store.active_children(parent.id)] == [first.id, second.id]


def test_indent_needs_a_previous_sibling(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    only = store.add("唯一一条")
    assert store.indent(only.id) is False
    assert only.parent_id is None


def test_indent_stops_at_two_levels(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)

    # 子项不能再缩进(否则就是三层)
    assert store.indent(second.id) is False
    assert second.parent_id == parent.id
    # 已经是父项的任务也不能被缩进
    third = store.add("另一个")
    store.indent(third.id)          # 变成 parent 的子项
    assert store.indent(parent.id) is False
    assert parent.parent_id is None


def test_indent_places_task_after_existing_children(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    later = store.add("后加的")

    assert store.indent(later.id) is True
    assert store.active_children(parent.id)[-1].id == later.id
    assert [t.id for t in store.ordered_active()] == [
        parent.id, first.id, second.id, later.id,
    ]


def test_outdent_promotes_task_below_the_group(tmp_path):
    store = TaskStore(tmp_path / "tasks.json")
    parent, first, second = _group(store)
    other = store.add("另一件事")

    assert store.outdent(first.id) is True
    assert first.parent_id is None
    assert [t.id for t in store.ordered_active()] == [
        parent.id, second.id, first.id, other.id,
    ]
    assert store.outdent(parent.id) is False


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
