"""软件目录与本地数据文件路径。"""

import shutil
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
LEGACY_DATA_DIR = Path.home() / ".sticky_tasks"


def migrate_legacy_data(
    data_dir: Path = DATA_DIR,
    legacy_data_dir: Path = LEGACY_DATA_DIR,
) -> list[str]:
    """新位置无对应文件时，从原用户目录复制已有数据。"""
    errors = []
    for name in ("tasks.json", "settings.json"):
        source = legacy_data_dir / name
        target = data_dir / name
        if not source.exists() or target.exists():
            continue
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        except OSError as exc:
            errors.append(f"{name} 迁移失败：{exc}")
    return errors
