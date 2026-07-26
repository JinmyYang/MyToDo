"""桌面任务便签 —— 入口。

运行:python main.py
数据存于:~/.sticky_tasks/tasks.json
"""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from sticky_tasks.main_window import MainWindow
from sticky_tasks.task_store import TaskStore

DATA_DIR = Path.home() / ".sticky_tasks"
DATA_FILE = DATA_DIR / "tasks.json"
SETTINGS_FILE = DATA_DIR / "settings.json"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("桌面便签")
    store = TaskStore(DATA_FILE)
    window = MainWindow(store, settings_path=SETTINGS_FILE)
    window.show()
    if store.load_warning:
        QTimer.singleShot(
            0,
            lambda message=store.load_warning: QMessageBox.warning(
                window, "任务数据恢复", message,
            ),
        )
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
