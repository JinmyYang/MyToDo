"""桌面任务便签 —— 入口。

运行:python main.py
数据存于软件目录下的 .sticky_tasks 文件夹。
"""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from sticky_tasks.app_paths import SETTINGS_FILE, TASKS_FILE, migrate_legacy_data
from sticky_tasks.main_window import MainWindow
from sticky_tasks.task_store import TaskStore


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("桌面便签")
    migration_errors = migrate_legacy_data()
    store = TaskStore(TASKS_FILE)
    window = MainWindow(store, settings_path=SETTINGS_FILE)
    window.show()
    warnings = migration_errors + ([store.load_warning] if store.load_warning else [])
    if warnings:
        QTimer.singleShot(
            0,
            lambda message="\n".join(warnings): QMessageBox.warning(
                window, "本地数据提示", message,
            ),
        )
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
