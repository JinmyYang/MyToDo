"""软件目录与本地数据文件路径。

用户数据存放在 %APPDATA%\\MyToDo,与安装目录解耦:
安装/更新/卸载覆盖程序文件时不会碰到数据。
旧便携版(程序目录内 .sticky_tasks)的数据在首次启动时一次性迁入。
"""

import os
import shutil
import sys
from pathlib import Path

APP_DIR_NAME = "MyToDo"
LEGACY_DIR_NAME = ".sticky_tasks"
_DATA_FILES = ("tasks.json", "settings.json")


def software_dir() -> Path:
    """返回源码入口或打包后可执行文件所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _migrate_legacy_data(target: Path) -> None:
    """新数据目录为空且程序目录旁有旧版数据时,复制 tasks/settings 过来。

    只迁一次:目标目录已有任何文件即跳过;只复制不删除旧文件,
    失败静默(不影响启动,用户仍得到全新空数据)。
    """
    try:
        if any(target.iterdir()):
            return
    except FileNotFoundError:
        pass
    except OSError:
        return
    legacy = software_dir() / LEGACY_DIR_NAME
    if not legacy.is_dir():
        return
    for name in _DATA_FILES:
        src = legacy / name
        if src.is_file():
            try:
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target / name)
            except OSError:
                pass


def data_dir() -> Path:
    """用户数据目录(%APPDATA%\\MyToDo),取用时顺带做旧数据迁移。"""
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    target = Path(base) / APP_DIR_NAME
    _migrate_legacy_data(target)
    return target


DATA_DIR = data_dir()
TASKS_FILE = DATA_DIR / "tasks.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
