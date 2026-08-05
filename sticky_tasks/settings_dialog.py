"""设置窗口:外观、语言、数据管理与关于。

独立非模态窗口,不遮挡主界面;任何修改即时生效(实时预览)。
颜色使用系统选择器，字体直接在设置窗口的下拉框中选择。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
    QColorDialog, QComboBox, QSlider, QSpinBox, QCompleter,
    QAbstractSpinBox, QLineEdit, QMessageBox,
)
# 注:QCompleter 仅用其枚举常量配置 combo 内置补全器,不另建实例
from PySide6.QtCore import Qt, Signal, QEvent, QUrl
from PySide6.QtGui import QColor, QCursor, QFontDatabase, QDesktopServices

from . import APP_NAME, APP_VERSION
from . import updater
from .app_settings import AppSettings, MIN_BG_OPACITY
from .i18n import LANG_EN, LANG_ZH, set_language, t
from .restart import restart_app

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


class _NoWheelComboBox(QComboBox):
    """禁用滚轮换字体:悬停/聚焦时滚轮一动就换字体,太容易误触。"""

    def wheelEvent(self, event):
        event.ignore()  # 交给父级(页面滚动等)


class _NoWheelSpinBox(QSpinBox):
    """禁用滚轮改字号,理由同上。"""

    def wheelEvent(self, event):
        event.ignore()


class _NoWheelSlider(QSlider):
    """禁用滚轮调透明度:悬停时滚轮一动就改值,太容易误触。"""

    def wheelEvent(self, event):
        event.ignore()


class SettingsWindow(QWidget):
    """外观设置独立窗口(非模态,实时预览)。"""

    changed = Signal()  # 任何设置变动时发出,主窗口据此实时刷新
    history_requested = Signal()

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        # 窗口文案跟随 settings 里的语言(启动时 main.py 已全局同步,
        # 这里再确保窗口自身始终与自己的 settings 一致)
        set_language(settings.language)
        self.setWindowTitle(t("settings.title"))
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.setStyleSheet(WINDOW_QSS)
        self.setFixedWidth(300)

        self._settings = settings
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(10)

        # ---- 预设主题 ----
        root.addWidget(self._row_label(t("settings.presets")))
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

        # ---- 背景颜色 / 字体颜色(并列两列) ----
        color_row = QHBoxLayout()
        color_row.setSpacing(14)
        bg_col = QVBoxLayout()
        bg_col.setSpacing(6)
        bg_col.addWidget(self._row_label(t("settings.bg_color")))
        self._bg_btn = self._make_color_btn(QColor(self._settings.bg_color))
        self._bg_btn.clicked.connect(self._pick_bg_color)
        bg_col.addWidget(self._bg_btn)
        color_row.addLayout(bg_col, 1)
        txt_col = QVBoxLayout()
        txt_col.setSpacing(6)
        txt_col.addWidget(self._row_label(t("settings.text_color")))
        self._txt_btn = self._make_color_btn(QColor(self._settings.text_color))
        self._txt_btn.clicked.connect(self._pick_text_color)
        txt_col.addWidget(self._txt_btn)
        color_row.addLayout(txt_col, 1)
        root.addLayout(color_row)

        # ---- 字体 ----
        root.addWidget(self._row_label(t("settings.font")))
        self._font_families = sorted(QFontDatabase.families(), key=str.casefold)
        self._font_combo = _NoWheelComboBox()
        self._font_combo.setEditable(True)
        self._font_combo.setInsertPolicy(QComboBox.NoInsert)
        self._font_combo.addItems(self._font_families)
        self._font_combo.setCurrentText(self._settings.font_family)
        self._font_combo.lineEdit().setPlaceholderText(t("settings.font_search"))
        # 直接配置内置补全器(可编辑 combo 自带),不再另建 QCompleter:
        # 少一份 500+ 字体项的补全模型,打开设置窗口更快。
        completer = self._font_combo.completer()
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self._font_combo.textActivated.connect(self._on_font_activated)
        self._font_combo.lineEdit().editingFinished.connect(self._commit_font_text)
        root.addWidget(self._font_combo)

        # ---- 字号 ----
        root.addWidget(self._row_label(t("settings.font_size")))
        size_row = QHBoxLayout()
        self._size_spin = _NoWheelSpinBox()
        self._size_spin.setRange(9, 24)
        self._size_spin.setValue(self._settings.font_size)
        self._size_spin.setSuffix(" px")
        self._size_spin.valueChanged.connect(self._on_size_changed)
        size_row.addWidget(self._size_spin)
        size_row.addStretch()
        root.addLayout(size_row)

        # ---- 背景透明度 ----
        root.addWidget(self._row_label(t("settings.bg_opacity")))
        op_row = QHBoxLayout()
        self._op_slider = _NoWheelSlider(Qt.Horizontal)
        self._op_slider.setRange(MIN_BG_OPACITY, 255)
        self._op_slider.setValue(self._settings.bg_opacity)
        op_row.addWidget(self._op_slider, 1)
        self._op_label = QLabel(f"{int(self._settings.bg_opacity / 255 * 100)}%")
        self._op_label.setFixedWidth(36)
        self._op_slider.valueChanged.connect(self._on_opacity_changed)
        op_row.addWidget(self._op_label)
        root.addLayout(op_row)

        # ---- 保存自定义预设(外观部分收尾,右对齐) ----
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_preset_btn = QPushButton(t("settings.save_preset_btn"))
        save_preset_btn.setObjectName("actionBtn")
        save_preset_btn.setCursor(QCursor(Qt.PointingHandCursor))
        save_preset_btn.clicked.connect(self._save_custom_preset)
        save_row.addWidget(save_preset_btn)
        root.addLayout(save_row)

        root.addWidget(self._separator())

        # ---- 语言 ----
        lang_row = QHBoxLayout()
        lang_row.addWidget(self._row_label(t("settings.language")))
        self._lang_combo = _NoWheelComboBox()
        self._lang_combo.addItem("中文", LANG_ZH)
        self._lang_combo.addItem("English", LANG_EN)
        self._lang_combo.setCurrentIndex(
            1 if self._settings.language == LANG_EN else 0,
        )
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_row.addWidget(self._lang_combo)
        lang_row.addStretch()
        root.addLayout(lang_row)

        root.addWidget(self._separator())

        # ---- 查看历史任务(右对齐) ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        history_btn = QPushButton(t("settings.history_btn"))
        history_btn.setObjectName("actionBtn")
        history_btn.setCursor(QCursor(Qt.PointingHandCursor))
        history_btn.clicked.connect(self.history_requested)
        btn_row.addWidget(history_btn)
        root.addLayout(btn_row)

        root.addWidget(self._separator())

        # ---- 版本与检查更新 ----
        about_row = QHBoxLayout()
        version_label = QLabel(f"{APP_NAME}  v{APP_VERSION}")
        version_label.setStyleSheet("color: #6f6f7a; font-size: 11px;")
        about_row.addWidget(version_label)
        about_row.addStretch()
        update_btn = QPushButton(t("settings.check_update_btn"))
        update_btn.setObjectName("actionBtn")
        update_btn.setCursor(QCursor(Qt.PointingHandCursor))
        update_btn.clicked.connect(self._check_update)
        about_row.addWidget(update_btn)
        root.addLayout(about_row)

        self._install_click_blank_clear_focus()

    # ---- 点击空白处清除焦点(消掉字号框的蓝色选中高亮)----
    _FOCUS_KEEPERS = (QComboBox, QAbstractSpinBox, QLineEdit, QSlider)

    def _install_click_blank_clear_focus(self):
        self.installEventFilter(self)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.MouseButtonPress
            and not isinstance(obj, self._FOCUS_KEEPERS)
        ):
            focused = self.focusWidget()
            if focused is not None:
                focused.clearFocus()
        return super().eventFilter(obj, event)

    # ---- 语言(两段式确认:确认切换 → 提示重启) ----
    def _on_language_changed(self, index):
        lang = self._lang_combo.itemData(index)
        if lang == self._settings.language:
            return
        old_index = 1 if self._settings.language == LANG_EN else 0
        lang_name = "English" if lang == LANG_EN else "中文"

        # 第一段:用旧语言确认,用户看得懂才能做决定
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(t("settings.lang_confirm", lang=lang_name))
        confirm_btn = box.addButton(t("common.confirm"), QMessageBox.AcceptRole)
        box.addButton(t("common.cancel"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is not confirm_btn:
            # 取消:下拉框回退,不保存任何改动
            self._lang_combo.blockSignals(True)
            self._lang_combo.setCurrentIndex(old_index)
            self._lang_combo.blockSignals(False)
            return

        self._settings.language = lang
        set_language(lang)
        self.changed.emit()

        # 第二段:用新语言提示,顺带预览新语言效果
        box2 = QMessageBox(self)
        box2.setWindowTitle(APP_NAME)
        box2.setText(t("settings.lang_restart"))
        restart_btn = box2.addButton(t("common.restart_now"), QMessageBox.AcceptRole)
        box2.addButton(t("common.later"), QMessageBox.RejectRole)
        box2.exec()
        if box2.clickedButton() is restart_btn:
            restart_app()

    # ---- 检查更新 ----
    def _check_update(self):
        try:
            info = updater.check_for_update(APP_VERSION)
        except updater.UpdateError as exc:
            QMessageBox.warning(self, APP_NAME, str(exc))
            return
        if info is None:
            QMessageBox.information(
                self, APP_NAME, t("settings.up_to_date", version=APP_VERSION),
            )
            return
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(
            t(
                "settings.new_version",
                latest=info["version"], current=APP_VERSION,
            ),
        )
        if info["notes"]:
            box.setInformativeText(info["notes"][:500])
        open_btn = box.addButton(t("settings.open_download"), QMessageBox.AcceptRole)
        box.addButton(t("settings.close"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn and info["url"]:
            QDesktopServices.openUrl(QUrl(info["url"]))

    # ---- 工具 ----
    def _separator(self):
        """分区之间的细横线(不用文字标题,版面更干净)。"""
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255, 255, 255, 18);")
        return sep

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
            QColor(self._settings.bg_color), t("settings.pick_bg"),
        )
        if color.isValid():
            self._bg_color = color
            self._paint_color_btn(self._bg_btn, color)
            self._emit_changed()
        else:
            self.changed.emit()

    def _pick_text_color(self):
        color = self._show_color_dialog(
            QColor(self._settings.text_color), t("settings.pick_text"),
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
            t("settings.custom_preset_tip") if preset is not None
            else t("settings.no_custom_preset"),
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
