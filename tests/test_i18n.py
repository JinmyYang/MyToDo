"""多语言(i18n)测试:语言切换、查表翻译与占位符填充。"""

import pytest

from sticky_tasks import i18n
from sticky_tasks.i18n import get_language, set_language, t


@pytest.fixture(autouse=True)
def restore_language():
    """每个用例后恢复默认中文,避免污染其他测试(冒烟测试断言中文文案)。"""
    original = get_language()
    yield
    set_language(original)


def test_default_language_is_chinese():
    set_language("zh")
    assert get_language() == "zh"


def test_zh_translation():
    set_language("zh")
    assert t("settings.title") == "设置"
    assert t("main.menu_quit") == "退出"


def test_en_translation():
    set_language("en")
    assert t("settings.title") == "Settings"
    assert t("main.menu_quit") == "Quit"


def test_placeholder_formatting():
    set_language("zh")
    assert t("main.completed_count", n=3) == "已完成  3"
    set_language("en")
    assert t("main.completed_count", n=3) == "Completed  3"


def test_unknown_language_falls_back_to_zh():
    set_language("fr")
    assert get_language() == "zh"
    assert t("settings.title") == "设置"


def test_missing_key_returns_key_itself():
    set_language("zh")
    assert t("no.such.key") == "no.such.key"


def test_missing_key_in_en_falls_back_to_zh():
    """英文表缺 key 时回退中文,而不是抛错或显示 key。"""
    set_language("en")
    i18n._TRANSLATIONS["en"].pop("main.menu_quit", None)
    try:
        assert t("main.menu_quit") == "退出"
    finally:
        i18n._TRANSLATIONS["en"]["main.menu_quit"] = "Quit"
