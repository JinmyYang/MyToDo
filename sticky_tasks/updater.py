"""检查更新与一键更新:查询 GitHub Releases 的最新版本并与当前版本比对。

纯标准库实现(urllib),不引入额外依赖;只发只读 GET 请求,
不上传任何用户数据。

一键更新流程(仅打包态可用):下载 Release 安装程序(MyToDo-Setup-*.exe)
→ 生成外部 cmd 脚本 → 程序退出后由脚本静默运行安装程序
(覆盖安装目录,卸载器等由 Inno Setup 维护)→ 重启程序。
运行中的 exe 被 Windows 锁定,无法自我覆盖,所以必须借助外部脚本。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# ---- GitHub 仓库(检查更新的数据来源)----
REPO_OWNER = "JinmyYang"
REPO_REPO = "MyToDo"

API_TIMEOUT = 8  # 秒
DOWNLOAD_TIMEOUT = 30  # 秒,作用于每次 socket 读取,大文件下载不受总时长限制


class UpdateError(Exception):
    """检查更新/下载/安装失败(未配置仓库 / 网络不通 / 响应异常)。"""


class UpdateCancelled(UpdateError):
    """用户主动取消下载,UI 层不当作错误提示。"""


def parse_version(text: str) -> tuple[int, ...]:
    """把 'v1.10.0' 之类的文本解析为数字元组,非法段按 0 处理。

    每段只取开头的数字部分(如 '0-beta1' 视为 0)。
    """
    parts = str(text).strip().lstrip("vV").split(".")
    nums = []
    for part in parts:
        match = re.match(r"\d+", part)
        nums.append(int(match.group()) if match else 0)
    return tuple(nums) or (0,)


def compare_versions(a: str, b: str) -> int:
    """语义化比较:a 新于 b 返回 1,旧于返回 -1,相同返回 0。

    长度不齐时短的一方补 0(如 1.2 == 1.2.0)。
    """
    va, vb = parse_version(a), parse_version(b)
    width = max(len(va), len(vb))
    va += (0,) * (width - len(va))
    vb += (0,) * (width - len(vb))
    if va > vb:
        return 1
    if va < vb:
        return -1
    return 0


def _pick_asset_url(assets: list) -> str:
    """从 Release 附件里挑安装程序直链,找不到返回空串。

    优先名称含 -setup- 的 .exe(如 MyToDo-Setup-v1.1.0.exe),兜底任意 .exe。
    """
    fallback = ""
    for asset in assets or []:
        url = asset.get("browser_download_url") or ""
        name = (asset.get("name") or "").lower()
        if "-setup-" in name and name.endswith(".exe"):
            return url
        if not fallback and name.endswith(".exe"):
            fallback = url
    return fallback


def check_for_update(current_version: str) -> dict | None:
    """查询最新 Release,有新版本返回信息字典,已是最新返回 None。

    主通道走 github.com 网页重定向(不受 API 匿名限流),失败再退回
    GitHub Releases API(可附带更新说明)。
    返回字段:version(新版本号)、notes(更新说明)、url(Release 页面)、
    asset_url(安装程序直链,可能为空串)。
    任何失败(含仓库未配置)统一抛 UpdateError,由 UI 层显示友好提示。
    """
    if not REPO_OWNER or not REPO_REPO:
        raise UpdateError("网络未连接，请稍后再试")
    try:
        return _check_via_redirect(current_version)
    except UpdateError:
        return _check_via_api(current_version)


def _parse_latest_tag(final_url: str) -> str:
    """从 /releases/tag/vX.Y.Z 形式的重定向终点提取版本号。

    仓库没有任何 Release 时 GitHub 会重定向到 /releases,返回空串。
    """
    match = re.search(r"/releases/tag/v?([^/]+)/?$", final_url)
    return match.group(1).lstrip("vV") if match else ""


def _check_via_redirect(current_version: str) -> dict | None:
    """用 github.com 网页重定向查最新版本:不消耗 API 匿名配额。

    安装程序链接按固定命名约定拼出(与 mytodo.iss 产物名一致)。
    """
    url = f"https://github.com/{REPO_OWNER}/{REPO_REPO}/releases/latest"
    request = urllib.request.Request(
        url, headers={"User-Agent": "MyToDo-UpdateCheck"},
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT) as resp:
            latest = _parse_latest_tag(resp.geturl())
    except Exception as exc:
        raise UpdateError("网络未连接，请检查网络后重试") from exc
    if not latest or compare_versions(latest, current_version) <= 0:
        return None
    tag = f"v{latest}"
    return {
        "version": latest,
        "notes": "",
        "url": f"https://github.com/{REPO_OWNER}/{REPO_REPO}/releases/tag/{tag}",
        "asset_url": (
            f"https://github.com/{REPO_OWNER}/{REPO_REPO}/releases"
            f"/download/{tag}/MyToDo-Setup-{tag}.exe"
        ),
    }


def _check_via_api(current_version: str) -> dict | None:
    """退回方案:GitHub Releases API(匿名限流 60 次/小时/出口 IP)。"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_REPO}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MyToDo-UpdateCheck",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise UpdateError("检查更新请求过于频繁，请稍后再试") from exc
        raise UpdateError("网络未连接，请检查网络后重试") from exc
    except Exception as exc:
        raise UpdateError("网络未连接，请检查网络后重试") from exc
    tag = data.get("tag_name") or ""
    latest = tag.lstrip("vV")
    if not latest or compare_versions(latest, current_version) <= 0:
        return None
    return {
        "version": latest,
        "notes": data.get("body") or "",
        "url": data.get("html_url") or "",
        "asset_url": _pick_asset_url(data.get("assets") or []),
    }


