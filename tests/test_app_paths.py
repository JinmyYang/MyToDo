"""软件目录数据路径测试。"""

import sys

from sticky_tasks.app_paths import software_dir


def test_source_run_uses_project_directory():
    assert (software_dir() / "main.py").is_file()


def test_packaged_run_uses_executable_directory(monkeypatch, tmp_path):
    executable = tmp_path / "StickyTasks.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    assert software_dir() == tmp_path
