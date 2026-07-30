"""软件目录数据路径与旧数据迁移测试。"""

import sys

from sticky_tasks.app_paths import migrate_legacy_data, software_dir


def test_source_run_uses_project_directory():
    assert (software_dir() / "main.py").is_file()


def test_packaged_run_uses_executable_directory(monkeypatch, tmp_path):
    executable = tmp_path / "StickyTasks.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    assert software_dir() == tmp_path


def test_legacy_data_is_copied_without_overwriting_new_data(tmp_path):
    legacy_dir = tmp_path / "legacy"
    data_dir = tmp_path / "software" / ".sticky_tasks"
    legacy_dir.mkdir()
    data_dir.mkdir(parents=True)
    (legacy_dir / "tasks.json").write_text("old tasks", encoding="utf-8")
    (legacy_dir / "settings.json").write_text("old settings", encoding="utf-8")
    (data_dir / "settings.json").write_text("new settings", encoding="utf-8")

    errors = migrate_legacy_data(data_dir, legacy_dir)

    assert errors == []
    assert (data_dir / "tasks.json").read_text(encoding="utf-8") == "old tasks"
    assert (data_dir / "settings.json").read_text(encoding="utf-8") == "new settings"
