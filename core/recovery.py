# -*- coding: utf-8 -*-
"""连接进度 / 恢复加速 —— 纯逻辑 (不依赖 GUI, 便于单元测试)。

断电重启后要等"连上外网", 慢通常卡在这几处:
  1. 路由器本体启动 (固件阶段, 管不了)
  2. 无线中继 (STA) 关联校园 WiFi 并拿到 IP
  3. 校园网上网认证 (Portal)
  4. 外网真正可达

管家能做的: 高频轮询路由器工作台状态, 把上面每个阶段可视化出来, 并在某个阶段
卡住时主动下发一次工作台动作 (重连中继 / 重新认证), 从而不必等路由器侧守护
自己的节奏 (实测中继守护约 6 分钟一轮、认证兜底约 2 分钟一轮)。

本模块只做判定与文案, 真正下发动作由 GUI 完成。
"""
import re

__all__ = ['UP_STAGES', 'parse_uptime_seconds', 'detect_stage', 'evaluate_progress']

# (key, 显示名, 该阶段完成时的进度)
UP_STAGES = [
    ("wait", "路由器工作台可达", 0),
    ("boot", "路由器已完成启动", 15),
    ("relay", "中继已连上校园 WiFi 并拿到 IP", 45),
    ("auth", "校园网上网认证已通过", 75),
    ("net", "外网已连通", 100),
]

#: 卡住多久就该主动推一把 (秒)
_NUDGE_AFTER = {
    "boot": ("reconnect_relay", 20),
    "relay": ("relogin", 10),
}


def parse_uptime_seconds(text):
    """把路由器 sys.uptime 解析成秒数, 无法解析返回 None。

    兼容 busybox/procps 常见格式:
        "24 min"、"20:23"(时:分)、"1:02:03"(时:分:秒)、
        "1 day, 2:03"、"3 days, 04:05"
    """
    if text is None:
        return None
    s = str(text).strip().lower()
    if not s:
        return None
    days = 0
    m = re.search(r"(\d+)\s*days?", s)
    if m:
        days = int(m.group(1))
        s = s[m.end():].lstrip(" ,")
    # 纯分钟写法: "24 min" / "24 minutes"
    m = re.fullmatch(r"(\d+)\s*min\w*", s)
    if m:
        return days * 86400 + int(m.group(1)) * 60
    # 冒号写法
    m = re.fullmatch(r"(\d+):(\d{1,2})(?::(\d{1,2}))?", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        c = int(m.group(3) or 0)
        if m.group(3) is None:
            secs = a * 3600 + b * 60          # 时:分
        else:
            secs = a * 3600 + b * 60 + c      # 时:分:秒
        return days * 86400 + secs
    m = re.fullmatch(r"(\d+)", s)
    if m:
        return days * 86400 + int(m.group(1)) * 60
    return None


def detect_stage(snap, reachable=True):
    """由一次状态快照判断当前连接阶段, 返回 UP_STAGES 的索引。"""
    if not reachable or not isinstance(snap, dict):
        return 0
    relay = snap.get("relay") or {}
    auth = str(snap.get("auth") or "")
    net = str(snap.get("net") or "")
    if "正常" in net or "通畅" in net:
        return 4
    if "在线" in auth:
        return 3
    if str(relay.get("ip") or "").strip():
        return 2
    return 1


def _detail_text(idx, snap):
    relay = (snap or {}).get("relay") or {}
    ap = (snap or {}).get("ap") or {}
    sysd = (snap or {}).get("sys") or {}
    if idx <= 0:
        return "正在连接路由器工作台…"
    if idx == 1:
        up = sysd.get("uptime") or "未知"
        return "路由器已启动 (运行 %s), 正在关联校园 WiFi「%s」…" % (
            up, relay.get("ssid") or "（未配置）")
    if idx == 2:
        return "中继已连上「%s」(信号 %s dBm, IP %s), 正在完成校园网认证…" % (
            relay.get("ssid") or "-", relay.get("signal") or "-", relay.get("ip") or "-")
    if idx == 3:
        return "校园网认证已通过, 正在等待外网真正可达…"
    return "外网已连通 (本机 AP「%s」, 运行 %s)" % (
        ap.get("ssid") or "-", sysd.get("uptime") or "-")


def evaluate_progress(snap, reachable=True, stage_seconds=0.0, elapsed=None):
    """汇总当前连接进度。

    snap:           status.sh 返回的 dict (不可达时给 None)
    reachable:      工作台是否可达
    stage_seconds:  在当前阶段已停留的秒数 (由调用方跨次累加, 用于判断"卡住")
    elapsed:        从开始等待起的总秒数 (仅用于显示)

    返回 dict:
        stage / stage_key / stage_label   当前阶段
        progress                          0~100 (当前阶段内会随时间缓慢爬升, 但不越过下一阶段)
        stages                            各阶段 [{key,label,done,active}]
        detail                            当前状态的一句话说明
        advice                            建议下发的动作 (reconnect_relay/relogin), 否则 None
        advice_text                       建议动作的中文说明
        stalled                           是否已卡住到该推一把的时长
    """
    idx = detect_stage(snap, reachable=reachable)
    key, label, base = UP_STAGES[idx]
    next_base = UP_STAGES[idx + 1][2] if idx + 1 < len(UP_STAGES) else base

    progress = float(base)
    if idx < len(UP_STAGES) - 1:
        # 阶段内轻微爬升: 最多吃掉到下一阶段差值的 60%, 避免看起来完全冻住
        creep = min(0.6 * (next_base - base), max(0.0, float(stage_seconds or 0)) * 0.5)
        progress = base + creep

    stages = []
    for i, (k, lb, _p) in enumerate(UP_STAGES):
        stages.append({"key": k, "label": lb, "done": i < idx, "active": i == idx})

    advice, advice_text, stalled = None, "", False
    rule = _NUDGE_AFTER.get(key)
    if rule and stage_seconds is not None and stage_seconds >= rule[1] and idx < 4:
        stalled = True
        advice = rule[0]
        advice_text = ("已在中继阶段等待 %d 秒, 建议主动重连中继"
                       if advice == "reconnect_relay"
                       else "已等待认证 %d 秒, 建议主动重新登录校园网") % int(stage_seconds)

    return {
        "stage": idx,
        "stage_key": key,
        "stage_label": label,
        "progress": progress,
        "stages": stages,
        "detail": _detail_text(idx, snap),
        "advice": advice,
        "advice_text": advice_text,
        "stalled": stalled,
        "elapsed": elapsed,
    }
