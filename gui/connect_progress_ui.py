# -*- coding: utf-8 -*-
"""「连接进度」窗口 Mixin (v5.3.0 新增)。

断电重启后要等"连上外网", 慢的根源在路由器侧的节奏:
  - 中继守护约 6 分钟一轮 (中继没拿到 IP 时要等下一轮才重连)
  - Portal 认证兜底约 2 分钟一轮 (crontab */2), 认证失败还会指数退避
本窗口在电脑端高频轮询 (2 秒/次), 把每个阶段画成进度条, 并在某一阶段卡住时
**主动下发一次工作台动作**(重连中继 / 重新登录校园网), 从而绕开上面的等待。

设计取舍: 仍然只做 HTTP 客户端, 不依赖 SSH; 路由器不在线时窗口自身安全。
判定/进度/建议全部落在 core.recovery 的纯函数里, 便于单元测试。
"""
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from urllib import request as urlrequest

from core import recovery as core_recovery

from gui.theme import *  # noqa: F401,F403
from gui.router_console_ui import (  # noqa: F401
    RC_DEFAULT_HOST, RC_DEFAULT_PORT, RC_DEFAULT_TOKEN, RC_TIMEOUT,
    rc_server_date)

CP_POLL_MS = 2000          # 轮询间隔
CP_NUDGE_COOLDOWN = 25     # 同一动作最短间隔(秒), 防止动作打太密
CP_HISTORY = 60            # 日志区保留行数


