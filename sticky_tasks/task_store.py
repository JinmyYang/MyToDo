"""数据层:任务模型与 JSON 持久化。

不依赖任何 Qt UI,可单独单元测试。

层级用"扁平存储 + parent_id"表达:任务仍是一条条排在一维数组里,
父项与子项的先后关系由数组顺序决定(父项后紧跟它的子项)。
这样既能保住既有的简单存储格式,又能支持一层分组。
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from .json_io import atomic_write_text

# 最多两层:顶层任务 + 一层子任务。再深在窄便签里排版会挤成一团。
MAX_DEPTH = 2


class Task:
    """单个任务。"""

    def __init__(
        self, id, text, completed=False, created_at=None, completed_at=None,
        deleted=False, deleted_at=None, parent_id=None, collapsed=False,
    ):
        self.id = id
        self.text = text
        self.completed = completed
        self.created_at = created_at or datetime.now().isoformat()
        self.completed_at = completed_at
        self.deleted = deleted
        self.deleted_at = deleted_at
        self.parent_id = parent_id or None   # 上级任务 id;None 表示顶层
        self.collapsed = bool(collapsed)     # 是否折叠子项(仅对父项有意义)

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "deleted": self.deleted,
            "deleted_at": self.deleted_at,
            "parent_id": self.parent_id,
            "collapsed": self.collapsed,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            text=d.get("text", ""),
            completed=d.get("completed", False),
            created_at=d.get("created_at"),
            completed_at=d.get("completed_at"),
            deleted=d.get("deleted", False),
            deleted_at=d.get("deleted_at"),
            parent_id=d.get("parent_id"),
            collapsed=d.get("collapsed", False),
        )

    @property
    def level(self):
        """0 = 顶层,1 = 子项。层级由 parent_id 推导,不单独存储。"""
        return 1 if self.parent_id else 0


class TaskStore:
    """任务存储:增删、完成、恢复、层级调整、JSON 保存/加载。"""

    def __init__(self, path):
        self.path = Path(path)
        self.tasks = []
        self.load_warning = None
        self.corrupt_backup_path = None
        self.load()

    # ---- 持久化 ----
    def load(self):
        self.tasks = []
        self.load_warning = None
        self.corrupt_backup_path = None
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            self.load_warning = f"任务文件读取失败：{exc}"
            return
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._quarantine_corrupt_file(f"任务文件无法解析：{exc}")
            return
        if not isinstance(data, list):
            self._quarantine_corrupt_file("任务文件格式错误：顶层内容必须是列表")
            return
        for d in data:
            try:
                self.tasks.append(Task.from_dict(d))
            except (KeyError, TypeError):
                continue  # 跳过单条坏数据
        self._normalize_tree()

    def save(self):
        atomic_write_text(
            self.path,
            json.dumps(
                [t.to_dict() for t in self.tasks],
                ensure_ascii=False,
                indent=2,
            ),
        )

    def _quarantine_corrupt_file(self, reason):
        """把损坏文件移走，避免后续保存覆盖唯一的可恢复副本。"""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = self.path.with_name(f"{self.path.name}.corrupt-{stamp}")
        try:
            os.replace(self.path, backup)
        except OSError as exc:
            self.load_warning = f"{reason}；损坏文件备份失败：{exc}"
            return
        self.corrupt_backup_path = backup
        self.load_warning = f"{reason}；原文件已备份到：{backup}"

    # ---- 查询 ----
    def get(self, task_id):
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    @staticmethod
    def _is_active(task):
        return not task.completed and not task.deleted

    def active_tasks(self):
        return [t for t in self.tasks if self._is_active(t)]

    def completed_tasks(self):
        tasks = [t for t in self.tasks if t.completed and not t.deleted]
        return sorted(
            tasks,
            key=lambda t: t.completed_at or t.created_at or "",
            reverse=True,
        )

    def completed_entries(self):
        """已完成面板的数据源:[(task, 上级任务名, 是否要连带恢复上级)]。

        每条已完成任务各占一行(子项也单独列出来,点了就恢复它);
        但上级如果也在历史里,恢复时会先把上级带回来,子项才有位置可待。
        """
        entries = []
        for task in self.completed_tasks():
            parent = self.get(task.parent_id) if task.parent_id else None
            parent_text = (parent.text or "") if parent is not None else ""
            with_parent = parent is not None and not self._is_active(parent)
            entries.append((task, parent_text, with_parent))
        return entries

    def history_tasks(self):
        """返回已完成或已删除任务，最近发生变更的排在前面。"""
        tasks = [t for t in self.tasks if t.completed or t.deleted]
        return sorted(
            tasks,
            key=lambda t: t.deleted_at or t.completed_at or t.created_at or "",
            reverse=True,
        )

    # ---- 层级 ----
    def children_of(self, task_id):
        return [t for t in self.tasks if t.parent_id == task_id]

    def active_children(self, task_id):
        return [t for t in self.children_of(task_id) if self._is_active(t)]

    def descendants(self, task_id, _seen=None):
        """所有下级任务(含已完成/已删除),带环保护。"""
        seen = _seen if _seen is not None else {task_id}
        found = []
        for child in self.children_of(task_id):
            if child.id in seen:
                continue
            seen.add(child.id)
            found.append(child)
            found.extend(self.descendants(child.id, seen))
        return found

    def _tree_order(self, tasks):
        """把一维数组排成树序:每个父项后面紧跟它的子项。"""
        by_parent = {}
        tops = []
        for task in tasks:
            if task.parent_id:
                by_parent.setdefault(task.parent_id, []).append(task)
            else:
                tops.append(task)
        ordered = []
        for top in tops:
            ordered.append(top)
            ordered.extend(by_parent.get(top.id, ()))
        known = {task.id for task in ordered}
        # 父项不在本次集合里的子项(理论上升级后不会出现):按顶层处理,避免丢行
        ordered.extend(task for task in tasks if task.id not in known)
        return ordered

    def ordered_active(self):
        """全部活跃任务,树序(含折叠父项下的子项)。"""
        return self._tree_order(self.active_tasks())

    def visible_active(self):
        """列表中真正可见的活跃任务:折叠父项下的子项被跳过。"""
        visible = []
        for task in self.ordered_active():
            parent = self.get(task.parent_id) if task.parent_id else None
            if parent is not None and parent.collapsed:
                continue
            visible.append(task)
        return visible

    def _depth(self, task):
        """任务在自己的分支里所处的层数(顶层 = 1),带环保护。"""
        depth = 1
        seen = {task.id}
        parent = self.get(task.parent_id) if task.parent_id else None
        while parent is not None and parent.id not in seen:
            depth += 1
            seen.add(parent.id)
            parent = self.get(parent.parent_id) if parent.parent_id else None
        return depth

    def _normalize_tree(self):
        """修正非法父子关系:父项不存在、层级超限、活跃子项挂在不可见的父项下。

        子项挂在已完成/已删除的父项下会变成"看不见的孤儿",这种必须提升为顶层;
        但历史项(自己已完成/已删除)本来就平铺展示,保留 parent_id 才能在历史窗口里
        标出它属于哪条任务,所以不拆。
        """
        by_id = {task.id: task for task in self.tasks}
        for task in self.tasks:
            parent = by_id.get(task.parent_id) if task.parent_id else None
            if parent is None or parent is task:
                task.parent_id = None
                continue
            if self._depth(task) > MAX_DEPTH:
                task.parent_id = None
                continue
            if self._is_active(task) and not self._is_active(parent):
                task.parent_id = None

    def _promote_if_orphaned(self, task):
        """父项不存在或不在活跃列表时,把任务提升为顶层。"""
        if not task.parent_id:
            return
        parent = self.get(task.parent_id)
        if parent is None or not self._is_active(parent):
            task.parent_id = None

    def toggle_collapse(self, task_id):
        task = self.get(task_id)
        if task is None or not self.active_children(task_id):
            return None
        task.collapsed = not task.collapsed
        self.save()
        return task.collapsed

    def apply_tree_layout(self, rows):
        """按 [(task_id, level)] 重排任务并重设父子关系。

        层级 1 的任务挂到它前面最近的顶层任务下(因此数组顺序即树序)。
        用于拖拽后的整体落盘,避免逐条改父子关系时出现中间态。
        """
        active = {t.id: t for t in self.active_tasks()}
        ordered_ids = [task_id for task_id, _ in rows]
        if len(ordered_ids) != len(active) or set(ordered_ids) != set(active):
            return False

        has_children = {task.parent_id for task in self.active_tasks() if task.parent_id}
        resolved = []
        last_top = None
        for task_id, level in rows:
            parent_id = None
            # 自己带着子项的行不能再变成子项,否则就成了第三层
            if level >= 1 and last_top is not None and task_id not in has_children:
                parent_id = last_top
            if parent_id is None:
                last_top = task_id
            resolved.append((active[task_id], parent_id))

        # 只剩顶层行的任务不能再假装有子项,否则新子项一进来就"凭空折叠"
        parents = {parent_id for _, parent_id in resolved if parent_id}
        reordered = iter(task for task, _ in resolved)
        self.tasks = [
            next(reordered) if self._is_active(task) else task
            for task in self.tasks
        ]
        for task, parent_id in resolved:
            task.parent_id = parent_id
            if task.collapsed and task.id not in parents:
                task.collapsed = False
        self.save()
        return True

    # ---- 变更 ----
    def add(self, text="", parent_id=None):
        parent = self.get(parent_id) if parent_id else None
        if parent is None or not self._is_active(parent) or parent.parent_id:
            parent_id = None
        else:
            parent.collapsed = False    # 新子项要能立刻看见
        task = Task(id=str(uuid.uuid4()), text=text, parent_id=parent_id)
        self.tasks.append(task)
        self.save()
        return task

    def update_text(self, task_id, text):
        t = self.get(task_id)
        if t is not None:
            t.text = text
            self.save()

    def complete(self, task_id):
        """完成任务;父项完成时子项一并完成,否则它们会留在列表里失去归属。"""
        t = self.get(task_id)
        if t is not None:
            stamp = datetime.now().isoformat()
            t.completed = True
            t.completed_at = stamp
            t.deleted = False
            t.deleted_at = None
            for child in self.descendants(task_id):
                if not self._is_active(child):
                    continue
                child.completed = True
                child.completed_at = stamp
            self.save()
        return t

    def restore(self, task_id):
        """恢复任务。

        - 恢复父项:连带把"同一批完成"的子项一起带回来(整组复位)
        - 恢复子项:只把上级恢复成容器,点哪条回哪条,兄弟项留在已完成里
        子项单独回升到顶层会丢掉它属于哪个分组,所以必须先把上级带回来。
        """
        t = self.get(task_id)
        if t is None or self._is_active(t):
            return t
        if t.parent_id:
            parent = self.get(t.parent_id)
            if parent is not None and not self._is_active(parent):
                self._restore_tasks([parent])
                parent.collapsed = False    # 恢复出来的子项得看得见
        self._restore_tasks([t] + self._same_batch_descendants(t))
        return t

    def _restore_tasks(self, tasks):
        """把一批任务改回活跃,并挪到数组末尾(与 UI 追加到列表末尾一致)。"""
        for task in tasks:
            task.completed = False
            task.completed_at = None
            task.deleted = False
            task.deleted_at = None
            self._promote_if_orphaned(task)
        for task in tasks:
            if task in self.tasks:
                self.tasks.remove(task)
        self.tasks.extend(tasks)
        self.save()

    def _same_batch_descendants(self, task):
        """跟父项同一批完成的子项;更早就完成的子项保持原状,不被连带恢复。"""
        batch = []
        for child in self.descendants(task.id):
            if not (child.completed or child.deleted):
                continue
            if task.completed_at is not None and child.completed_at is not None:
                if child.completed_at < task.completed_at:
                    continue
            batch.append(child)
        return batch

    def delete(self, task_id):
        """把任务连同其子项移入历史记录，不立即永久删除。"""
        task = self.get(task_id)
        if task is not None:
            stamp = datetime.now().isoformat()
            for item in [task] + self.descendants(task_id):
                if item.deleted:
                    continue
                item.deleted = True
                item.deleted_at = stamp
            self.save()
        return task

    def restore_many(self, task_ids):
        ids = set(task_ids)
        for task_id in list(ids):
            ids.update(child.id for child in self.descendants(task_id))
        restored = []
        for task in self.tasks:
            if task.id in ids and (task.completed or task.deleted):
                task.completed = False
                task.completed_at = None
                task.deleted = False
                task.deleted_at = None
                self._promote_if_orphaned(task)
                restored.append(task)
        if restored:
            self.save()
        return restored

    def permanent_delete(self, task_ids):
        ids = set(task_ids)
        for task_id in list(ids):
            ids.update(child.id for child in self.descendants(task_id))
        removed = [task for task in self.tasks if task.id in ids]
        if removed:
            self.tasks = [task for task in self.tasks if task.id not in ids]
            self.save()
        return removed
