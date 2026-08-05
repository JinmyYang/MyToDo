"""外观设置持久化与字体选择测试。"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import QApplication, QColorDialog

from sticky_tasks.app_settings import AppSettings, MIN_BG_OPACITY
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


def test_background_opacity_starts_at_one_percent(app, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        '{"bg_opacity": 0, "custom_preset": {'
        '"bg": "#25262c", "text": "#e9e9ef", "font": "Arial", '
        '"size": 13, "opacity": 0}}',
        encoding="utf-8",
    )

    loaded = AppSettings.load(path)
    window = SettingsWindow(loaded)

    assert loaded.bg_opacity == MIN_BG_OPACITY
    assert loaded.custom_preset["opacity"] == MIN_BG_OPACITY
    assert window._op_slider.minimum() == MIN_BG_OPACITY
    window._op_slider.setValue(window._op_slider.minimum())
    assert window._op_label.text() == "1%"


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


def test_language_persists_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    settings = AppSettings(language="en")
    settings.save(path)
    assert AppSettings.load(path).language == "en"


def test_language_default_is_zh():
    assert AppSettings().language == "zh"


def test_language_invalid_value_rejected(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"language": "fr"}', encoding="utf-8")
    assert AppSettings.load(path).language == "zh"


def test_settings_window_language_combo_reflects_setting(app):
    settings = AppSettings(language="en")
    window = SettingsWindow(settings)
    assert window._lang_combo.currentData() == "en"
    assert window.windowTitle() == "Settings"

    zh_settings = AppSettings(language="zh")
    zh_window = SettingsWindow(zh_settings)
    assert zh_window._lang_combo.currentData() == "zh"
    assert zh_window.windowTitle() == "设置"


# ---- 语言切换两段式交互(模拟弹窗,无头) ----
def _patch_message_boxes(monkeypatch, answers):
    """模拟 QMessageBox:answers 按弹窗出现顺序作答,True=第一个按钮(AcceptRole)。"""
    from PySide6.QtWidgets import QMessageBox as MB

    state = {"calls": 0}

    def fake_exec(self):
        ans = answers[min(state["calls"], len(answers) - 1)]
        state["calls"] += 1
        role = MB.AcceptRole if ans else MB.RejectRole
        picked = None
        for btn in self.buttons():
            if self.buttonRole(btn) == role:
                picked = btn
                break
        self._fake_picked = picked
        return 0

    monkeypatch.setattr(MB, "exec", fake_exec)
    monkeypatch.setattr(
        MB, "clickedButton", lambda self: getattr(self, "_fake_picked", None),
    )
    return state


def test_language_cancel_reverts_combo(app, monkeypatch):
    from sticky_tasks.i18n import set_language

    _patch_message_boxes(monkeypatch, [False])  # 点"取消"
    settings = AppSettings(language="zh")
    window = SettingsWindow(settings)
    window._lang_combo.setCurrentIndex(1)
    assert settings.language == "zh"          # 未保存
    assert window._lang_combo.currentIndex() == 0  # 下拉框回退
    set_language("zh")


def test_language_confirm_later_saves_without_restart(app, monkeypatch):
    from sticky_tasks import settings_dialog
    from sticky_tasks.i18n import set_language

    _patch_message_boxes(monkeypatch, [True, False])  # 确认 + 稍后
    restarted = []
    monkeypatch.setattr(settings_dialog, "restart_app", lambda: restarted.append(True))
    settings = AppSettings(language="zh")
    window = SettingsWindow(settings)
    window._lang_combo.setCurrentIndex(1)
    assert settings.language == "en"
    assert restarted == []                    # 未触发重启
    set_language("zh")


def test_language_confirm_restart_now_calls_restart(app, monkeypatch):
    from sticky_tasks import settings_dialog
    from sticky_tasks.i18n import set_language

    _patch_message_boxes(monkeypatch, [True, True])  # 确认 + 立即重启
    restarted = []
    monkeypatch.setattr(settings_dialog, "restart_app", lambda: restarted.append(True))
    settings = AppSettings(language="zh")
    window = SettingsWindow(settings)
    window._lang_combo.setCurrentIndex(1)
    assert settings.language == "en"
    assert restarted == [True]                # 触发了重启
    set_language("zh")
