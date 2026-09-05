# -*- coding: utf-8 -*-
"""网络历史记录与断网时间线 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import sysutils  # noqa: F401

__all__ = ['record_network_history', 'summarize_network_history', 'analyze_outage_timeline', '_fmt_duration']

def record_network_history(cfg, event, message, **details):
    if not cfg.get("history_enabled", False):
        return False
    item = {"time": sysutils.now_str(), "event": event, "message": message, "details": details}
    try:
        with open(common.HISTORY_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        if os.path.getsize(common.HISTORY_PATH) > 2 * 1024 * 1024:
            with open(common.HISTORY_PATH, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()[-5000:]
            with open(common.HISTORY_PATH, "w", encoding="utf-8") as handle:
                handle.writelines(lines)
        return True
    except Exception:
        return False


def summarize_network_history(days=7):
    """将技术事件汇总成普通用户可以理解的稳定性报告。"""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    events = []
    try:
        with open(common.HISTORY_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                    when = datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
                    if when >= cutoff:
                        events.append(item)
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    counts = {key: 0 for key in ("online", "disconnect", "recovery", "failure", "vpn_issue")}
    for item in events:
        if item.get("event") in counts:
            counts[item["event"]] += 1
    checks = counts["online"] + counts["disconnect"] + counts["vpn_issue"]
    stable = (counts["online"] * 100.0 / checks) if checks else None
    if not events:
        summary = "还没有可汇总的网络记录。开启保存后，软件会在这里解释最近的稳定情况。"
    elif counts["failure"]:
        summary = "网络近期不太稳定，有自动恢复失败的情况，建议检查账号、路由器或校园出口。"
    elif counts["disconnect"] or counts["vpn_issue"]:
        summary = "网络偶尔出现波动，大多数时候软件能够继续检测或自动恢复。"
    else:
        summary = "网络整体稳定，最近没有记录到明显掉线。"
    return {"days": days, "events": len(events), "counts": counts, "stable_percent": stable,
            "summary": summary}


def analyze_outage_timeline(days=7):
    """提取断网时间线: 每次掉线的事件 + 下次恢复, 计算断网时长和频率。
    返回 [{start, end, duration_s, event, message}...] 按时间排序。"""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    events = []
    try:
        with open(common.HISTORY_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                    when = datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
                    if when >= cutoff:
                        events.append(item)
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    # 断网事件 = disconnect 或 failure; 恢复 = recovery 或 online
    outages = []
    last_disconnect_time = None
    last_disconnect_msg = ""
    for item in events:
        ev = item.get("event")
        when = datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
        if ev == "disconnect":
            last_disconnect_time = when
            last_disconnect_msg = item.get("message", "")
        elif ev in ("recovery", "online"):
            if last_disconnect_time is not None:
                end = when
                dur = (end - last_disconnect_time).total_seconds()
                outages.append({
                    "start": last_disconnect_time.strftime("%m-%d %H:%M:%S"),
                    "end": end.strftime("%m-%d %H:%M:%S"),
                    "duration_s": int(dur),
                    "duration": _fmt_duration(dur),
                    "message": last_disconnect_msg,
                })
                last_disconnect_time = None
    # 若最后一次断网还没恢复
    if last_disconnect_time is not None:
        now = datetime.datetime.now()
        dur = (now - last_disconnect_time).total_seconds()
        outages.append({
            "start": last_disconnect_time.strftime("%m-%d %H:%M:%S"),
            "end": "至今未恢复",
            "duration_s": int(dur),
            "duration": _fmt_duration(dur),
            "message": last_disconnect_msg,
        })
    return outages


def _fmt_duration(seconds):
    """秒 -> 友好时长 (X分X秒 / X小时X分 / X天X小时)"""
    seconds = int(seconds)
    if seconds < 60:
        return "%d秒" % seconds
    if seconds < 3600:
        return "%d分%d秒" % (seconds // 60, seconds % 60)
    if seconds < 86400:
        return "%d小时%d分" % (seconds // 3600, (seconds % 3600) // 60)
    return "%d天%d小时" % (seconds // 86400, (seconds % 86400) // 3600)


# ---------- 环境识别 ----------
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
