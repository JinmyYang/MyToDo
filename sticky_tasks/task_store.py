"""数据层:任务模型与 JSON 持久化。

不依赖任何 Qt UI,可单独单元测试。
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from .json_io import atomic_write_text


class Task:
    """单个任务。"""

    def __init__(
        self, id, text, completed=False, created_at=None, completed_at=None,
        deleted=False, deleted_at=None,
    ):
        self.id = id
        self.text = text
        self.completed = completed
        self.created_at = created_at or datetime.now().isoformat()
        self.completed_at = completed_at
        self.deleted = deleted
        self.deleted_at = deleted_at

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "deleted": self.deleted,
            "deleted_at": self.deleted_at,
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
        )


class TaskStore:
    """任务存储:增删、完成、恢复、JSON 保存/加载。"""

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

    def active_tasks(self):
        return [t for t in self.tasks if not t.completed and not t.deleted]

    def completed_tasks(self):
        tasks = [t for t in self.tasks if t.completed and not t.deleted]
        return sorted(
            tasks,
            key=lambda t: t.completed_at or t.created_at or "",
            reverse=True,
        )

    def history_tasks(self):
        """返回已完成或已删除任务，最近发生变更的排在前面。"""
        tasks = [t for t in self.tasks if t.completed or t.deleted]
        return sorted(
            tasks,
            key=lambda t: t.deleted_at or t.completed_at or t.created_at or "",
            reverse=True,
        )

    # ---- 变更 ----
    def add(self, text=""):
        task = Task(id=str(uuid.uuid4()), text=text)
        self.tasks.append(task)
        self.save()
        return task

    def update_text(self, task_id, text):
        t = self.get(task_id)
        if t is not None:
            t.text = text
            self.save()

    def reorder_active(self, task_ids):
        """按给定 ID 顺序重排活跃任务，并保留历史任务的相对位置。"""
        active = self.active_tasks()
        current_ids = [task.id for task in active]
        ordered_ids = list(task_ids)
        if len(ordered_ids) != len(current_ids) or set(ordered_ids) != set(current_ids):
            return False
        if ordered_ids == current_ids:
            return False

        active_by_id = {task.id: task for task in active}
        reordered = iter(active_by_id[task_id] for task_id in ordered_ids)
        self.tasks = [
            next(reordered) if not task.completed and not task.deleted else task
            for task in self.tasks
        ]
        self.save()
        return True

    def complete(self, task_id):
        t = self.get(task_id)
        if t is not None:
            t.completed = True
            t.completed_at = datetime.now().isoformat()
            t.deleted = False
            t.deleted_at = None
            self.save()
        return t

    def restore(self, task_id):
        t = self.get(task_id)
        if t is not None:
            t.completed = False
            t.completed_at = None
            t.deleted = False
            t.deleted_at = None
            self.save()
        return t

    def delete(self, task_id):
        """把任务移入历史记录，不立即永久删除。"""
        task = self.get(task_id)
        if task is not None:
            task.deleted = True
            task.deleted_at = datetime.now().isoformat()
            self.save()
        return task

    def restore_many(self, task_ids):
        ids = set(task_ids)
        restored = []
        for task in self.tasks:
            if task.id in ids and (task.completed or task.deleted):
                task.completed = False
                task.completed_at = None
                task.deleted = False
                task.deleted_at = None
                restored.append(task)
        if restored:
            self.save()
        return restored

    def permanent_delete(self, task_ids):
        ids = set(task_ids)
        removed = [task for task in self.tasks if task.id in ids]
        if removed:
            self.tasks = [task for task in self.tasks if task.id not in ids]
            self.save()
        return removed
