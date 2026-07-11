"""数据层:任务模型与 JSON 持久化。

不依赖任何 Qt UI,可单独单元测试。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path


class Task:
    """单个任务。"""

    def __init__(self, id, text, completed=False, created_at=None):
        self.id = id
        self.text = text
        self.completed = completed
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "completed": self.completed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d["id"],
            text=d.get("text", ""),
            completed=d.get("completed", False),
            created_at=d.get("created_at"),
        )


class TaskStore:
    """任务存储:增删、完成、恢复、JSON 保存/加载。"""

    def __init__(self, path):
        self.path = Path(path)
        self.tasks = []
        self.load()

    # ---- 持久化 ----
    def load(self):
        self.tasks = []
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return  # 损坏文件不崩溃,从空开始
        if not isinstance(data, list):
            return
        for d in data:
            try:
                self.tasks.append(Task.from_dict(d))
            except (KeyError, TypeError):
                continue  # 跳过单条坏数据

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([t.to_dict() for t in self.tasks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- 查询 ----
    def get(self, task_id):
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def active_tasks(self):
        return [t for t in self.tasks if not t.completed]

    def completed_tasks(self):
        return [t for t in self.tasks if t.completed]

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
            self.save()
        return t

    def restore(self, task_id):
        t = self.get(task_id)
        if t is not None:
            t.completed = False
            self.save()
        return t

    def delete(self, task_id):
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self.save()
