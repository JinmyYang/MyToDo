"""检查更新(updater)测试:版本比较与 GitHub API 流程。"""

import json

import pytest

from sticky_tasks import updater
from sticky_tasks.updater import (
    UpdateError, check_for_update, compare_versions, parse_version,
)


# ---- 版本解析与比较 ----
def test_parse_version_basic():
    assert parse_version("1.0.0") == (1, 0, 0)
    assert parse_version("v1.10.0") == (1, 10, 0)
    assert parse_version("V2.1") == (2, 1)
    assert parse_version("") == (0,)


def test_parse_version_tolerates_garbage_segments():
    assert parse_version("1.0.0-beta1") == (1, 0, 0)
    assert parse_version("abc") == (0,)


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("1.0.0", "1.0.0", 0),
        ("v1.0.1", "1.0.0", 1),
        ("1.0.0", "1.0.1", -1),
        ("1.10.0", "1.9.2", 1),     # 按数字比,不按字符串
        ("1.2", "1.2.0", 0),         # 长度不齐补 0
        ("2.0", "1.9.9", 1),
    ],
)
def test_compare_versions(a, b, expected):
    assert compare_versions(a, b) == expected


# ---- 检查更新流程 ----
def test_check_update_without_repo_config_raises():
    """仓库地址未填写时,应报网络未连接(发布前的占位行为)。"""
    monkeypatch_attrs = (updater.REPO_OWNER, updater.REPO_REPO)
    assert monkeypatch_attrs == ("", "")
    with pytest.raises(UpdateError, match="网络未连接"):
        check_for_update("1.0.0")


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def configured_repo(monkeypatch):
    monkeypatch.setattr(updater, "REPO_OWNER", "someone")
    monkeypatch.setattr(updater, "REPO_REPO", "mytodo")


def test_check_update_returns_new_release(monkeypatch, configured_repo):
    payload = {
        "tag_name": "v1.2.0",
        "body": "修复若干问题",
        "html_url": "https://example.com/releases/v1.2.0",
    }
    monkeypatch.setattr(
        updater.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeResponse(payload),
    )
    info = check_for_update("1.0.0")
    assert info is not None
    assert info["version"] == "1.2.0"
    assert info["notes"] == "修复若干问题"
    assert info["url"].endswith("v1.2.0")


def test_check_update_up_to_date_returns_none(monkeypatch, configured_repo):
    payload = {"tag_name": "v1.0.0", "body": "", "html_url": ""}
    monkeypatch.setattr(
        updater.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeResponse(payload),
    )
    assert check_for_update("1.0.0") is None


def test_check_update_network_error_raises(monkeypatch, configured_repo):
    def _raise(req, timeout=None):
        raise OSError("no network")

    monkeypatch.setattr(updater.urllib.request, "urlopen", _raise)
    with pytest.raises(UpdateError, match="网络未连接"):
        check_for_update("1.0.0")
