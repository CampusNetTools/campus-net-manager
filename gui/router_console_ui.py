# -*- coding: utf-8 -*-
"""「路由器后台工作台」窗口 Mixin (v5.1.0 新增)。

把部署在路由器上的监控工作台 (uhttpd :8088) 融合进管家:

  1. 直接读取路由器控制台的状态接口 (HTTP JSON), 不依赖 SSH / paramiko
  2. 实时展示: 无线中继 / 本机 AP / 校园网认证 / 外网 / 透明代理 / VPN /
     SSH / 防护开关(OTA/MLO) / 系统信息 / 守护日志
  3. 一键操作: 重启透明代理 / 重启 VPN / 重新登录校园网 / 重连中继 /
     重启 WiFi / 重启路由器
  4. 可视化切换中继目标 (换成其它校园网 SSID, 不必再登 SSH)

设计取舍: 只做 HTTP 客户端。路由器侧的工作台 + 守护脚本 (campus-keeper.sh)
负责采集与自愈; 本窗口只做展示与下发指令, 因此路由器不在线时窗口安全性不受影响。
"""
import json
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox
from urllib import request as urlrequest
from urllib.error import URLError
from urllib.parse import urlencode

import keepalive_core as core

from gui.theme import *  # noqa: F401,F403
from gui.scrollkit import fit_geometry  # noqa: F401

# 路由器工作台默认参数 (与 /data/other_vol/console 部署一致)
RC_DEFAULT_HOST = "192.168.31.1"
RC_DEFAULT_PORT = 8088
RC_DEFAULT_TOKEN = "12345678"
RC_TIMEOUT = 12


