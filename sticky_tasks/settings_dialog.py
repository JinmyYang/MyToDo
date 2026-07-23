"""设置窗口:自定义背景色、字体色、字体、字号、透明度。

独立非模态窗口,不遮挡主界面;任何修改即时生效(实时预览)。
调用 Windows 原生颜色选择器(QColorDialog)和系统字体库(QFontDialog)。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QColorDialog, QFontDialog, QSlider, QSpinBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QCursor

from .app_settings import AppSettings

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
        font_row = QHBoxLayout()
        self._font_label = QLabel(self._settings.font_family)
        self._font_label.setStyleSheet("color: #e0e0e8; font-size: 12px;")
        font_row.addWidget(self._font_label, 1)
        font_btn = QPushButton("选择…")
        font_btn.setObjectName("actionBtn")
        font_btn.setCursor(QCursor(Qt.PointingHandCursor))
        font_btn.clicked.connect(self._pick_font)
        font_row.addWidget(font_btn)
        root.addLayout(font_row)

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
        self._op_slider.setRange(60, 255)
        self._op_slider.setValue(self._settings.bg_opacity)
        op_row.addWidget(self._op_slider, 1)
        self._op_label = QLabel(f"{int(self._settings.bg_opacity / 255 * 100)}%")
        self._op_label.setFixedWidth(36)
        self._op_slider.valueChanged.connect(self._on_opacity_changed)
        op_row.addWidget(self._op_label)
        root.addLayout(op_row)

        # ---- 恢复默认 ----
        root.addSpacing(8)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("actionBtn")
        reset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        root.addLayout(btn_row)

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
        self._settings.font_family = self._font_family
        self._settings.font_size = self._size_spin.value()
        self._settings.bg_opacity = self._op_slider.value()
        self.changed.emit()

    # ---- 槽 ----
    def _pick_bg_color(self):
        color = QColorDialog.getColor(
            QColor(self._settings.bg_color), self, "选择背景颜色")
        if color.isValid():
            self._bg_color = color
            self._paint_color_btn(self._bg_btn, color)
            self._emit_changed()

    def _pick_text_color(self):
        color = QColorDialog.getColor(
            QColor(self._settings.text_color), self, "选择字体颜色")
        if color.isValid():
            self._txt_color = color
            self._paint_color_btn(self._txt_btn, color)
            self._emit_changed()

    def _pick_font(self):
        initial = QFont(self._settings.font_family, self._settings.font_size)
        ok, font = QFontDialog.getFont(initial, self, "选择字体")
        if ok:
            self._font_family = font.family()
            if font.pointSize() > 0:
                self._size_spin.setValue(font.pointSize())
            self._font_label.setText(self._font_family)
            self._emit_changed()

    def _on_size_changed(self, val):
        self._emit_changed()

    def _on_opacity_changed(self, val):
        self._op_label.setText(f"{int(val / 255 * 100)}%")
        self._emit_changed()

    def _apply_preset(self, preset):
        """一键应用预设主题。"""
        self._bg_color = QColor(preset["bg"])
        self._txt_color = QColor(preset["text"])
        self._font_family = preset["font"]
        self._paint_color_btn(self._bg_btn, self._bg_color)
        self._paint_color_btn(self._txt_btn, self._txt_color)
        self._font_label.setText(self._font_family)
        self._size_spin.setValue(preset["size"])
        self._op_slider.setValue(preset["opacity"])
        self._emit_changed()

    def _reset(self):
        defaults = AppSettings()
        self._bg_color = QColor(defaults.bg_color)
        self._txt_color = QColor(defaults.text_color)
        self._font_family = defaults.font_family
        self._paint_color_btn(self._bg_btn, self._bg_color)
        self._paint_color_btn(self._txt_btn, self._txt_color)
        self._font_label.setText(self._font_family)
        self._size_spin.setValue(defaults.font_size)
        self._op_slider.setValue(defaults.bg_opacity)
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

    @property
    def _font_family(self):
        return self._settings.font_family

    @_font_family.setter
    def _font_family(self, f: str):
        self._settings.font_family = f