class ConnectProgressMixin:
    """「连接进度」窗口。"""

    # ------------------------------------------------------------------ 配置
    def _cp_settings(self):
        try:
            return self._rc_settings()                 # 与工作台窗口共用配置
        except Exception:
            return {"host": RC_DEFAULT_HOST, "port": str(RC_DEFAULT_PORT),
                    "token": RC_DEFAULT_TOKEN}

    def _cp_base(self):
        conf = self._cp_settings()
        return "http://%s:%s" % (conf["host"], conf["port"])

    # ------------------------------------------------------------------ 窗口
    def show_connect_progress_window(self):
        try:
            existing = getattr(self, "_cp_window", None)
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return
        except Exception:
            pass

        self._cp_style()
        self._cp_state = {
            "started_at": time.time(),
            "stage": None,
            "stage_since": time.time(),
            "last_nudge": {},
            "auto": True,
            "reachable": False,
        }
        self._cp_lines = []

        win = tk.Toplevel(self)
        self._cp_window = win
        win.title("校园网连接进度")
        win.configure(bg=BG)
        win.geometry("620x680")
        win.minsize(560, 560)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 20))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="校园网连接进度", style="DialogTitle.TLabel").grid(
            row=0, column=0, sticky="w")
        self._cp_sub = ttk.Label(
            card,
            text="实时跟踪「路由器启动 → 中继关联 → 校园网认证 → 外网连通」四个阶段, "
                 "并在卡住时自动推一把。",
            style="Muted.TLabel", wraplength=560)
        self._cp_sub.grid(row=1, column=0, sticky="w", pady=(6, 14))

        # ---------- 进度条 ----------
        pbar_row = ttk.Frame(card, style="Card.TFrame")
        pbar_row.grid(row=2, column=0, sticky="ew")
        pbar_row.columnconfigure(0, weight=1)
        self._cp_bar = ttk.Progressbar(pbar_row, style="Conn.Horizontal.TProgressbar",
                                       mode="determinate", maximum=100.0)
        self._cp_bar.grid(row=0, column=0, sticky="ew")
        self._cp_pct = ttk.Label(pbar_row, text="0%", style="CpPct.TLabel")
        self._cp_pct.grid(row=0, column=1, sticky="e", padx=(12, 0))

        self._cp_head = ttk.Label(card, text="正在连接…", style="CpHead.TLabel",
                                  wraplength=560)
        self._cp_head.grid(row=3, column=0, sticky="w", pady=(12, 2))
        self._cp_detail = ttk.Label(card, text="", style="Muted.TLabel", wraplength=560)
        self._cp_detail.grid(row=4, column=0, sticky="w")

        # ---------- 阶段清单 ----------
        ttk.Label(card, text="阶段", style="Field.TLabel").grid(
            row=5, column=0, sticky="w", pady=(14, 4))
        stage_box = ttk.Frame(card, style="Card.TFrame")
        stage_box.grid(row=6, column=0, sticky="ew")
        stage_box.columnconfigure(0, weight=1)
        self._cp_stage_labels = []
        for i, (_k, lb, _p) in enumerate(core_recovery.UP_STAGES):
            lab = ttk.Label(stage_box, text="○  " + lb, style="CpStageIdle.TLabel")
            lab.grid(row=i, column=0, sticky="w", pady=1)
            self._cp_stage_labels.append(lab)

        # ---------- 计时 / 动作 ----------
        meta = ttk.Frame(card, style="Card.TFrame")
        meta.grid(row=7, column=0, sticky="ew", pady=(14, 0))
        meta.columnconfigure(1, weight=1)
        self._cp_timer = ttk.Label(meta, text="已等待 00:00", style="Card.TLabel")
        self._cp_timer.grid(row=0, column=0, sticky="w")
        self._cp_auto_btn = ttk.Button(meta, text="自动加速: 开", style="AutoOn.TButton",
                                       command=self._cp_toggle_auto)
        self._cp_auto_btn.grid(row=0, column=1, sticky="e")

        acts = ttk.Frame(card, style="Card.TFrame")
        acts.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        for i in range(4):
            acts.columnconfigure(i, weight=1, uniform="cpact")
        ttk.Button(acts, text="重新计时", style="Gray.TButton",
                   command=self._cp_restart).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(acts, text="立即重连中继", style="Gray.TButton",
                   command=lambda: self._cp_nudge("reconnect_relay", force=True)).grid(
            row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(acts, text="重新登录校园网", style="Gray.TButton",
                   command=lambda: self._cp_nudge("relogin", force=True)).grid(
            row=0, column=2, sticky="ew", padx=(0, 6))
        ttk.Button(acts, text="关闭", style="Gray.TButton",
                   command=lambda: self._cp_close()).grid(row=0, column=3, sticky="ew")

        # ---------- 动作日志 ----------
        ttk.Label(card, text="动作记录", style="Field.TLabel").grid(
            row=9, column=0, sticky="w", pady=(14, 4))
        logbox = tk.Text(card, height=7, width=1, bg="#09101c", fg="#9fb0c8",
                         font=("PingFang SC", 9), relief="flat", wrap="word",
                         padx=10, pady=8, state="disabled")
        logbox.grid(row=10, column=0, sticky="nsew")
        card.rowconfigure(10, weight=1)
        self._cp_logbox = logbox

        win.protocol("WM_DELETE_WINDOW", self._cp_close)

        def _cp_on_resize(_e=None):
            try:
                wpx = win.winfo_width() - 96
                if wpx > 260:
                    for lb in (self._cp_sub, self._cp_head, self._cp_detail):
                        lb.configure(wraplength=wpx)
            except Exception:
                pass

        win.bind("<Configure>", _cp_on_resize)
        self._cp_log("开始跟踪连接进度 (每 %d 秒刷新一次)" % (CP_POLL_MS // 1000))
        self._cp_tick()

    def _cp_style(self):
        """进度条等局部样式 (即使主窗样式未应用也能正常显示)。"""
        try:
            s = ttk.Style(self)
            s.configure("Conn.Horizontal.TProgressbar", troughcolor=CARD2,
                        background=ACCENT, bordercolor=BORDER, lightcolor=ACCENT,
                        darkcolor=ACCENT, thickness=14)
            s.configure("CpPct.TLabel", background=CARD, foreground=ACCENT,
                        font=("PingFang SC", 16, "bold"))
            s.configure("CpHead.TLabel", background=CARD, foreground=FG,
                        font=("PingFang SC", 13, "bold"))
            s.configure("CpStageIdle.TLabel", background=CARD, foreground=MUTED, font=FONT)
            s.configure("CpStageActive.TLabel", background=CARD, foreground=ACCENT, font=FONT)
            s.configure("CpStageDone.TLabel", background=CARD, foreground=GREEN, font=FONT)
        except Exception:
            pass

    # ------------------------------------------------------------------ 交互
    def _cp_close(self):
        try:
            if self._cp_window is not None and self._cp_window.winfo_exists():
                self._cp_window.destroy()
        except Exception:
            pass
        self._cp_window = None

    def _cp_restart(self):
        st = getattr(self, "_cp_state", None)
        if st:
            st["started_at"] = time.time()
            st["stage"] = None
            st["stage_since"] = time.time()
            st["last_nudge"] = {}
        self._cp_log("已重新计时")
        self._cp_tick()

    def _cp_toggle_auto(self):
        st = getattr(self, "_cp_state", None)
        if not st:
            return
        st["auto"] = not st.get("auto", True)
        on = st["auto"]
        try:
            self._cp_auto_btn.configure(text="自动加速: %s" % ("开" if on else "关"),
                                        style="AutoOn.TButton" if on else "AutoOff.TButton")
        except Exception:
            pass
        self._cp_log("自动加速已%s" % ("开启" if on else "关闭"))

    def _cp_log(self, text):
        lines = getattr(self, "_cp_lines", None)
        if lines is None:
            lines = self._cp_lines = []
        lines.append("%s  %s" % (time.strftime("%H:%M:%S"), text))
        del lines[:-CP_HISTORY]
        try:
            box = self._cp_logbox
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", "\n".join(lines))
            box.see("end")
            box.configure(state="disabled")
        except Exception:
            pass

    # ------------------------------------------------------------------ 轮询
    def _cp_tick(self):
        win = getattr(self, "_cp_window", None)
        if win is None or not win.winfo_exists():
            return
        base = self._cp_base()

        def worker():
            snap, reachable = None, False
            try:
                with urlrequest.urlopen(base + "/cgi-bin/status.sh",
                                         timeout=RC_TIMEOUT) as resp:
                    snap = json.loads(resp.read().decode("utf-8", errors="replace"))
                reachable = True
            except Exception:
                snap, reachable = None, False
            try:
                self.after(0, lambda: self._cp_render(snap, reachable))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _cp_render(self, snap, reachable):
        win = getattr(self, "_cp_window", None)
        if win is None or not win.winfo_exists():
            return
        st = getattr(self, "_cp_state", None)
        if st is None:
            return

        now = time.time()
        info = core_recovery.evaluate_progress(
            snap, reachable=reachable,
            stage_seconds=now - st.get("stage_since", now),
            elapsed=now - st.get("started_at", now))

        # 阶段切换 -> 重置阶段计时
        if st.get("stage") != info["stage"]:
            if st.get("stage") is not None:
                self._cp_log("进入阶段 %d/%d: %s" % (
                    info["stage"], len(core_recovery.UP_STAGES) - 1, info["stage_label"]))
            st["stage"] = info["stage"]
            st["stage_since"] = now

        # 进度条 / 文本
        try:
            self._cp_bar.configure(value=info["progress"])
            self._cp_pct.configure(text="%d%%" % int(round(info["progress"])))
            self._cp_head.configure(text=info["stage_label"])
            self._cp_detail.configure(text=info["detail"])
            elapsed = int(now - st.get("started_at", now))
            self._cp_timer.configure(text="已等待 %02d:%02d" % (elapsed // 60, elapsed % 60))
            for i, lab in enumerate(self._cp_stage_labels):
                s = info["stages"][i]
                mark = "✓" if s["done"] else ("●" if s["active"] else "○")
                style = ("CpStageDone.TLabel" if s["done"]
                         else ("CpStageActive.TLabel" if s["active"] else "CpStageIdle.TLabel"))
                lab.configure(text="%s  %s" % (mark, s["label"]), style=style)
        except Exception:
            pass

        st["reachable"] = reachable

        # 完成后停表提示
        if info["stage"] >= len(core_recovery.UP_STAGES) - 1:
            if not st.get("done_logged"):
                st["done_logged"] = True
                secs = int(now - st.get("started_at", now))
                self._cp_log("✓ 外网已连通, 本次共等待 %d 分 %d 秒" % (secs // 60, secs % 60))
        else:
            st["done_logged"] = False

        # 自动加速
        if st.get("auto", True) and info["advice"]:
            last = st["last_nudge"].get(info["advice"], 0)
            if now - last >= CP_NUDGE_COOLDOWN:
                st["last_nudge"][info["advice"]] = now
                self._cp_log("卡在「%s」→ 自动下发 %s" % (info["stage_label"], info["advice"]))
                self._cp_nudge(info["advice"])
            else:
                wait = int(CP_NUDGE_COOLDOWN - (now - last))
                self._cp_detail.configure(
                    text=info["detail"] + "  (下次自动动作 %d 秒后)" % max(0, wait))

        win.after(CP_POLL_MS, self._cp_tick)

    # ------------------------------------------------------------------ 下发动作
    def _cp_nudge(self, op, force=False):
        st = getattr(self, "_cp_state", None)
        if st is None:
            return
        conf = self._cp_settings()
        base = "http://%s:%s" % (conf["host"], conf["port"])
        url = "%s/cgi-bin/action.sh?op=%s&token=%s" % (base, op, conf["token"])
        label = {"reconnect_relay": "重连中继", "relogin": "重新登录校园网"}.get(op, op)

        def worker():
            try:
                opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
                with opener.open(url, timeout=RC_TIMEOUT) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                ok = bool(data.get("ok"))
                msg = data.get("msg") or ("完成" if ok else "失败")
                self.after(0, lambda: self._cp_log("「%s」%s: %s" % (
                    label, "成功" if ok else "未成功", msg)))
            except Exception as exc:
                self.after(0, lambda: self._cp_log("「%s」请求失败: %s" % (label, exc)))

        threading.Thread(target=worker, daemon=True).start()
