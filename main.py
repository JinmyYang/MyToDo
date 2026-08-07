"""MyToDo 桌面任务便签 —— 入口。

运行:python main.py
数据存于软件目录下的 .sticky_tasks 文件夹。
"""

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from sticky_tasks import APP_NAME
from sticky_tasks.app_paths import DATA_DIR, SETTINGS_FILE, TASKS_FILE, software_dir
from sticky_tasks.app_settings import AppSettings
from sticky_tasks import dialogs
from sticky_tasks.i18n import set_language, t
from sticky_tasks.main_window import MainWindow
from sticky_tasks.single_instance import SingleInstance
from sticky_tasks.task_store import TaskStore


def _icon_file() -> "Path":
    """图标路径:源码态在软件目录 assets/;打包态 PyInstaller 会放进 _internal。"""
    candidate = software_dir() / "assets" / "icon.ico"
    if candidate.exists():
        return candidate
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "assets" / "icon.ico"
    return candidate


ICON_FILE = _icon_file()
CRASH_LOG = DATA_DIR / "crash.log"
MAX_CRASH_LOG_BYTES = 256 * 1024


def _handle_exception(exc_type, exc_value, exc_tb):
    """全局崩溃兜底:堆栈追加写入 crash.log,并给用户一个提示。"""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # 超过体积上限时只保留后半部分,避免无限增长
        if CRASH_LOG.exists() and CRASH_LOG.stat().st_size > MAX_CRASH_LOG_BYTES:
            old = CRASH_LOG.read_text(encoding="utf-8", errors="replace")
            CRASH_LOG.write_text(old[len(old) // 2:], encoding="utf-8")
        with CRASH_LOG.open("a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.now().isoformat()} =====\n")
            f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    except OSError:
        pass
    dialogs.critical(
        None, APP_NAME, t("app.crash"),
    )
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def main():
    sys.excepthook = _handle_exception
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # 界面语言在构建任何窗口前确定(改语言后重启生效)
    set_language(AppSettings.load(SETTINGS_FILE).language)
    if ICON_FILE.exists():
        app.setWindowIcon(QIcon(str(ICON_FILE)))
    # 单实例保护:测试环境可设 STICKY_SKIP_SINGLE_INSTANCE=1 跳过;
    # --restarting 为自动重启的新进程,等待旧进程释放锁而不是立即报错
    guard = None
    restarting = "--restarting" in sys.argv
    if not os.environ.get("STICKY_SKIP_SINGLE_INSTANCE"):
        guard = SingleInstance(DATA_DIR)
        if not guard.try_acquire(5000 if restarting else 0):
            dialogs.information(
                None, APP_NAME, t("app.running", name=APP_NAME),
            )
            return
    store = TaskStore(TASKS_FILE)
    window = MainWindow(store, settings_path=SETTINGS_FILE)
    window.show()
    if store.load_warning:
        QTimer.singleShot(
            0,
            lambda: dialogs.warning(
                window, t("app.data_warning"), store.load_warning,
            ),
        )
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
