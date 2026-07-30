"""应用设置:用户自定义外观 + 自动对比色派生。

持久化到软件目录下的 .sticky_tasks/settings.json,与 tasks.json 同目录。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from PySide6.QtGui import QColor

from .json_io import atomic_write_text


MIN_BG_OPACITY = 3  # 约 1%（内部透明度范围为 0~255）


def _luminance(c: QColor) -> float:
    """相对亮度(0~255),用于判断背景明暗。"""
    return 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()


def _mix(base: QColor, overlay: QColor, alpha: int) -> QColor:
    """将 overlay 以 alpha(0~255)叠加到 base 上,返回混合色。"""
    a = alpha / 255.0
    return QColor(
        int(base.red() * (1 - a) + overlay.red() * a),
        int(base.green() * (1 - a) + overlay.green() * a),
        int(base.blue() * (1 - a) + overlay.blue() * a),
    )


@dataclass
class Theme:
    """从用户设置派生的完整配色方案。

    fixed_* 系列:软件自身标识(标题、已完成标签),不随用户自定义改变。
    其余颜色:根据背景明暗自动派生,始终保持与背景可区分。
    """

    # ---- 用户可自定义 ----
    bg_color: QColor = field(default_factory=lambda: QColor("#25262c"))
    text_color: QColor = field(default_factory=lambda: QColor("#e9e9ef"))
    font_family: str = "Segoe UI Variable"
    font_size: int = 13
    bg_opacity: int = 240  # 0~255

    # ---- 固定(软件标识,不随自定义变) ----
    fixed_title_color: QColor = field(default_factory=lambda: QColor("#9a9aa5"))
    fixed_footer_color: QColor = field(default_factory=lambda: QColor("#8a8a94"))

    # ---- 自动派生 ----
    sep_color: QColor = field(init=False)
    icon_color: QColor = field(init=False)
    icon_hover_color: QColor = field(init=False)
    highlight_color: QColor = field(init=False)
    scrollbar_color: QColor = field(init=False)
    scrollbar_hover_color: QColor = field(init=False)
    accent_color: QColor = field(init=False)
    edge_fade_color: QColor = field(init=False)
    is_dark: bool = field(init=False)

    def __post_init__(self):
        self._derive()

    def _derive(self):
        bg = self.bg_color
        lum = _luminance(bg)
        self.is_dark = lum < 128

        if self.is_dark:
            # 深色背景 → 用白色低透明度做线条/图标/高亮
            white = QColor(255, 255, 255)
            self.sep_color = QColor(255, 255, 255, 10)
            self.icon_color = _mix(bg, white, 110)
            self.icon_hover_color = _mix(bg, white, 200)
            self.highlight_color = QColor(255, 255, 255, 7)
            self.scrollbar_color = QColor(255, 255, 255, 36)
            self.scrollbar_hover_color = QColor(255, 255, 255, 58)
            self.accent_color = QColor("#5ea0ff")
            self.edge_fade_color = QColor(bg.red(), bg.green(), bg.blue())
        else:
            # 浅色背景 → 用黑色低透明度
            black = QColor(0, 0, 0)
            self.sep_color = QColor(0, 0, 0, 18)
            self.icon_color = _mix(bg, black, 100)
            self.icon_hover_color = _mix(bg, black, 180)
            self.highlight_color = QColor(0, 0, 0, 10)
            self.scrollbar_color = QColor(0, 0, 0, 40)
            self.scrollbar_hover_color = QColor(0, 0, 0, 70)
            self.accent_color = QColor("#2b7de9")
            self.edge_fade_color = QColor(bg.red(), bg.green(), bg.blue())


@dataclass
class AppSettings:
    """用户设置,持久化到 JSON。"""

    bg_color: str = "#25262c"
    text_color: str = "#e9e9ef"
    font_family: str = "Segoe UI Variable"
    font_size: int = 13
    bg_opacity: int = 240
    window_x: int | None = None
    window_y: int | None = None
    window_width: int | None = None
    window_height: int | None = None
    custom_colors: list[str] = field(default_factory=list)
    custom_preset: dict | None = None

    def to_theme(self) -> Theme:
        return Theme(
            bg_color=QColor(self.bg_color),
            text_color=QColor(self.text_color),
            font_family=self.font_family,
            font_size=self.font_size,
            bg_opacity=self.bg_opacity,
        )

    def save(self, path: Path):
        atomic_write_text(
            path,
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
        )

    @classmethod
    def load(cls, path: Path) -> "AppSettings":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        s = cls()
        for key in ("bg_color", "text_color", "font_family"):
            if key in data and isinstance(data[key], str):
                setattr(s, key, data[key])
        for key in ("font_size", "bg_opacity"):
            if key in data and type(data[key]) is int:
                setattr(s, key, data[key])
        for key in ("window_x", "window_y", "window_width", "window_height"):
            if key in data and type(data[key]) is int:
                setattr(s, key, data[key])
        if isinstance(data.get("custom_colors"), list):
            s.custom_colors = [
                color for color in data["custom_colors"]
                if isinstance(color, str) and QColor(color).isValid()
            ][:16]
        preset = data.get("custom_preset")
        required = {"bg", "text", "font", "size", "opacity"}
        if isinstance(preset, dict) and required.issubset(preset):
            if (
                isinstance(preset["bg"], str)
                and isinstance(preset["text"], str)
                and QColor(preset["bg"]).isValid()
                and QColor(preset["text"]).isValid()
                and isinstance(preset["font"], str)
                and type(preset["size"]) is int
                and type(preset["opacity"]) is int
            ):
                s.custom_preset = {
                    "name": "自定义",
                    "bg": QColor(preset["bg"]).name(),
                    "text": QColor(preset["text"]).name(),
                    "font": preset["font"],
                    "size": max(9, min(24, preset["size"])),
                    "opacity": max(MIN_BG_OPACITY, min(255, preset["opacity"])),
                }
        # 校验颜色合法性
        if not QColor(s.bg_color).isValid():
            s.bg_color = "#25262c"
        if not QColor(s.text_color).isValid():
            s.text_color = "#e9e9ef"
        s.font_size = max(9, min(24, s.font_size))
        s.bg_opacity = max(MIN_BG_OPACITY, min(255, s.bg_opacity))
        if s.window_width is not None:
            s.window_width = max(220, s.window_width)
        if s.window_height is not None:
            s.window_height = max(200, s.window_height)
        return s
