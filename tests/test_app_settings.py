"""外观设置持久化与字体选择测试。"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import QApplication, QColorDialog

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
    current = window._font_combo.currentText()
    family = next(
        (name for name in QFontDatabase.families() if name != current),
        current,
    )

    window._font_combo.setCurrentText(family)
    window._on_font_activated(family)

    assert settings.font_family == family


def test_font_search_uses_plain_editable_combo_and_contains_matching(app):
    window = SettingsWindow(AppSettings())
    assert window._font_combo.isEditable()
    assert window._font_combo.completer().filterMode() == Qt.MatchContains
    assert window._font_combo.count() == len(QFontDatabase.families())


def test_custom_colors_and_preset_persist_roundtrip(app, tmp_path):
    path = tmp_path / "settings.json"
    settings = AppSettings()
    window = SettingsWindow(settings)
    QColorDialog.setCustomColor(0, QColor("#123456"))
    window._remember_custom_colors()
    settings.bg_color = "#334455"
    settings.text_color = "#f1f2f3"
    settings.font_size = 17
    window._save_custom_preset()
    settings.save(path)

    loaded = AppSettings.load(path)
    assert loaded.custom_colors[0] == "#123456"
    assert loaded.custom_preset["bg"] == "#334455"
    assert loaded.custom_preset["text"] == "#f1f2f3"
    assert loaded.custom_preset["size"] == 17

    loaded.bg_color = "#000000"
    loaded.text_color = "#ffffff"
    loaded.font_size = 10
    reloaded_window = SettingsWindow(loaded)
    reloaded_window._apply_custom_preset()
    assert loaded.bg_color == "#334455"
    assert loaded.text_color == "#f1f2f3"
    assert loaded.font_size == 17
