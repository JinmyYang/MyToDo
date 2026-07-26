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
    ):
        self.id = id
        self.text = text
        self.completed = completed
        self.created_at = created_at or datetime.now().isoformat()
        self.completed_at = completed_at

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            text=d.get("text", ""),
            completed=d.get("completed", False),
            created_at=d.get("created_at"),
            completed_at=d.get("completed_at"),
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
        return [t for t in self.tasks if not t.completed]

    def completed_tasks(self):
        tasks = [t for t in self.tasks if t.completed]
        return sorted(
            tasks,
            key=lambda t: t.completed_at or t.created_at or "",
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

    def complete(self, task_id):
        t = self.get(task_id)
        if t is not None:
            t.completed = True
            t.completed_at = datetime.now().isoformat()
            self.save()
        return t

    def restore(self, task_id):
        t = self.get(task_id)
        if t is not None:
            t.completed = False
            t.completed_at = None
            self.save()
        return t

    def delete(self, task_id):
        for index, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(index)
                self.save()
                return task, index
        return None

    def reinstate(self, task, index):
        """把刚删除的任务放回原位置，供 UI 的短暂撤销使用。"""
        if self.get(task.id) is not None:
            return task
        self.tasks.insert(max(0, min(index, len(self.tasks))), task)
        self.save()
        return task
