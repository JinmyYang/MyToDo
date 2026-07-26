"""外观设置持久化与字体选择测试。"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import pytest
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from sticky_tasks.app_settings import AppSettings
from sticky_tasks.settings_dialog import SettingsWindow


@pytest.fixture
def app():
    return QApplication.instance() or QApplication(sys.argv)


def test_font_settings_persist_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = AppSettings(
        font_family="Arial",
        font_size=16,
    )
    settings.save(path)

    loaded = AppSettings.load(path)
    assert loaded.font_family == "Arial"
    assert loaded.font_size == 16
    assert list(tmp_path.glob(".settings.json.*.tmp")) == []


def test_window_geometry_persists_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = AppSettings(
        window_x=120,
        window_y=80,
        window_width=360,
        window_height=520,
    )
    settings.save(path)

    loaded = AppSettings.load(path)
    assert (loaded.window_x, loaded.window_y) == (120, 80)
    assert (loaded.window_width, loaded.window_height) == (360, 520)


def test_font_combo_updates_family_without_system_dialog(app):
    settings = AppSettings()
    window = SettingsWindow(settings)
    current = window._font_combo.currentFont().family()
    family = next(
        (name for name in QFontDatabase.families() if name != current),
        current,
    )

    window._font_combo.setCurrentFont(QFont(family))
    window._on_font_changed(window._font_combo.currentFont())

    assert settings.font_family == window._font_combo.currentFont().family()
