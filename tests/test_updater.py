"""检查更新(updater)测试:版本比较、GitHub API 流程与一键更新。"""

import json

import pytest

from sticky_tasks import updater
from sticky_tasks.updater import (
    UpdateCancelled, UpdateError, build_update_script, check_for_update,
    compare_versions, download_asset, parse_version, prepare_and_launch_update,
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
def test_check_update_without_repo_config_raises(monkeypatch):
    """仓库地址未配置时,应报网络未连接。"""
    monkeypatch.setattr(updater, "REPO_OWNER", "")
    monkeypatch.setattr(updater, "REPO_REPO", "")
    with pytest.raises(UpdateError, match="网络未连接"):
        check_for_update("1.0.0")


def test_repo_config_points_to_release_repo():
    """发布版必须已配置真实仓库,否则用户无法检查更新。"""
    assert updater.REPO_OWNER == "JinmyYang"
    assert updater.REPO_REPO == "MyToDo"


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
    assert info["asset_url"] == ""  # 无附件时为空串,UI 退回前往下载


def test_check_update_picks_setup_exe_url(monkeypatch, configured_repo):
    """多附件时优先选 -Setup- 的 exe 直链。"""
    payload = {
        "tag_name": "v1.2.0",
        "body": "",
        "html_url": "",
        "assets": [
            {"name": "checksums.exe", "browser_download_url": "https://dl/c.exe"},
            {
                "name": "MyToDo-Setup-v1.2.0.exe",
                "browser_download_url": "https://dl/setup.exe",
            },
        ],
    }
    monkeypatch.setattr(
        updater.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeResponse(payload),
    )
    info = check_for_update("1.0.0")
    assert info["asset_url"] == "https://dl/setup.exe"


def test_check_update_falls_back_to_any_exe(monkeypatch, configured_repo):
    payload = {
        "tag_name": "v1.2.0",
        "body": "",
        "html_url": "",
        "assets": [
            {"name": "MyToDo-installer.exe", "browser_download_url": "https://dl/i.exe"},
        ],
    }
    monkeypatch.setattr(
        updater.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeResponse(payload),
    )
    info = check_for_update("1.0.0")
    assert info["asset_url"] == "https://dl/i.exe"


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


# ---- 一键更新:下载 ----
class _FakeAssetResponse:
    """模拟可分块读取的下载响应。"""

    def __init__(self, chunks, content_length=None):
        self._chunks = list(chunks)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def read(self, size=-1):
        return self._chunks.pop(0) if self._chunks else b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_asset_writes_file_and_reports_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(
        updater.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeAssetResponse(
            [b"a" * 10, b"b" * 5], content_length=15,
        ),
    )
    dest = tmp_path / "setup.exe"
    seen = []
    download_asset(
        "https://example.com/setup.exe", dest,
        progress_cb=lambda d, t: seen.append((d, t)),
    )
    assert dest.read_bytes() == b"a" * 10 + b"b" * 5
    assert seen == [(10, 15), (15, 15)]


def test_download_asset_cancel_raises_and_cleans_up(monkeypatch, tmp_path):
    monkeypatch.setattr(
        updater.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeAssetResponse([b"a" * 10]),
    )
    dest = tmp_path / "setup.exe"
    with pytest.raises(UpdateCancelled):
        download_asset(
            "https://example.com/setup.exe", dest, cancel_check=lambda: True,
        )
    assert not dest.exists()  # 残缺文件已清理


def test_download_asset_network_error_raises(monkeypatch, tmp_path):
    def _raise(req, timeout=None):
        raise OSError("no network")

    monkeypatch.setattr(updater.urllib.request, "urlopen", _raise)
    with pytest.raises(UpdateError, match="网络未连接"):
        download_asset("https://example.com/setup.exe", tmp_path / "setup.exe")


# ---- 一键更新:脚本生成与启动 ----
def test_build_update_script_is_ascii_and_silent_installs():
    text = build_update_script(
        r"C:\tmp\MyToDo-Setup-v1.2.0.exe",
        r"D:\MyToDo", r"D:\MyToDo\MyToDo.exe", r"C:\tmp",
    )
    text.encode("ascii")  # 纯 ASCII,避免 cmd 代码页问题
    assert ":wait_loop" in text                 # 等旧进程退出再安装
    assert "/VERYSILENT" in text                # 静默安装不弹向导
    assert '/DIR="D:\\MyToDo"' in text          # 覆盖原安装目录
    assert 'start "" "D:\\MyToDo\\MyToDo.exe"' in text  # 更新后重启


def test_prepare_and_launch_update(tmp_path, monkeypatch):
    """生成更新脚本并用 cmd 启动(不真实执行)。"""
    dl_dir = tmp_path / "dl"
    dl_dir.mkdir()
    setup_path = dl_dir / "MyToDo-Setup-v1.2.0.exe"
    setup_path.write_bytes(b"MZ-fake")
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    launched = []
    monkeypatch.setattr(
        updater.subprocess, "Popen",
        lambda cmd, **kw: launched.append(cmd),
    )
    prepare_and_launch_update(setup_path, install_dir)
    script = dl_dir / "update.cmd"
    assert script.exists()
    body = script.read_text(encoding="mbcs")
    assert "MyToDo-Setup-v1.2.0.exe" in body
    assert str(install_dir) in body
    assert launched and launched[0][:2] == ["cmd", "/c"]


def test_prepare_and_launch_update_rejects_unwritable_dir(tmp_path):
    """安装目录不可写(用文件冒充目录)时应报友好错误。"""
    fake = tmp_path / "not_a_dir"
    fake.write_text("x", encoding="ascii")
    setup_path = tmp_path / "setup.exe"
    setup_path.write_bytes(b"")
    with pytest.raises(UpdateError, match="无写入权限"):
        prepare_and_launch_update(setup_path, fake)
