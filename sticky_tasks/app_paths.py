"""软件目录与本地数据文件路径。"""

import sys
from pathlib import Path


def software_dir() -> Path:
    """返回源码入口或打包后可执行文件所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


DATA_DIR = software_dir() / ".sticky_tasks"
TASKS_FILE = DATA_DIR / "tasks.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
