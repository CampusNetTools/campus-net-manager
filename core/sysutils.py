# -*- coding: utf-8 -*-
"""日志/通知/自启/电源断言/单实例锁 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import netinfo  # noqa: F401

__all__ = ['now_str', 'log', 'send_system_notification', '_trim_log', 'AUTOSTART_CMD', 'autostart_enabled', 'set_autostart', 'keep_awake_start', 'keep_awake_stop', 'keep_awake_enabled']

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    line = "[%s] %s" % (now_str(), msg)
    try:
        with open(common.LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        _trim_log()
    except Exception:
        pass
    return line


def send_system_notification(text, title="校园网连接管家"):
    """发送系统通知；失败时由界面回退到运行日志。"""
    if not common.IS_MACOS:
        return False
    script = ('on run argv\n'
              'display notification (item 2 of argv) with title (item 1 of argv)\n'
              'end run')
    try:
        result = subprocess.run(["/usr/bin/osascript", "-e", script, "--", title, text],
                                capture_output=True, timeout=8)
        return result.returncode == 0
    except Exception:
        return False


def _trim_log(max_bytes=2 * 1024 * 1024, keep_bytes=300 * 1024):
    """日志超过 2MB 时截断到 300KB, 防止无限增长"""
    try:
        if os.path.getsize(common.LOG_PATH) > max_bytes:
            with open(common.LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            with open(common.LOG_PATH, "w", encoding="utf-8") as f:
                f.write("...日志已自动清理...\n" + content[-keep_bytes:])
    except Exception:
        pass


# 开机自启: Windows 使用注册表 Run 键；macOS 使用当前用户的 LaunchAgent。
_AUTOSTART_NAME = "CampusNetManager"
_MAC_LAUNCH_LABEL = "com.campusnettools.campusnetmanager"
AUTOSTART_CMD = '"%s" "%s"' % (
    sys.executable if not getattr(sys, "frozen", False) else sys.executable,
    os.path.abspath(__file__) if not getattr(sys, "frozen", False) else os.path.join(BASE_DIR, "校园网连接管家.exe"),
)


def autostart_enabled():
    if common.IS_MACOS:
        return os.path.exists(os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", _MAC_LAUNCH_LABEL + ".plist"))
    out = netinfo._run_decode(["reg", "query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                       "/v", _AUTOSTART_NAME])
    return "CampusNetManager" in out


def set_autostart(enabled):
    """开启/关闭开机自启；macOS 只登记下次登录启动，不立即拉起第二个实例。"""
    if common.IS_MACOS:
        path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", _MAC_LAUNCH_LABEL + ".plist")
        try:
            if enabled:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.join(os.path.dirname(__file__), "app_gui.py")]
                with open(path, "wb") as f:
                    plistlib.dump({"Label": _MAC_LAUNCH_LABEL, "ProgramArguments": args,
                                   "RunAtLoad": True, "ProcessType": "Interactive"}, f)
                return True
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception:
            return False
    try:
        if enabled:
            # exe 版: 指向 exe 自己; 源码版: 指向 pythonw + app_gui.py
            if getattr(sys, "frozen", False):
                cmd = '"%s"' % os.path.join(BASE_DIR, "校园网连接管家.exe")
            else:
                pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                cmd = '"%s" "%s"' % (pyw, os.path.join(BASE_DIR, "app_gui.py"))
            r = subprocess.run(["reg", "add", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                                "/v", _AUTOSTART_NAME, "/t", "REG_SZ", "/d", cmd, "/f"],
                               capture_output=True, timeout=10,
                               creationflags=_NO_WINDOW)
            return r.returncode == 0
        else:
            r = subprocess.run(["reg", "delete", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                                "/v", _AUTOSTART_NAME, "/f"],
                               capture_output=True, timeout=10,
                               creationflags=_NO_WINDOW)
            return r.returncode == 0
    except Exception:
        return False


# ---------- 合盖/休眠保持运行 ----------
# macOS 笔记本合盖或系统空闲会自动进入睡眠, 守护线程随之暂停, 导致掉线后无法自动重登。
# caffeinate 是 macOS 自带命令, 可通过电源断言阻止系统睡眠/空闲睡眠, 让程序在合盖/休眠
# 状态下继续联网保活。仅 macOS 有效, Windows 用 nvidia/电源计划由系统管理, 此处返回 False。
_keep_awake_proc = None
_keep_awake_lock = threading.Lock()


def keep_awake_start():
    """启动 caffeinate 电源断言, 阻止系统睡眠/空闲睡眠/显示器睡眠。返回 True 表示已启动。
    仅 macOS 生效; 精灵窗口/合盖场景下守护线程可继续运行。"""
    global _keep_awake_proc
    if not common.IS_MACOS:
        return False
    with _keep_awake_lock:
        if _keep_awake_proc and _keep_awake_proc.poll() is None:
            return True  # 已在运行
        try:
            # -d 阻止显示器睡眠, -i 阻止空闲睡眠, -s 阻止系统睡眠(合盖), -m 阻止磁盘睡眠
            proc = subprocess.Popen(
                ["/usr/bin/caffeinate", "-d", "-i", "-s", "-m",
                 "-w", str(os.getpid())],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _keep_awake_proc = proc
            return True
        except Exception:
            return False


def keep_awake_stop():
    """停止 caffeinate 电源断言 (可选调用; 进程退出时 caffeinate 的 -w 标志会自动结束)。"""
    global _keep_awake_proc
    with _keep_awake_lock:
        if _keep_awake_proc and _keep_awake_proc.poll() is None:
            try:
                _keep_awake_proc.terminate()
            except Exception:
                pass
        _keep_awake_proc = None


def keep_awake_enabled():
    """查询保持唤醒是否正在生效。"""
    global _keep_awake_proc
    if not common.IS_MACOS:
        return False
    return bool(_keep_awake_proc and _keep_awake_proc.poll() is None)


# ---------- 版本与诊断 ----------
