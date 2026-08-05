"""检查更新:查询 GitHub Releases 的最新版本并与当前版本比对。

纯标准库实现(urllib),不引入额外依赖;只发一个只读 GET 请求,
不上传任何用户数据。

发布前 TODO:仓库建好后填写下方 REPO_OWNER / REPO_REPO,
检查更新即可自动接通;未填写时点击会提示"网络未连接"。
"""

from __future__ import annotations

import json
import re
import urllib.request

# ---- 发布前填写(GitHub 用户名 / 仓库名)----
REPO_OWNER = ""
REPO_REPO = ""

API_TIMEOUT = 8  # 秒


class UpdateError(Exception):
    """检查更新失败(未配置仓库 / 网络不通 / 响应异常)。"""


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


def check_for_update(current_version: str) -> dict | None:
    """查询最新 Release,有新版本返回信息字典,已是最新返回 None。

    返回字段:version(新版本号)、notes(更新说明)、url(Release 页面)。
    任何失败(含仓库未配置)统一抛 UpdateError,由 UI 层显示友好提示。
    """
    if not REPO_OWNER or not REPO_REPO:
        raise UpdateError("网络未连接，请稍后再试")
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
    }