class RouterConsoleMixin:
    """「路由器后台工作台」窗口。"""

    # ------------------------------------------------------------------ 配置
    def _rc_settings(self):
        """读取路由器工作台连接参数 (config.json -> router_console)。"""
        try:
            cfg = core.load_config()
        except Exception:
            cfg = {}
        section = cfg.get("router_console") or {}
        return {
            "host": section.get("host") or RC_DEFAULT_HOST,
            "port": str(section.get("port") or RC_DEFAULT_PORT),
            "token": section.get("token") or RC_DEFAULT_TOKEN,
        }

    def _rc_save_settings(self, host, port, token):
        try:
            cfg = core.load_config()
            cfg["router_console"] = {"host": host, "port": str(port), "token": token}
            core.save_config(cfg)
            return True
        except Exception as exc:
            self._log("保存路由器工作台参数失败: %s" % exc)
            return False

    # ------------------------------------------------------------------ 窗口
    def show_router_console_window(self):
        """打开「路由器后台工作台」窗口 (已打开则聚焦)。"""
        existing = getattr(self, "_rc_window", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                self._rc_refresh()
                return
        except Exception:
            pass

        conf = self._rc_settings()
        win = tk.Toplevel(self)
        self._rc_window = win
        win.title("路由器后台工作台")
        win.configure(bg=BG)
        win.geometry("880x700")          # 占位尺寸, 构建完成后按内容自适应
        win.minsize(720, 520)            # 允许缩放到的最小可用尺寸
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 20))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text="路由器后台工作台", style="DialogTitle.TLabel").grid(
            row=0, column=0, sticky="w")
        lbl_sub = ttk.Label(
            card,
            text="读取路由器上部署的监控工作台: 中继 / 认证 / 透明代理 / VPN / 防护 / 日志, 并可一键操作。",
            style="Muted.TLabel", wraplength=780)
        lbl_sub.grid(row=1, column=0, sticky="w", pady=(6, 12))

        # ---------- 连接参数行 ----------
        bar = ttk.Frame(card, style="Card.TFrame")
        bar.grid(row=2, column=0, sticky="ew")
        for col in (1, 3, 5):
            bar.columnconfigure(col, weight=1 if col == 1 else 0)

        ttk.Label(bar, text="路由器", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        ent_host = ttk.Entry(bar, width=16)
        ent_host.grid(row=0, column=1, sticky="w", padx=(8, 4))
        ent_host.insert(0, conf["host"])
        ttk.Label(bar, text=":", style="Field.TLabel").grid(row=0, column=2, sticky="w")
        ent_port = ttk.Entry(bar, width=7)
        ent_port.grid(row=0, column=3, sticky="w", padx=(4, 12))
        ent_port.insert(0, conf["port"])
        ttk.Label(bar, text="令牌", style="Field.TLabel").grid(row=0, column=4, sticky="w")
        ent_token = ttk.Entry(bar, width=12, show="●")
        ent_token.grid(row=0, column=5, sticky="w", padx=(8, 12))
        ent_token.insert(0, conf["token"])
        ttk.Button(bar, text="保存", style="Gray.TButton",
                   command=lambda: self._rc_do_save(ent_host, ent_port, ent_token)).grid(
            row=0, column=6, padx=(0, 6))
        ttk.Button(bar, text="刷新", command=self._rc_refresh).grid(row=0, column=7, padx=(0, 6))
        ttk.Button(bar, text="网页版", style="Gray.TButton",
                   command=lambda: self._rc_open_browser(ent_host, ent_port)).grid(
            row=0, column=8)

        # ---------- 状态总览 ----------
        self._rc_head = ttk.Label(card, text="正在读取…", style="Muted.TLabel", wraplength=780)
        self._rc_head.grid(row=3, column=0, sticky="w", pady=(12, 6))

        box = tk.Text(card, height=15, width=1, bg="#09101c", fg="#b7c4d8",
                      font=("PingFang SC", 10), relief="flat", wrap="word",
                      padx=12, pady=10, state="disabled")
        box.grid(row=4, column=0, sticky="nsew", pady=(0, 10))
        self._rc_box = box

        # ---------- 一键操作 ----------
        ttk.Label(card, text="一键操作", style="Field.TLabel").grid(
            row=5, column=0, sticky="w", pady=(4, 4))
        acts = ttk.Frame(card, style="Card.TFrame")
        acts.grid(row=6, column=0, sticky="ew")
        for i in range(3):
            acts.columnconfigure(i, weight=1, uniform="rcact")
        buttons = [
            ("重启透明代理", "restart_proxy", False),
            ("重启 VPN", "restart_vpn", False),
            ("重新登录校园网", "relogin", False),
            ("重连中继", "reconnect_relay", False),
            ("重启 WiFi", "restart_ap", True),
            ("重启路由器", "restart_router", True),
        ]
        for idx, (text, op, danger) in enumerate(buttons):
            ttk.Button(acts, text=text, style="Gray.TButton",
                       command=lambda o=op, d=danger: self._rc_action(o, confirm=d)).grid(
                row=idx // 3, column=idx % 3, sticky="ew", padx=(0, 6), pady=(0, 6))

        # ---------- 切换中继目标 ----------
        ttk.Label(card, text="切换中继目标 (换成其它校园网 / WiFi)", style="Field.TLabel").grid(
            row=7, column=0, sticky="w", pady=(6, 4))
        sw = ttk.Frame(card, style="Card.TFrame")
        sw.grid(row=8, column=0, sticky="ew")
        sw.columnconfigure(1, weight=1)
        sw.columnconfigure(3, weight=1)
        ttk.Label(sw, text="SSID", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        ent_ssid = ttk.Entry(sw)
        ent_ssid.grid(row=0, column=1, sticky="ew", padx=(8, 10))
        ttk.Label(sw, text="密码", style="Field.TLabel").grid(row=0, column=2, sticky="w")
        ent_pass = ttk.Entry(sw, show="●")
        ent_pass.grid(row=0, column=3, sticky="ew", padx=(8, 10))
        ttk.Button(sw, text="切换", style="Gray.TButton",
                   command=lambda: self._rc_switch_relay(ent_ssid, ent_pass)).grid(
            row=0, column=4)
        lbl_hint = ttk.Label(
            card,
            text="提示: 切换后约 1 分钟生效; 校园网通常还需要重新登录认证 (可用上面的「重新登录校园网」)。",
            style="Muted.TLabel", wraplength=780)
        lbl_hint.grid(row=9, column=0, sticky="w", pady=(6, 6))

        # ---------- 守护日志 ----------
        ttk.Label(card, text="守护日志 (最近 30 行)", style="Field.TLabel").grid(
            row=10, column=0, sticky="w", pady=(4, 4))
        logbox = tk.Text(card, height=7, width=1, bg="#09101c", fg="#9fb0c8",
                         font=("PingFang SC", 9), relief="flat", wrap="none",
                         padx=10, pady=8, state="disabled")
        logbox.grid(row=11, column=0, sticky="nsew")
        card.rowconfigure(11, weight=1)
        self._rc_logbox = logbox

        win.protocol("WM_DELETE_WINDOW", lambda: (setattr(self, "_rc_window", None), win.destroy()))

        # 说明文字随窗口宽度自动换行 (不再写死 780)
        wrap_labels = [lbl_sub, self._rc_head, lbl_hint]

        def _rc_on_resize(_event=None):
            try:
                wpx = win.winfo_width() - 96
                if wpx > 260:
                    for lb in wrap_labels:
                        lb.configure(wraplength=wpx)
            except Exception:
                pass

        win.bind("<Configure>", _rc_on_resize)
        # 按内容自适应窗口尺寸 (避免留白 / 裁切)
        win.after(80, lambda: self._rc_autosize(win))
        self._rc_refresh()

    def _rc_autosize(self, win):
        """按内容贴合窗口尺寸: 宽高都跟随内容需求(不留白、不裁切), 夹在屏幕内并居中。

        宽高都取"内容请求值"而不是写死像素, 这样在高分屏缩放(字体更大)下也不会裁切。
        """
        try:
            win.update_idletasks()
            screen_w = win.winfo_screenwidth()
            screen_h = win.winfo_screenheight()
            need_w = win.winfo_reqwidth() + 6
            need_h = win.winfo_reqheight() + 6
            w = max(760, min(need_w, screen_w - 120))
            h = max(520, min(need_h, screen_h - 110))
            x = max(0, (screen_w - w) // 2)
            y = max(0, (screen_h - h) // 3)
            win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        except Exception:
            pass

    # ------------------------------------------------------------------ 内部
    def _rc_base(self, host, port):
        return "http://%s:%s" % (host, port)

    def _rc_do_save(self, ent_host, ent_port, ent_token):
        ok = self._rc_save_settings(ent_host.get().strip(), ent_port.get().strip(),
                                    ent_token.get().strip())
        self._rc_set_head("参数已保存" if ok else "参数保存失败", ok)
        self._rc_refresh()

    def _rc_open_browser(self, ent_host, ent_port):
        url = self._rc_base(ent_host.get().strip(), ent_port.get().strip()) + "/"
        try:
            webbrowser.open(url)
        except Exception as exc:
            messagebox.showwarning("打开失败", str(exc))

    def _rc_set_head(self, text, ok=None):
        try:
            if not self._rc_head.winfo_exists():
                return
        except Exception:
            return
        self._rc_head.configure(text=text)
        try:
            if ok is True:
                self._rc_head.configure(foreground=OK_COLOR if "OK_COLOR" in globals() else "#31c48d")
            elif ok is False:
                self._rc_head.configure(foreground="#ef5960")
            else:
                self._rc_head.configure(foreground=MUTED if "MUTED" in globals() else "#8b93a1")
        except Exception:
            pass

    def _rc_fill_box(self, text):
        try:
            box = self._rc_box
            if not box.winfo_exists():
                return
        except Exception:
            return
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _rc_fill_log(self, text):
        try:
            box = self._rc_logbox
            if not box.winfo_exists():
                return
        except Exception:
            return
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _rc_refresh(self):
        conf = self._rc_settings()
        # 窗口里可能被用户改过, 优先用窗口内的值
        try:
            if self._rc_window is not None and self._rc_window.winfo_exists():
                conf = {"host": conf["host"], "port": conf["port"], "token": conf["token"]}
        except Exception:
            pass
        base = self._rc_base(conf["host"], conf["port"])
        self._rc_set_head("正在读取 %s …" % base, None)

        def worker():
            try:
                with urlrequest.urlopen(base + "/cgi-bin/status.sh", timeout=RC_TIMEOUT) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                self.after(0, lambda: self._rc_render(data))
            except URLError as exc:
                self.after(0, lambda: self._rc_fail("无法连接路由器工作台: %s" % exc))
            except Exception as exc:
                self.after(0, lambda: self._rc_fail("读取失败: %s" % exc))

        threading.Thread(target=worker, daemon=True).start()

    def _rc_fail(self, msg):
        self._rc_set_head(msg + " (确认路由器已开机、工作台端口 %s 正常)" % RC_DEFAULT_PORT, False)
        self._rc_fill_box("未获取到路由器状态。\n\n可能原因:\n"
                          "  1) 路由器未通电 / 不在本机同一网段\n"
                          "  2) 路由器上的工作台 (uhttpd :%s) 未启动\n"
                          "  3) 端口填错\n\n"
                          "可在路由器上执行: start-stop-daemon -S -b -x /usr/sbin/uhttpd -- -p %s -h /data/other_vol/console"
                          % (RC_DEFAULT_PORT, RC_DEFAULT_PORT))
        self._rc_fill_log("")

    def _rc_render(self, d):
        relay = d.get("relay", {}) or {}
        ap = d.get("ap", {}) or {}
        proxy = d.get("proxy", {}) or {}
        vpn = d.get("vpn", {}) or {}
        ssh = d.get("ssh", {}) or {}
        sysd = d.get("sys", {}) or {}
        guard = d.get("guard", {}) or {}

        auth = d.get("auth", "-")
        net = d.get("net", "-")
        auth_ok = "在线" in auth
        net_ok = "正常" in net
        self._rc_set_head(
            "校园网认证: %s   |   外网: %s   |   中继信号: %s dBm   |   %s"
            % (auth, net, relay.get("signal", "-"), sysd.get("uptime", "")),
            auth_ok and net_ok)

        def onoff(v, good_when_zero=True):
            try:
                n = int(v)
            except Exception:
                return "-"
            good = (n == 0) if good_when_zero else (n > 0)
            return "[正常]" if good else "[注意]"

        lines = []
        lines.append("── 无线中继 (上游校园网) ──────────────────────────────")
        lines.append("  目标 SSID : %s" % relay.get("ssid", "-"))
        lines.append("  信号强度 : %s dBm     上游 BSSID: %s"
                     % (relay.get("signal", "-"), relay.get("bssid", "-")))
        lines.append("  本机 IP  : %s" % relay.get("ip", "-"))
        lines.append("")
        lines.append("── 本机 WiFi / 认证 ────────────────────────────────")
        lines.append("  AP SSID  : %s     信道: %s" % (ap.get("ssid", "-"), ap.get("channel", "-")))
        lines.append("  校园网认证: %s     外网: %s" % (auth, net))
        lines.append("")
        lines.append("── 透明代理 (mihomo) ──────────────────────────────")
        lines.append("  进程: %s 个    混合端口 7890: %s    透明端口 7891: %s    面板 9091: %s"
                     % (proxy.get("proc", "0"), proxy.get("p7890", "0"),
                        proxy.get("p7891", "0"), proxy.get("panel", "0")))
        lines.append("  节点: %s" % proxy.get("nodes", "-"))
        lines.append("")
        lines.append("── VPN (L2TP/IPSec) ──────────────────────────────")
        lines.append("  xl2tpd: %s    IPSec(pluto): %s    UDP 500: %s"
                     % (vpn.get("xl2tpd", "0"), vpn.get("ipsec", "0"), vpn.get("udp500", "0")))
        lines.append("")
        lines.append("── 远程访问 / 防护 ────────────────────────────────")
        lines.append("  SSH(dropbear): %s" % ssh.get("dropbear", "0"))
        lines.append("  自动固件下载(OTA): %s %s       MLO: %s %s"
                     % (guard.get("ota_auto", "-"), onoff(guard.get("ota_auto", "-")),
                        guard.get("mlo_support", "-"), onoff(guard.get("mlo_support", "-"))))
        lines.append("")
        mem_used = sysd.get("mem_used", "0")
        mem_total = sysd.get("mem_total", "0")
        try:
            mem_txt = "%dMB / %dMB" % (int(mem_used) // 1024, int(mem_total) // 1024)
        except Exception:
            mem_txt = "%s / %s KB" % (mem_used, mem_total)
        lines.append("── 系统 ────────────────────────────────────────")
        lines.append("  型号 / 固件: %s / %s    运行时长: %s    负载: %s    内存: %s"
                     % (sysd.get("model", "-"), sysd.get("rom", "-"),
                        sysd.get("uptime", "-"), sysd.get("load", "-"), mem_txt))
        self._rc_fill_box("\n".join(lines))

        log_text = (d.get("log", "") or "").replace("~", "\n")
        self._rc_fill_log(log_text or "(暂无日志)")

    def _rc_action(self, op, confirm=False):
        labels = {
            "restart_proxy": "重启透明代理", "restart_vpn": "重启 VPN",
            "relogin": "重新登录校园网", "reconnect_relay": "重连中继",
            "restart_ap": "重启 WiFi", "restart_router": "重启路由器",
        }
        title = labels.get(op, op)
        if confirm and not messagebox.askyesno("确认操作", "确定要执行「%s」吗？\n可能造成短暂断网。" % title):
            return
        conf = self._rc_settings()
        url = "%s/cgi-bin/action.sh?%s" % (
            self._rc_base(conf["host"], conf["port"]),
            urlencode({"op": op, "token": conf["token"]}))
        self._rc_set_head("正在执行「%s」…" % title, None)

        def worker():
            try:
                with urlrequest.urlopen(url, timeout=RC_TIMEOUT) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                msg = data.get("msg") or ("完成" if data.get("ok") else "失败")
                self.after(0, lambda: self._rc_set_head("「%s」: %s" % (title, msg), bool(data.get("ok"))))
                self.after(2000, self._rc_refresh)
            except Exception as exc:
                self.after(0, lambda: self._rc_set_head("「%s」执行失败: %s" % (title, exc), False))

        threading.Thread(target=worker, daemon=True).start()

    def _rc_switch_relay(self, ent_ssid, ent_pass):
        ssid = ent_ssid.get().strip()
        password = ent_pass.get()
        if not ssid:
            messagebox.showwarning("缺少 SSID", "请填写要连接的 WiFi 名称 (SSID)。")
            return
        if not messagebox.askyesno("确认切换中继",
                                   "确定把中继切换到「%s」吗？\n切换期间路由器会短暂断网 (约 1 分钟)。" % ssid):
            return
        conf = self._rc_settings()
        url = "%s/cgi-bin/action.sh?%s" % (
            self._rc_base(conf["host"], conf["port"]),
            urlencode({"op": "switch_relay", "token": conf["token"],
                       "ssid": ssid, "pass": password}))
        self._rc_set_head("正在切换中继到「%s」…" % ssid, None)

        def worker():
            try:
                with urlrequest.urlopen(url, timeout=RC_TIMEOUT) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                msg = data.get("msg") or "已提交"
                self.after(0, lambda: self._rc_set_head(msg, bool(data.get("ok"))))
                self.after(60000, self._rc_refresh)
            except Exception as exc:
                self.after(0, lambda: self._rc_set_head("切换失败: %s" % exc, False))

        threading.Thread(target=worker, daemon=True).start()
