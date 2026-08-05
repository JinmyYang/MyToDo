"""多语言支持:中文 / English。

极简方案:查表翻译,不走 Qt Linguist。界面文案在启动时按
当前语言构建,改语言后提示重启生效。
"""

LANG_ZH = "zh"
LANG_EN = "en"
SUPPORTED = (LANG_ZH, LANG_EN)

_current = LANG_ZH


def set_language(lang: str):
    """设置当前语言;不支持的值回退到中文。"""
    global _current
    _current = lang if lang in SUPPORTED else LANG_ZH


def get_language() -> str:
    return _current


def t(key: str, **fmt) -> str:
    """按 key 取当前语言文案,可用关键字参数填充占位符。

    缺 key 时直接返回 key 本身,保证永不崩。
    """
    table = _TRANSLATIONS.get(_current) or _TRANSLATIONS[LANG_ZH]
    text = table.get(key)
    if text is None:
        text = (_TRANSLATIONS[LANG_ZH].get(key) or key)
    if fmt:
        try:
            text = text.format(**fmt)
        except (KeyError, IndexError):
            pass
    return text


# 注:"已完成  {n}" 的双空格是排版设计,两种语言均保留。
_TRANSLATIONS = {
    LANG_ZH: {
        # ---- 通用 ----
        "common.confirm": "确认",
        "common.cancel": "取消",
        "common.restart_now": "立即重启",
        "common.later": "稍后",
        # ---- 主窗口 ----
        "app.running": "{name} 已在运行,请勿重复打开。",
        "app.crash": "程序遇到了意外错误。\n错误详情已记录到 .sticky_tasks/crash.log，反馈问题时请附带该文件。",
        "app.data_warning": "本地数据提示",
        "main.new_tooltip": "新建任务 (Ctrl+N)",
        "main.empty_hint": "暂无任务 —— 点击上方 + 或按 Ctrl+N 新建",
        "main.completed_count": "已完成  {n}",
        "main.settings_tooltip": "设置",
        "main.lock_tooltip": "{action} (Ctrl+L)",
        "main.lock_action_on": "锁定窗口",
        "main.lock_action_off": "解锁窗口",
        "main.menu_quit": "退出",
        "main.menu_unlock": "解锁",
        # ---- 任务项 ----
        "task.mark_done": "标记为完成",
        "task.edit": "编辑",
        "task.delete": "删除",
        "task.edit_placeholder": "输入任务…",
        # ---- 设置窗口 ----
        "settings.title": "设置",
        "settings.presets": "预设",
        "settings.bg_color": "背景颜色",
        "settings.text_color": "字体颜色",
        "settings.font": "字体",
        "settings.font_search": "搜索字体",
        "settings.font_size": "字号",
        "settings.bg_opacity": "背景透明度",
        "settings.language": "界面语言",
        "settings.history_btn": "查看历史任务",
        "settings.save_preset_btn": "保存为自定义预设",
        "settings.check_update_btn": "检查更新",
        "settings.custom_preset_tip": "自定义预设",
        "settings.no_custom_preset": "尚未保存自定义预设",
        "settings.pick_bg": "选择背景颜色",
        "settings.pick_text": "选择字体颜色",
        "settings.lang_confirm": "界面语言将切换为{lang}，确定吗？",
        "settings.lang_restart": "语言已切换，将在重启后生效。",
        "settings.up_to_date": "当前已是最新版本 (v{version})。",
        "settings.new_version": "发现新版本 v{latest}（当前 v{current}）",
        "settings.open_download": "前往下载",
        "settings.close": "关闭",
    },
    LANG_EN: {
        # ---- Common ----
        "common.confirm": "Confirm",
        "common.cancel": "Cancel",
        "common.restart_now": "Restart now",
        "common.later": "Later",
        # ---- Main window ----
        "app.running": "{name} is already running.",
        "app.crash": "An unexpected error occurred.\nDetails were saved to .sticky_tasks/crash.log — please attach it when reporting.",
        "app.data_warning": "Local Data Notice",
        "main.new_tooltip": "New task (Ctrl+N)",
        "main.empty_hint": "No tasks — click + above or press Ctrl+N",
        "main.completed_count": "Completed  {n}",
        "main.settings_tooltip": "Settings",
        "main.lock_tooltip": "{action} (Ctrl+L)",
        "main.lock_action_on": "Lock window",
        "main.lock_action_off": "Unlock window",
        "main.menu_quit": "Quit",
        "main.menu_unlock": "Unlock",
        # ---- Task item ----
        "task.mark_done": "Mark as done",
        "task.edit": "Edit",
        "task.delete": "Delete",
        "task.edit_placeholder": "Type a task…",
        # ---- Settings window ----
        "settings.title": "Settings",
        "settings.presets": "Presets",
        "settings.bg_color": "Background color",
        "settings.text_color": "Text color",
        "settings.font": "Font",
        "settings.font_search": "Search fonts",
        "settings.font_size": "Font size",
        "settings.bg_opacity": "Background opacity",
        "settings.language": "Interface language",
        "settings.history_btn": "View history",
        "settings.save_preset_btn": "Save as preset",
        "settings.check_update_btn": "Check for updates",
        "settings.custom_preset_tip": "Custom preset",
        "settings.no_custom_preset": "No custom preset saved",
        "settings.pick_bg": "Pick background color",
        "settings.pick_text": "Pick text color",
        "settings.lang_confirm": "Switch interface language to {lang}?",
        "settings.lang_restart": "Language switched. It will take effect after a restart.",
        "settings.up_to_date": "You're up to date (v{version}).",
        "settings.new_version": "New version v{latest} available (current v{current})",
        "settings.open_download": "Download",
        "settings.close": "Close",
    },
}
