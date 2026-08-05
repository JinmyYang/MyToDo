"""单实例锁:防止多开程序导致两个实例互相覆盖数据文件。"""

from pathlib import Path

from PySide6.QtCore import QLockFile


class SingleInstance:
    """进程存活期间持有锁文件;进程退出(含崩溃)后锁自动释放。"""

    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(data_dir / "app.lock"))
        self._lock.setStaleLockTime(0)  # 崩溃残留锁由 QLockFile 自动识别清理

    def try_acquire(self, timeout_ms: int = 0) -> bool:
        # 0 = 不等待,拿不到立即返回;重启场景传正值等待旧进程释放锁
        return self._lock.tryLock(timeout_ms)
