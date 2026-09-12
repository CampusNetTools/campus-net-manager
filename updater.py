# -*- coding: utf-8 -*-
"""自动更新: 检查 GitHub Releases 新版本、下载、平台自替换脚本。

设计要点:
- 网络请求走系统代理(urllib 默认), 校园网/Clash 环境下都能连 GitHub。
- 自替换采用"父进程退出后脚本替换"模式: macOS bash / Windows bat。
- 下载后校验 SHA256: 优先用 GitHub 资产自带的 digest 字段, 否则下载配套的
  SHA256SUMS/<asset>.sha256 校验和文件; 校验不过直接删除并中止, 绝不替换运行。
- 所有函数无副作用可测: 网络层通过 opener 注入, 脚本只生成不落盘执行。
"""
import datetime
import hashlib
import hmac
import json
import locale
import os
import re
import ssl
import stat
import sys
import tempfile
import urllib.request
import urllib.error

try:
    import certifi
    HAS_CERTIFI = True
except Exception:
    HAS_CERTIFI = False


def _ssl_context():
    """带证书包的 SSL 上下文: PyInstaller 冻结包找不到系统 CA 时用 certifi 兜底
    (根因 2026-09-06: 冻结 App 检查 GitHub 报 CERTIFICATE_VERIFY_FAILED, 更新弹窗从未真正触发)。"""
    ctx = ssl.create_default_context()
    if HAS_CERTIFI:
        try:
            ctx.load_verify_locations(certifi.where())
        except Exception:
            pass
    return ctx

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
    try:
        req = urllib.request.Request(API_LATEST, headers=_UA)
        if opener:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        else:
            with urllib.request.urlopen(req, timeout=timeout,
                                        context=_ssl_context()) as resp:
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
               "size": a.get("size", 0),
               "digest": a.get("digest") or ""}   # GitHub 会带 "sha256:<hex>"
              for a in data.get("assets", [])]
    return {"tag": tag,
            "version": parse_version(tag),
            "notes": (data.get("body") or "").strip(),
            "page": data.get("html_url") or RELEASES_PAGE,
            "assets": assets}


# 规范资产命名: 校园网连接管家-<版本>-win64.exe / 校园网连接管家-macOS-arm64-<版本>.zip。
# v5.2.1 起 Windows exe 统一改中文名「校园网连接管家」(与 macOS .app 一致);
# 旧英文名 CampusNetManager-<版本>-*(连字符)仍视为规范;
# 更旧的下划线命名 CampusNetManager_v*_* 是次选 —— 历史上 Release 里多个都传过,
# 按顺序取第一个会取到 Mac 侧误传的重复包。
_CANONICAL_ASSET = re.compile(
    r"^(校园网连接管家|campusnetmanager)-[^-]+-(win64|windows|macos|arm64)",
    re.IGNORECASE)


def asset_candidates(assets, platform=None):
    """返回该平台的全部候选资产, 规范命名优先、其次名字更短的。"""
    platform = platform or ("macos" if sys.platform == "darwin" else "windows")
    out = []
    for a in assets or []:
        name = (a.get("name") or "").lower()
        if platform == "macos" and not (name.endswith(".zip") and "macos" in name):
            continue
        if platform == "windows" and not name.endswith(".exe"):
            continue
        out.append(a)
    out.sort(key=lambda a: (0 if _CANONICAL_ASSET.match(a.get("name") or "") else 1,
                            len(a.get("name") or "")))
    return out


def pick_asset(assets, platform=None):
    """按平台挑安装包: macOS→*macos*.zip, Windows→*.exe。找不到返回 None。

    多个候选时优先规范命名, 并写日志记录被跳过的重复包 —— 避免再次出现
    "Mac 侧误传的重复 exe 抢在规范包前面被选中"的事故。
    """
    cands = asset_candidates(assets, platform)
    if not cands:
        return None
    if len(cands) > 1:
        _log("同平台存在 %d 个安装包, 选用 %s; 其余: %s"
             % (len(cands), cands[0].get("name", "?"),
                ", ".join(a.get("name", "?") for a in cands[1:])))
    return cands[0]


# ---------- SHA256 校验 ----------

_HEX64 = re.compile(r"\b([0-9a-fA-F]{64})\b")
_CHECKSUM_NAMES = ("sha256sums", "sha256sums.txt", "sha256sum", "checksums.txt")