# ---- 一键更新:下载与安装 ----
def make_update_dir() -> Path:
    """创建本次更新的临时目录(安装程序下载与更新脚本都放这里)。

    更新脚本最后会整体删除该目录,完成自清理。
    """
    return Path(tempfile.mkdtemp(prefix="MyToDo_update_"))


def download_asset(
    url: str,
    dest_path,
    progress_cb=None,
    cancel_check=None,
) -> None:
    """流式下载 Release 附件到 dest_path。

    progress_cb(done, total):进度回调,total 为 0 表示服务端未给长度;
    cancel_check() 返回 True 时中止下载并删除残缺文件,抛 UpdateCancelled。
    其余失败统一抛 UpdateError。
    """
    dest_path = Path(dest_path)
    request = urllib.request.Request(
        url, headers={"User-Agent": "MyToDo-UpdateCheck"},
    )
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(dest_path, "wb") as f:
                while True:
                    if cancel_check is not None and cancel_check():
                        raise UpdateCancelled("用户取消下载")
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb is not None:
                        progress_cb(done, total)
    except UpdateCancelled:
        dest_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        dest_path.unlink(missing_ok=True)
        raise UpdateError("网络未连接，请检查网络后重试") from exc


def build_update_script(
    setup_path, install_dir, exe_path, temp_dir,
) -> str:
    """生成覆盖更新的 cmd 脚本文本(纯 ASCII,避免代码页问题)。

    流程:等当前程序进程退出 → 静默运行安装程序(/DIR 指定原安装目录,
    Inno Setup 覆盖升级)→ 安装成功则重启程序 → 删除临时目录与脚本自身。
    """
    exe_name = Path(exe_path).name
    return (
        "@echo off\n"
        "setlocal\n"
        f"set \"EXE_NAME={exe_name}\"\n"
        ":wait_loop\n"
        "tasklist /FI \"IMAGENAME eq %EXE_NAME%\" 2>NUL"
        " | find /I \"%EXE_NAME%\" >NUL\n"
        "if %ERRORLEVEL%==0 (\n"
        "    timeout /t 1 /nobreak >NUL\n"
        "    goto wait_loop\n"
        ")\n"
        f"\"{setup_path}\""
        f" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-"
        f" /DIR=\"{install_dir}\"\n"
        f"if not exist \"{exe_path}\" exit /b 1\n"
        f"start \"\" \"{exe_path}\"\n"
        f"rmdir /S /Q \"{temp_dir}\"\n"
        # 脚本自身在 temp_dir 里被锁,先删文件再补删空目录
        f"(goto) 2>NUL & del \"%~f0\" & rd \"{temp_dir}\"\n"
    )


def prepare_and_launch_update(setup_path, install_dir) -> None:
    """生成并启动外部更新脚本(调用方随后应退出程序)。

    setup_path 与脚本同处临时目录(setup_path 的父目录),脚本负责善后清理。
    安装目录不可写等失败统一抛 UpdateError。
    """
    setup_path = Path(setup_path)
    install_dir = Path(install_dir)
    temp_dir = setup_path.parent
    # 先探测安装目录可写性,避免下载完才发现无法覆盖
    probe = install_dir / ".mytodo_update_probe"
    try:
        probe.write_text("", encoding="ascii")
        probe.unlink()
    except OSError as exc:
        raise UpdateError("程序目录无写入权限，请前往下载页手动更新") from exc
    exe_path = install_dir / "MyToDo.exe"
    script = temp_dir / "update.cmd"
    text = build_update_script(setup_path, install_dir, exe_path, temp_dir)
    try:
        # cmd 按系统 ANSI 代码页读取,中文路径需 mbcs 编码写出
        script.write_text(text, encoding="mbcs")
    except (UnicodeEncodeError, LookupError):
        script.write_text(text, encoding="utf-8")
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    subprocess.Popen(["cmd", "/c", str(script)], **kwargs)
