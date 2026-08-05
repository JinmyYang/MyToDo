"""重启软件(语言切换等场景)。

独立成模块避免循环依赖:settings_dialog 需要调用重启,
而 main.py 依赖 main_window → settings_dialog,不能被反向 import。
"""

import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication


def restart_app():
    """带 --restarting 标记启动新进程,然后退出当前进程。

    新进程拿单实例锁时会等待旧进程释放(见 main.py),
    不会被误判为"重复打开"。
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后:可执行文件自身即入口
        cmd = [sys.executable]
    else:
        # 源码运行:python main.py
        cmd = [sys.executable, str(Path(sys.argv[0]).resolve())]
    cmd.append("--restarting")
    kwargs = {}
    if sys.platform == "win32":
        # 脱离控制台,不弹黑窗
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    subprocess.Popen(cmd, **kwargs)
    app = QApplication.instance()
    if app is not None:
        app.quit()
