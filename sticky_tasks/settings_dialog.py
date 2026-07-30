"""设置窗口:自定义背景色、字体色、字体、字号、透明度。

独立非模态窗口,不遮挡主界面;任何修改即时生效(实时预览)。
颜色使用系统选择器，字体直接在设置窗口的下拉框中选择。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QColorDialog, QComboBox, QSlider, QSpinBox, QCompleter,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFontDatabase

from .app_settings import AppSettings, MIN_BG_OPACITY

WINDOW_QSS = """
SettingsWindow {
    background: #1e1f24;
}
QLabel { color: #c8c8d2; font-size: 12px; }
QLabel#sectionTitle {
    color: #9a9aa5;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
}
QPushButton#colorBtn {
    border: 1px solid rgba(255,255,255,30);
    border-radius: 6px;
    min-width: 60px;
    min-height: 26px;
}
QPushButton#actionBtn {
    background: rgba(255,255,255,8);
    border: 1px solid rgba(255,255,255,16);
    border-radius: 7px;
    color: #d0d0d8;
    padding: 6px 16px;
    font-size: 12px;
}
QPushButton#actionBtn:hover {
    background: rgba(255,255,255,14);
}
QSlider::groove:horizontal {
    height: 4px;
    background: rgba(255,255,255,20);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    background: #5ea0ff;
    border-radius: 7px;
}
QSpinBox {
    background: rgba(255,255,255,8);
    border: 1px solid rgba(255,255,255,20);
    border-radius: 6px;
    color: #e0e0e8;
    padding: 3px 6px;
    font-size: 12px;
}
QSpinBox::up-button, QSpinBox::down-button { width: 16px; }
QComboBox {
    background: rgba(255,255,255,8);
    border: 1px solid rgba(255,255,255,20);
    border-radius: 6px;
    color: #e0e0e8;
    min-height: 28px;
    padding: 2px 8px;
}
QComboBox QAbstractItemView {
    background: #282930;
    border: 1px solid rgba(255,255,255,20);
    color: #e0e0e8;
    selection-background-color: #3d6599;
}
"""

# 预设主题:每套包含 bg_color, text_color, font_family, font_size, bg_opacity
PRESETS = [
    {"name": "深空",   "bg": "#25262c", "text": "#e9e9ef", "font": "Segoe UI Variable", "size": 13, "opacity": 240},
    {"name": "暖夜",   "bg": "#2c2420", "text": "#f0e6dc", "font": "Microsoft YaHei UI", "size": 13, "opacity": 235},
    {"name": "森林",   "bg": "#1e2a22", "text": "#e4f0e8", "font": "Microsoft YaHei UI", "size": 13, "opacity": 238},
    {"name": "海洋",   "bg": "#1a2432", "text": "#dce8f4", "font": "Segoe UI Variable", "size": 13, "opacity": 240},
    {"name": "薰衣草", "bg": "#282430", "text": "#ece6f4", "font": "Microsoft YaHei UI", "size": 13, "opacity": 236},
    {"name": "素白",   "bg": "#f2f2f4", "text": "#2c2c32", "font": "Microsoft YaHei UI", "size": 13, "opacity": 248},
]


class SettingsWindow(QWidget):
    """外观设置独立窗口(非模态,实时预览)。"""

    changed = Signal()  # 任何设置变动时发出,主窗口据此实时刷新
    history_requested = Signal()

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("外观设置")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setStyleSheet(WINDOW_QSS)
        self.setFixedWidth(300)

        self._settings = settings
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        # 标题
        title = QLabel("外观设置")
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        # ---- 预设主题 ----
        root.addWidget(self._row_label("预设"))
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        for p in PRESETS:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setToolTip(p["name"])
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {p['bg']};"
                f"  border: 2px solid rgba(255,255,255,40);"
                f"  border-radius: 14px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  border-color: #5ea0ff;"
                f"}}"
            )
            btn.clicked.connect(lambda checked=False, preset=p: self._apply_preset(preset))
            preset_row.addWidget(btn)
        self._custom_preset_btn = QPushButton("自")
        self._custom_preset_btn.setFixedSize(28, 28)
        self._custom_preset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._custom_preset_btn.clicked.connect(self._apply_custom_preset)
        preset_row.addWidget(self._custom_preset_btn)
        self._refresh_custom_preset_button()
        preset_row.addStretch()
        root.addLayout(preset_row)

        # ---- 背景颜色 ----
        root.addWidget(self._row_label("背景颜色"))
        bg_row = QHBoxLayout()
        self._bg_btn = self._make_color_btn(QColor(self._settings.bg_color))
        self._bg_btn.clicked.connect(self._pick_bg_color)
        bg_row.addWidget(self._bg_btn)
        bg_row.addStretch()
        root.addLayout(bg_row)

        # ---- 字体颜色 ----
        root.addWidget(self._row_label("字体颜色"))
        txt_row = QHBoxLayout()
        self._txt_btn = self._make_color_btn(QColor(self._settings.text_color))
        self._txt_btn.clicked.connect(self._pick_text_color)
        txt_row.addWidget(self._txt_btn)
        txt_row.addStretch()
        root.addLayout(txt_row)

        # ---- 字体 ----
        root.addWidget(self._row_label("字体"))
        self._font_families = sorted(QFontDatabase.families(), key=str.casefold)
        self._font_combo = QComboBox()
        self._font_combo.setEditable(True)
        self._font_combo.setInsertPolicy(QComboBox.NoInsert)
        self._font_combo.addItems(self._font_families)
        self._font_combo.setCurrentText(self._settings.font_family)
        self._font_combo.lineEdit().setPlaceholderText("搜索字体")
        completer = QCompleter(self._font_families, self._font_combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated[str].connect(self._on_font_activated)
        self._font_combo.setCompleter(completer)
        self._font_combo.textActivated.connect(self._on_font_activated)
        self._font_combo.lineEdit().editingFinished.connect(self._commit_font_text)
        root.addWidget(self._font_combo)

        # ---- 字号 ----
        root.addWidget(self._row_label("字号"))
        size_row = QHBoxLayout()
        self._size_spin = QSpinBox()
        self._size_spin.setRange(9, 24)
        self._size_spin.setValue(self._settings.font_size)
        self._size_spin.setSuffix(" px")
        self._size_spin.valueChanged.connect(self._on_size_changed)
        size_row.addWidget(self._size_spin)
        size_row.addStretch()
        root.addLayout(size_row)

        # ---- 背景透明度 ----
        root.addWidget(self._row_label("背景透明度"))
        op_row = QHBoxLayout()
        self._op_slider = QSlider(Qt.Horizontal)
        self._op_slider.setRange(MIN_BG_OPACITY, 255)
        self._op_slider.setValue(self._settings.bg_opacity)
        op_row.addWidget(self._op_slider, 1)
        self._op_label = QLabel(f"{int(self._settings.bg_opacity / 255 * 100)}%")
        self._op_label.setFixedWidth(36)
        self._op_slider.valueChanged.connect(self._on_opacity_changed)
        op_row.addWidget(self._op_label)
        root.addLayout(op_row)

        # ---- 操作 ----
        root.addSpacing(8)
        btn_row = QHBoxLayout()
        history_btn = QPushButton("查看历史任务")
        history_btn.setObjectName("actionBtn")
        history_btn.setCursor(QCursor(Qt.PointingHandCursor))
        history_btn.clicked.connect(self.history_requested)
        btn_row.addWidget(history_btn)
        save_preset_btn = QPushButton("保存为自定义预设")
        save_preset_btn.setObjectName("actionBtn")
        save_preset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        save_preset_btn.clicked.connect(self._save_custom_preset)
        btn_row.addWidget(save_preset_btn)
        root.addLayout(btn_row)

        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("actionBtn")
        reset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        reset_btn.clicked.connect(self._reset)
        reset_row.addWidget(reset_btn)
        root.addLayout(reset_row)

    # ---- 工具 ----
    def _row_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #8a8a94; font-size: 12px;")
        lbl.setFixedHeight(18)
        return lbl

    def _make_color_btn(self, color: QColor) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("colorBtn")
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._paint_color_btn(btn, color)
        return btn

    def _paint_color_btn(self, btn: QPushButton, color: QColor):
        btn.setStyleSheet(
            f"QPushButton#colorBtn {{"
            f"  background: {color.name()};"
            f"  border: 1px solid rgba(255,255,255,30);"
            f"  border-radius: 6px;"
            f"  min-width: 60px; min-height: 26px;"
            f"}}"
        )

    def _emit_changed(self):
        """将当前 UI 状态写回 settings 并通知主窗口刷新。"""
        self._settings.bg_color = self._bg_color.name()
        self._settings.text_color = self._txt_color.name()
        if self._font_combo.currentText() in self._font_families:
            self._settings.font_family = self._font_combo.currentText()
        self._settings.font_size = self._size_spin.value()
        self._settings.bg_opacity = self._op_slider.value()
        self.changed.emit()

    # ---- 槽 ----
    def _pick_bg_color(self):
        color = self._show_color_dialog(
            QColor(self._settings.bg_color), "选择背景颜色",
        )
        if color.isValid():
            self._bg_color = color
            self._paint_color_btn(self._bg_btn, color)
            self._emit_changed()
        else:
            self.changed.emit()

    def _pick_text_color(self):
        color = self._show_color_dialog(
            QColor(self._settings.text_color), "选择字体颜色",
        )
        if color.isValid():
            self._txt_color = color
            self._paint_color_btn(self._txt_btn, color)
            self._emit_changed()
        else:
            self.changed.emit()

    def _on_font_activated(self, family):
        if family in self._font_families:
            self._settings.font_family = family
            self.changed.emit()

    def _commit_font_text(self):
        family = self._font_combo.currentText().strip()
        match = next(
            (name for name in self._font_families if name.casefold() == family.casefold()),
            None,
        )
        self._font_combo.setCurrentText(match or self._settings.font_family)
        if match:
            self._settings.font_family = match
            self.changed.emit()

    def _on_size_changed(self, val):
        self._emit_changed()

    def _on_opacity_changed(self, val):
        self._op_label.setText(f"{int(val / 255 * 100)}%")
        self._emit_changed()

    def _apply_preset(self, preset):
        """一键应用预设主题。"""
        self._bg_color = QColor(preset["bg"])
        self._txt_color = QColor(preset["text"])
        self._paint_color_btn(self._bg_btn, self._bg_color)
        self._paint_color_btn(self._txt_btn, self._txt_color)
        self._font_combo.blockSignals(True)
        self._size_spin.blockSignals(True)
        self._op_slider.blockSignals(True)
        self._font_combo.setCurrentText(preset["font"])
        self._size_spin.setValue(preset["size"])
        self._op_slider.setValue(preset["opacity"])
        self._font_combo.blockSignals(False)
        self._size_spin.blockSignals(False)
        self._op_slider.blockSignals(False)
        self._op_label.setText(f"{int(preset['opacity'] / 255 * 100)}%")
        self._emit_changed()

    def _save_custom_preset(self):
        self._settings.custom_preset = {
            "name": "自定义",
            "bg": self._settings.bg_color,
            "text": self._settings.text_color,
            "font": self._settings.font_family,
            "size": self._settings.font_size,
            "opacity": self._settings.bg_opacity,
        }
        self._refresh_custom_preset_button()
        self.changed.emit()

    def _apply_custom_preset(self):
        if self._settings.custom_preset is not None:
            self._apply_preset(self._settings.custom_preset)

    def _refresh_custom_preset_button(self):
        preset = self._settings.custom_preset
        color = preset["bg"] if preset is not None else "#34353d"
        self._custom_preset_btn.setToolTip(
            "自定义预设" if preset is not None else "尚未保存自定义预设"
        )
        self._custom_preset_btn.setEnabled(preset is not None)
        self._custom_preset_btn.setStyleSheet(
            "QPushButton {"
            f"background: {color}; color: #ffffff;"
            "border: 2px solid rgba(255,255,255,40); border-radius: 14px;"
            "font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { border-color: #5ea0ff; }"
        )

    def _restore_custom_colors(self):
        for index, color in enumerate(self._settings.custom_colors):
            if index < QColorDialog.customCount():
                QColorDialog.setCustomColor(index, QColor(color))

    def _show_color_dialog(self, initial, title):
        self._restore_custom_colors()
        dialog = QColorDialog(initial, self)
        dialog.setWindowTitle(title)
        dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        accepted = dialog.exec()
        self._remember_custom_colors()
        return dialog.selectedColor() if accepted else QColor()

    def _remember_custom_colors(self):
        self._settings.custom_colors = [
            QColorDialog.customColor(index).name()
            for index in range(QColorDialog.customCount())
            if QColorDialog.customColor(index).isValid()
        ]

    def _reset(self):
        defaults = AppSettings()
        self._bg_color = QColor(defaults.bg_color)
        self._txt_color = QColor(defaults.text_color)
        self._paint_color_btn(self._bg_btn, self._bg_color)
        self._paint_color_btn(self._txt_btn, self._txt_color)
        self._font_combo.blockSignals(True)
        self._size_spin.blockSignals(True)
        self._op_slider.blockSignals(True)
        self._font_combo.setCurrentText(defaults.font_family)
        self._size_spin.setValue(defaults.font_size)
        self._op_slider.setValue(defaults.bg_opacity)
        self._font_combo.blockSignals(False)
        self._size_spin.blockSignals(False)
        self._op_slider.blockSignals(False)
        self._op_label.setText(f"{int(defaults.bg_opacity / 255 * 100)}%")
        self._emit_changed()

    # ---- 初始化内部状态(从 settings 读取) ----
    @property
    def _bg_color(self):
        return QColor(self._settings.bg_color)

    @_bg_color.setter
    def _bg_color(self, c: QColor):
        self._settings.bg_color = c.name()

    @property
    def _txt_color(self):
        return QColor(self._settings.text_color)

    @_txt_color.setter
    def _txt_color(self, c: QColor):
        self._settings.text_color = c.name()