def sha256_of_file(path, chunk_size=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def digest_to_hex(digest):
    """GitHub asset.digest 形如 'sha256:abcdef…' → 纯 hex; 非法返回 ""。"""
    text = (digest or "").strip().lower()
    if text.startswith("sha256:"):
        text = text.split(":", 1)[1]
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else ""


def parse_checksum_for(text, filename):
    """从 sha256sum 格式文本里取指定文件的哈希。

    支持 "<hex>  <file>" 与 "<hex> *<file>"; 只有单条记录且未写文件名时直接采用。
    """
    lines = [ln for ln in (text or "").splitlines() if _HEX64.search(ln)]
    if not lines:
        return ""
    target = (filename or "").strip().lower()
    for line in lines:
        match = _HEX64.search(line)
        rest = line.replace(match.group(1), "", 1).strip().lstrip("*").strip().lower()
        if target and (rest == target or rest.endswith(target)):
            return match.group(1).lower()
    if len(lines) == 1:
        return _HEX64.search(lines[0]).group(1).lower()
    return ""


def checksum_asset_for(assets, asset_name):
    """找配套校验和资产: <asset>.sha256 优先, 其次 SHA256SUMS(.txt)。"""
    wanted = [(asset_name or "").lower() + s
              for s in (".sha256", ".sha256sum", ".sha256.txt")]
    fallback = None
    for a in assets or []:
        name = (a.get("name") or "").lower()
        if name in wanted:
            return a
        if name in _CHECKSUM_NAMES and fallback is None:
            fallback = a
    return fallback


def resolve_expected_sha256(assets, asset, opener=None, timeout=15):
    """解析目标资产应有的 SHA256。

    优先级: 资产自带 digest(GitHub API) > 独立校验和文件 > ""(无法校验)。
    任何网络/解析失败都返回 "", 由调用方决定是否放行(见 verify_download)。
    """
    hex_value = digest_to_hex((asset or {}).get("digest"))
    if hex_value:
        return hex_value
    checksum = checksum_asset_for(assets, (asset or {}).get("name", ""))
    if not checksum or not checksum.get("url"):
        return ""
    try:
        req = urllib.request.Request(checksum["url"], headers=_UA)
        if opener:
            with opener.open(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        else:
            with urllib.request.urlopen(req, timeout=timeout,
                                        context=_ssl_context()) as resp:
                text = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        _log("校验和文件下载失败: %r" % exc)
        return ""
    return parse_checksum_for(text, (asset or {}).get("name", ""))


def verify_download(path, expected_sha256):
    """校验已下载文件, 返回 (ok, message)。expected 为空时不拦截(只提示未校验)。"""
    if not expected_sha256:
        return True, "未提供 SHA256, 跳过校验(建议 Release 附带 SHA256SUMS)"
    try:
        actual = sha256_of_file(path)
    except Exception as exc:
        return False, "无法读取下载文件: %s" % exc
    if hmac.compare_digest(actual.lower(), expected_sha256.strip().lower()):
        return True, "SHA256 校验通过"
    return False, "SHA256 校验失败(期望 %s…, 实际 %s…)" % (
        expected_sha256[:12], actual[:12])


def download(url, dest, progress=None, timeout=60, opener=None, chunk_size=65536):
    """下载到 dest, progress(已下载, 总大小) 回调。返回 dest。"""
    req = urllib.request.Request(url, headers=_UA)
    if opener:
        ctx_resp = opener.open(req, timeout=timeout)
    else:
        ctx_resp = urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())
    with ctx_resp as resp:
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

def macos_apply_script(app_path, new_app_path, pid=None, stale_apps=()):
    """生成 bash 脚本: 等待当前进程退出 → 替换 .app → 去隔离属性 → 重新打开。

    stale_apps: 同目录下要清理的旧版本 .app(历史英文名 CampusNetManager.app 等),
    在替换成功后 rm -rf, 保证目录里只留最新一个。"""
    pid = pid or os.getpid()
    cleanup = ""
    for stale in (stale_apps or ()):
        if stale and os.path.normcase(os.path.abspath(stale)) != \
                os.path.normcase(os.path.abspath(app_path)):
            cleanup += 'rm -rf "%s"\n' % stale
    return """#!/bin/bash
# CampusNetManager 自更新脚本 (生成后由 App 启动, 然后 App 退出)
while kill -0 %d 2>/dev/null; do sleep 0.5; done
sleep 1
rm -rf "%s"
mv "%s" "%s"
%sxattr -dr com.apple.quarantine "%s" 2>/dev/null
open "%s"
rm -f "$0"
""" % (pid, app_path, new_app_path, app_path, cleanup, app_path, app_path)


def stale_version_patterns():
    """返回「同目录下旧版本安装包」的文件名匹配模式(用于更新后清理残留)。

    覆盖所有历史命名, 让用户目录里最终只剩当前运行的这一个 exe:
    - 校园网连接管家.exe            (v5.2.1 起中文名, 无版本号)
    - 校园网连接管家-vX.Y.Z-win64.exe
    - CampusNetManager.exe          (v5.2.0 及以前英文名, 无版本号)
    - CampusNetManager-vX.Y.Z-win64.exe / CampusNetManager_vX.Y.Z_win64.exe
    """
    return ("校园网连接管家*.exe", "CampusNetManager*.exe")


def windows_apply_script(exe_path, new_exe_path, pid=None, stale_exe=(),
                         final_exe=None):
    """生成 bat 脚本: 等待进程退出 → 替换 exe → 清理同目录旧版本 → 重启。

    exe_path:      当前正在运行的 exe 完整路径(等待其退出 + 作为兜底覆盖目标)。
    new_exe_path:  已下载的新 exe 完整路径(move 的源)。
    final_exe:     更新后希望保留的最终文件名(规范中文名「校园网连接管家.exe」)。
                   缺省时=exe_path(即覆盖原路径, 保持原文件名)。
                   若 final_exe != exe_path: 新文件落到 final_exe, 原 exe_path
                   与其它旧版本一并删除, 目录里只留这一个规范名 exe。
    stale_exe:     额外要删除的同目录旧版本 exe(历史英文名/带版本号残留)。

    编码: cmd 按系统 ANSI 代码页(中文 Windows=GBK)解码 bat —— write_apply_script
    对 .bat 用本地 ANSI 编码落盘, 中文路径(如 桌面\\校园网连接管家.exe)才能正确解析。
    find/timeout 必须用 System32 绝对路径: PATH 上若有 Git/MSYS 的 GNU find、
    GNU timeout, 裸命令名会被劫持, 导致等待循环与计时全部失效。"""
    pid = pid or os.getpid()
    sys32 = os.environ.get("SystemRoot", r"C:\Windows") + r"\System32"
    final = final_exe or exe_path
    # move 的目标: 若 final 与 exe_path 不同, 直接落到 final; 否则覆盖 exe_path。
    move_target = final
    cleanup = ""
    # 清理名单: 旧 exe_path(若 != final) + 所有 stale, 去重且排除最终文件。
    seen = set()
    for stale in list(stale_exe or ()) + [exe_path]:
        if not stale:
            continue
        if os.path.normcase(os.path.abspath(stale)) == \
                os.path.normcase(os.path.abspath(final)):
            continue
        key = os.path.normcase(os.path.abspath(stale))
        if key in seen:
            continue
        seen.add(key)
        cleanup += 'if exist "%s" del /f /q "%s" >nul\n' % (stale, stale)
    return """@echo off
rem CampusNetManager self-update script
:wait
tasklist /FI "PID eq %d" | "%s\\find.exe" "%d" >nul
if not errorlevel 1 (
    "%s\\timeout.exe" /t 1 /nobreak >nul
    goto wait
)
"%s\\timeout.exe" /t 1 /nobreak >nul
move /y "%s" "%s" >nul
%sstart "" "%s"
del "%%~f0"
""" % (pid, sys32, pid, sys32, sys32, new_exe_path, move_target, cleanup, final)


def find_stale_executables(directory, current_exe):
    """列出目录下应清理的旧版本 exe(不含当前运行的 exe)。

    用 stale_version_patterns 的 glob 匹配, 排除 current_exe 本身 ——
    供 GUI 在生成自替换脚本前枚举, 把旧版本名单写进脚本一次性清掉。
    """
    import glob
    directory = os.path.abspath(directory)
    current = os.path.normcase(os.path.abspath(current_exe))
    stale = []
    for pattern in stale_version_patterns():
        for path in glob.glob(os.path.join(directory, pattern)):
            if os.path.isfile(path) and os.path.normcase(os.path.abspath(path)) != current:
                stale.append(path)
    return sorted(set(stale))


def find_stale_apps(directory, current_app):
    """列出目录下应清理的旧版本 .app(不含当前运行的 .app)。

    覆盖中文名「校园网连接管家.app」与历史英文名「CampusNetManager.app」两种,
    让目录里最终只留最新一个。"""
    import glob
    directory = os.path.abspath(directory)
    current = os.path.normcase(os.path.abspath(current_app))
    stale = []
    for pattern in ("校园网连接管家.app", "CampusNetManager.app"):
        for path in glob.glob(os.path.join(directory, pattern)):
            if os.path.isdir(path) and os.path.normcase(os.path.abspath(path)) != current:
                stale.append(path)
    return sorted(set(stale))


def _bat_encoding():
    """cmd 解析 bat 用的是系统 ANSI 代码页(中文 Windows=cp936)。
    不能用 locale.getpreferredencoding: Python 开 UTF-8 模式时它返回 utf-8,
    与 cmd 的实际解码代码页脱节。用 Win32 GetACP 拿真实值。"""
    try:
        import ctypes
        acp = ctypes.windll.kernel32.GetACP()
        return "cp%d" % acp
    except Exception:
        return "gbk"


def write_apply_script(content, suffix):
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="cnm_update_")
    if suffix.lower() == ".bat" and os.name == "nt":
        # cmd 按系统 ANSI 代码页解码 bat; 用 UTF-8 写会把中文路径
        # (桌面\校园网连接管家.exe)变成乱码, 替换必然失败。
        encoding = _bat_encoding()
    else:
        encoding = "utf-8"
    with os.fdopen(fd, "w", encoding=encoding, errors="replace") as f:
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
