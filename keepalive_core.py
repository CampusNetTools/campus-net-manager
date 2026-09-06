# -*- coding: utf-8 -*-
"""
校园网连接管家 - 核心模块门面 (facade)

v3.0.0 起实现拆分到 core/ 包, 本文件只re-export, 保持
`import keepalive_core` / `patch.object(keepalive_core, ...)` 旧代码可用。
唯一权威版本号: 本文件 APP_VERSION。
"""
import os  # noqa: F401  (测试 patch core.os)
import subprocess  # noqa: F401  (测试 patch core.subprocess)
import sys  # noqa: F401

from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core.config import *  # noqa: F401,F403
from core.history import *  # noqa: F401,F403
from core.netinfo import *  # noqa: F401,F403
from core.speed import *  # noqa: F401,F403
from core.router import *  # noqa: F401,F403
from core.portal import *  # noqa: F401,F403
from core.matching import *  # noqa: F401,F403
from core.auth import *  # noqa: F401,F403
from core.sysutils import *  # noqa: F401,F403
from core.daemon import *  # noqa: F401,F403
from core import config, netinfo, router, sysutils  # noqa: F401


APP_VERSION = "3.1.4"
APP_NAME = "校园网连接管家"


def collect_diagnostics():
    """收集诊断信息(密码脱敏), 供一键导出求助"""
    lines = []
    lines.append("=" * 46)
    lines.append("%s 诊断报告 v%s" % (APP_NAME, APP_VERSION))
    lines.append("时间: %s" % sysutils.now_str())
    lines.append("=" * 46)
    try:
        mode, ssid = netinfo.get_connection_mode()
        lines.append("连接方式: %s%s" % ("WiFi" if mode == "wifi" else "有线" if mode == "ethernet" else "无连接",
                                        " (%s)" % ssid if ssid else ""))
        lines.append("网关: %s" % (netinfo.get_gateway() or "-"))
        lines.append("网关MAC: %s" % (router.get_gateway_mac() or "-"))
        cfg = config.load_config()
        lines.append("档案数: %d" % len(cfg.get("profiles", [])))
        for p in cfg.get("profiles", []):
            lines.append("  档案[%s] ssid=%s 账号=%s 运营商=%s 间隔=%ss 认证=%s"
                         % (p.get("name", "?"),
                            p.get("ssid") or "任意",
                            p.get("username", ""),
                            p.get("login_type", ""),
                            p.get("interval", "?"),
                            p.get("auth_url", "")))
        lines.append("开机自启: %s" % ("开启" if sysutils.autostart_enabled() else "关闭"))
        lines.append("VPN隧道: %s" % ("已检测到" if netinfo.vpn_active() else "未检测到"))
        lines.append("热点共享: %s" % ("开启" if router.hotspot_on() else "关闭"))
    except Exception as e:
        lines.append("环境检测异常: %s" % e)
    lines.append("-" * 46)
    lines.append("最近日志:")
    try:
        if os.path.exists(common.LOG_PATH):
            with open(common.LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                tail = f.readlines()[-40:]
            lines.extend(l.rstrip("\n") for l in tail)
    except Exception:
        pass
    # 会话归属分析 (防踢排查): 用有账号档案探测一次, 看谁占着校园网名额
    lines.append("-" * 46)
    lines.append("会话归属:")
    try:
        import diagnostics
        for p in cfg.get("profiles", []):
            if p.get("username"):
                ana = diagnostics.analyze(p)
                if ana.get("ok"):
                    lines.append("  账号 %s -> 会话IP %s / 会话MAC %s (本机:%s) / 来源MAC %s (本机:%s) / %s"
                                 % (ana.get("uid"), ana.get("session_ip"), ana.get("session_mac"),
                                    "是" if ana.get("session_is_local") else "否",
                                    ana.get("source_mac"),
                                    "是" if ana.get("source_is_local") else "否",
                                    ana.get("note") or ""))
                else:
                    lines.append("  账号 %s -> 探测失败: %s" % (p.get("username"), ana.get("detail")))
                break
    except Exception as exc:
        lines.append("  会话分析异常: %s" % exc)
    return "\n".join(lines)


# ---------- 锁 ----------
def acquire_lock():
    try:
        if os.path.exists(common.LOCK_PATH):
            with open(common.LOCK_PATH) as f:
                old_pid = f.read().strip()
            if old_pid and old_pid != str(os.getpid()):
                if common.IS_MACOS:
                    try:
                        os.kill(int(old_pid), 0)
                        return False
                    except (OSError, ValueError):
                        pass
                else:
                    out = netinfo._run_decode(["tasklist", "/FI", "PID eq %s" % old_pid])
                    if old_pid in out:
                        return False
        with open(common.LOCK_PATH, "w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return True


def release_lock():
    try:
        if os.path.exists(common.LOCK_PATH):
            os.remove(common.LOCK_PATH)
    except Exception:
        pass
