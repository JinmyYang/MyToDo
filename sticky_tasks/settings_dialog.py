"""设置对话框:自定义背景色、字体色、字体、字号、透明度。

调用 Windows 原生颜色选择器(QColorDialog)和系统字体库(QFontDialog)。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QColorDialog, QFontDialog, QSlider, QSpinBox, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QCursor

from .app_settings import AppSettings

DIALOG_QSS = """
QDialog {
    background: #1e1f24;
    border-radius: 10px;
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
QPushButton#primaryBtn {
    background: rgba(94,160,255,140);
    border: none;
    border-radius: 7px;
    color: #ffffff;
    padding: 6px 20px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#primaryBtn:hover {
    background: rgba(94,160,255,180);
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


class SettingsDialog(QDialog):
    """外观设置对话框。"""

    applied = Signal()  # 用户点"应用"后发出

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("外观设置")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(DIALOG_QSS)
        self.setFixedWidth(320)

        self._settings = settings
        # 工作副本,点应用才写回
        self._bg_color = QColor(settings.bg_color)
        self._text_color = QColor(settings.text_color)
        self._font_family = settings.font_family
        self._font_size = settings.font_size
        self._bg_opacity = settings.bg_opacity

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        # 标题
        title = QLabel("外观设置")
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        # ---- 背景颜色 ----
        root.addWidget(self._row_label("背景颜色"))
        bg_row = QHBoxLayout()
        self._bg_btn = self._make_color_btn(self._bg_color)
        self._bg_btn.clicked.connect(self._pick_bg_color)
        bg_row.addWidget(self._bg_btn)
        bg_row.addStretch()
        root.addLayout(bg_row)

        # ---- 字体颜色 ----
        root.addWidget(self._row_label("字体颜色"))
        txt_row = QHBoxLayout()
        self._txt_btn = self._make_color_btn(self._text_color)
        self._txt_btn.clicked.connect(self._pick_text_color)
        txt_row.addWidget(self._txt_btn)
        txt_row.addStretch()
        root.addLayout(txt_row)

        # ---- 字体 ----
        root.addWidget(self._row_label("字体"))
        font_row = QHBoxLayout()
        self._font_label = QLabel(self._font_family)
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
        self._size_spin.setValue(self._font_size)
        self._size_spin.setSuffix(" px")
        size_row.addWidget(self._size_spin)
        size_row.addStretch()
        root.addLayout(size_row)

        # ---- 背景透明度 ----
        root.addWidget(self._row_label("背景透明度"))
        op_row = QHBoxLayout()
        self._op_slider = QSlider(Qt.Horizontal)
        self._op_slider.setRange(60, 255)
        self._op_slider.setValue(self._bg_opacity)
        op_row.addWidget(self._op_slider, 1)
        self._op_label = QLabel(f"{int(self._bg_opacity / 255 * 100)}%")
        self._op_label.setFixedWidth(36)
        self._op_slider.valueChanged.connect(self._on_opacity_changed)
        op_row.addWidget(self._op_label)
        root.addLayout(op_row)

        # ---- 按钮行 ----
        root.addSpacing(6)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = QPushButton("恢复默认")
        reset_btn.setObjectName("actionBtn")
        reset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        apply_btn = QPushButton("应用")
        apply_btn.setObjectName("primaryBtn")
        apply_btn.setCursor(QCursor(Qt.PointingHandCursor))
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)
        root.addLayout(btn_row)

    # ---- 工具 ----
    def _row_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #8a8a94; font-size: 11px; margin-bottom: -6px;")
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

    # ---- 槽 ----
    def _pick_bg_color(self):
        color = QColorDialog.getColor(self._bg_color, self, "选择背景颜色")
        if color.isValid():
            self._bg_color = color
            self._paint_color_btn(self._bg_btn, color)

    def _pick_text_color(self):
        color = QColorDialog.getColor(self._text_color, self, "选择字体颜色")
        if color.isValid():
            self._text_color = color
            self._paint_color_btn(self._txt_btn, color)

    def _pick_font(self):
        initial = QFont(self._font_family, self._font_size)
        ok, font = QFontDialog.getFont(initial, self, "选择字体")
        if ok:
            self._font_family = font.family()
            self._font_size = font.pointSize() if font.pointSize() > 0 else self._font_size
            self._font_label.setText(self._font_family)
            self._size_spin.setValue(self._font_size)

    def _on_opacity_changed(self, val):
        self._op_label.setText(f"{int(val / 255 * 100)}%")

    def _reset(self):
        defaults = AppSettings()
        self._bg_color = QColor(defaults.bg_color)
        self._text_color = QColor(defaults.text_color)
        self._font_family = defaults.font_family
        self._font_size = defaults.font_size
        self._bg_opacity = defaults.bg_opacity
        self._paint_color_btn(self._bg_btn, self._bg_color)
        self._paint_color_btn(self._txt_btn, self._text_color)
        self._font_label.setText(self._font_family)
        self._size_spin.setValue(self._font_size)
        self._op_slider.setValue(self._bg_opacity)

    def _apply(self):
        self._settings.bg_color = self._bg_color.name()
        self._settings.text_color = self._text_color.name()
        self._settings.font_family = self._font_family
        self._settings.font_size = self._size_spin.value()
        self._settings.bg_opacity = self._op_slider.value()
        self.applied.emit()
        self.accept()
