# -*- coding: utf-8 -*-
"""自动更新: 检查 GitHub Releases 新版本、下载、平台自替换脚本。

设计要点:
- 网络请求走系统代理(urllib 默认), 校园网/Clash 环境下都能连 GitHub。
- 自替换采用"父进程退出后脚本替换"模式: macOS bash / Windows bat。
- 所有函数无副作用可测: 网络层通过 opener 注入, 脚本只生成不落盘执行。
"""
import datetime
import json
import os
import re
import stat
import sys
import tempfile
import urllib.request

REPO = "CampusNetTools/campus-net-manager"
API_LATEST = "https://api.github.com/repos/%s/releases/latest" % REPO
RELEASES_PAGE = "https://github.com/%s/releases/latest" % REPO

_UA = {"User-Agent": "CampusNetManager-Updater"}


def parse_version(text):
    """从 'v3.0.0' / '3.0.0' / 任意含版本号的文本提取 (3, 0, 0); 失败返回 None。"""
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(latest, current):
    lv, cv = parse_version(latest), parse_version(current)
    return bool(lv and cv and lv > cv)


def _log(msg):
    """写日志; 桌面端定位到 core.sysutils, 失败静默(独立环境不阻塞)。"""
    try:
        from core import sysutils
        sysutils.log(msg)
    except Exception:
        pass


def check_for_update(current_version, timeout=10, opener=None):
    """查询最新 Release。有更新返回信息 dict; 已最新/失败返回 None。

    返回: {tag, version, notes, page, assets: [{name, url, size}]}
    """
    open_fn = opener.open if opener else urllib.request.urlopen
    try:
        req = urllib.request.Request(API_LATEST, headers=_UA)
        with open_fn(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        _log("更新检查失败: %r (%s)" % (exc, API_LATEST))
        return None
    tag = data.get("tag_name", "")
    if not is_newer(tag, current_version):
        _log("更新检查: 已是最新 (%s)" % tag)
        return None
    assets = [{"name": a.get("name", ""),
               "url": a.get("browser_download_url", ""),
               "size": a.get("size", 0)}
              for a in data.get("assets", [])]
    return {"tag": tag,
            "version": parse_version(tag),
            "notes": (data.get("body") or "").strip(),
            "page": data.get("html_url") or RELEASES_PAGE,
            "assets": assets}


def pick_asset(assets, platform=None):
    """按平台挑安装包: macOS→*macos*.zip, Windows→*.exe。找不到返回 None。"""
    platform = platform or ("macos" if sys.platform == "darwin" else "windows")
    for a in assets:
        name = a.get("name", "").lower()
        if platform == "macos" and name.endswith(".zip") and "macos" in name:
            return a
        if platform == "windows" and name.endswith(".exe"):
            return a
    return None


def download(url, dest, progress=None, timeout=60, opener=None, chunk_size=65536):
    """下载到 dest, progress(已下载, 总大小) 回调。返回 dest。"""
    open_fn = opener.open if opener else urllib.request.urlopen
    req = urllib.request.Request(url, headers=_UA)
    with open_fn(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    return dest


# ---------- 自替换脚本 ----------

def macos_apply_script(app_path, new_app_path, pid=None):
    """生成 bash 脚本: 等待当前进程退出 → 替换 .app → 去隔离属性 → 重新打开。"""
    pid = pid or os.getpid()
    return """#!/bin/bash
# CampusNetManager 自更新脚本 (生成后由 App 启动, 然后 App 退出)
while kill -0 %d 2>/dev/null; do sleep 0.5; done
sleep 1
rm -rf "%s"
mv "%s" "%s"
xattr -dr com.apple.quarantine "%s" 2>/dev/null
open "%s"
rm -f "$0"
""" % (pid, app_path, new_app_path, app_path, app_path, app_path)


def windows_apply_script(exe_path, new_exe_path, pid=None):
    """生成 bat 脚本: 等待进程退出 → 替换 exe → 重启。仅 ASCII 路径注释, 中文路径由变量传。"""
    pid = pid or os.getpid()
    return """@echo off
rem CampusNetManager self-update script
:wait
tasklist /FI "PID eq %d" | find "%d" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)
timeout /t 1 /nobreak >nul
move /y "%s" "%s" >nul
start "" "%s"
del "%%~f0"
""" % (pid, pid, new_exe_path, exe_path, exe_path)


def write_apply_script(content, suffix):
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="cnm_update_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


# ---------- 自动检查节流/跳过 (纯函数, 供 GUI 与测试) ----------

def should_auto_check(prefs, now=None, interval_hours=20):
    """距离上次检查超过 interval_hours 才自动检查; 手动检查不受限。"""
    last = (prefs or {}).get("update_last_check", "")
    if not last:
        return True
    try:
        last_dt = datetime.datetime.fromisoformat(last)
    except ValueError:
        return True
    now = now or datetime.datetime.now()
    return (now - last_dt) >= datetime.timedelta(hours=interval_hours)


def should_notify(prefs, latest_tag):
    """用户没跳过这个版本才弹窗。"""
    return (prefs or {}).get("update_skip_version", "") != latest_tag


def mark_checked(prefs, now=None):
    prefs["update_last_check"] = (now or datetime.datetime.now()).isoformat(timespec="seconds")
    return prefs
