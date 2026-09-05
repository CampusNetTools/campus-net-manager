# -*- coding: utf-8 -*-
"""守护控制与状态栏 Mixin (自 app_gui.py 拆分)"""
import os  # noqa: F401
import queue  # noqa: F401
import threading  # noqa: F401
import webbrowser  # noqa: F401
import tkinter as tk  # noqa: F401
from tkinter import ttk, messagebox, filedialog  # noqa: F401

import keepalive_core as core  # noqa: F401
import shared_proxy  # noqa: F401
from PIL import Image, ImageDraw, ImageTk  # noqa: F401

from gui.theme import *  # noqa: F401,F403

try:
    import pystray  # noqa: F401
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

try:
    import qrcode  # noqa: F401
    HAS_QR = True
except Exception:
    HAS_QR = False


class DaemonCtlMixin:
    def set_guard(self, running):
        self._guard_want = running
        self.lbl_guard.configure(text="守护: 运行中" if running else "守护: 未运行")
        self.dot_guard.configure(fg=GREEN if running else MUTED)
        self.btn_guard.configure(text="停止守护" if running else "启动守护",
                                 style="Danger.TButton" if running else "Green.TButton")


    def set_net(self, paths, authed, last_check, in_campus=None, user_any_network=False):
        if last_check:
            self.lbl_last.configure(text="上次检测: %s" % last_check)
        vpn = paths.get("vpn", False)
        current = paths.get("current", False)
        physical = paths.get("physical", current)
        self._last_authed = bool(authed)
        self._last_internet = bool(physical if (vpn and core.IS_MACOS) else current)
        # 用户选了「任意网络使用」且明确不在校园网: 显示 WiFi 连接正常(绿点), 不展示校园网相关状态。
        if user_any_network and in_campus is False:
            self.dot_net.configure(fg=GREEN)
            self.lbl_net.configure(text="网络: WiFi 连接正常")
            return
        if authed and physical and current:
            self.dot_net.configure(fg=GREEN)
            self.lbl_net.configure(text="网络: VPN 与校园网在线" if vpn else "网络: 在线正常")
        elif authed and physical and vpn:
            self.dot_net.configure(fg=YELLOW)
            self.lbl_net.configure(text="网络: 校园网在线 (VPN异常)")
        elif authed:
            self.dot_net.configure(fg=YELLOW)
            self.lbl_net.configure(text="网络: 校园网出口异常")
        elif vpn and current:
            self.dot_net.configure(fg=YELLOW)
            self.lbl_net.configure(text="网络: VPN在线 (校园认证掉线)")
        else:
            self.dot_net.configure(fg=RED)
            self.lbl_net.configure(text="网络: 已掉线")


    def set_env(self, mode, ssid, gw, profile_name, in_campus):
        if in_campus is None:
            return
        conn = (" (" + ssid + ")" if ssid else ("" if not in_campus else (" (有线/网关 %s)" % gw if gw else "")))
        if in_campus:
            self.dot_env.configure(fg=GREEN)
            extra = " → 档案「%s」" % profile_name if profile_name else " (未匹配档案)"
            self.lbl_env.configure(text="环境: 校园网%s%s" % (conn, extra))
        else:
            self.dot_env.configure(fg=MUTED)
            self.lbl_env.configure(text="环境: 非校园网环境 守护休眠")


    def _on_log(self, line):
        self.log_q.put(line)


    def _on_status(self, paths, authed, last_check, in_campus=None, user_any_network=False):
        self.after(0, self.set_net, paths, authed, last_check, in_campus, user_any_network)


    def _on_env(self, mode, ssid, gw, profile_name, in_campus):
        self.after(0, self.set_env, mode, ssid, gw, profile_name, in_campus)

    # ---------- 动作 ----------

    def start_daemon(self, silent=False):
        if self.daemon and self.daemon.is_alive():
            return
        if not core.acquire_lock():
            messagebox.showwarning("已有实例", "检测到已有守护实例在运行。\n请先关闭它，或重启电脑后重试。")
            return
        self.cfg = core.load_config()
        if not any(p.get("username") and p.get("password") for p in self.cfg.get("profiles", [])):
            messagebox.showwarning("未配置", "请先在档案中填写账号密码并保存")
            core.release_lock()
            return
        self.daemon = core.KeepAliveDaemon(self.cfg, on_log=self._on_log, on_status=self._on_status,
                                           on_env=self._on_env, on_alert=self._on_alert)
        self.daemon.start()
        # 按偏好实例保持唤醒(合盖不睡眠); 失败仅记录不阻断守护
        if self.cfg.get("keep_awake"):
            if core.keep_awake_start():
                self._log("已开启合盖/休眠保持运行 (caffeinate)")
            else:
                self._log("警告: 合盖保持运行启动失败")
        self.set_guard(True)
        if not silent:
            self._log("守护启动 (GUI)")


    def toggle_daemon(self):
        """单按钮切换守护状态。"""
        if self.daemon and self.daemon.is_alive():
            self.stop_daemon()
        else:
            self.start_daemon()


    def export_diag(self):
        """诊断导出: 先选择保存位置，再生成网络状态/脱敏档案/日志。"""
        import datetime
        default_name = "校园网连接管家诊断_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filedialog.asksaveasfilename(
            title="保存诊断报告",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("文本报告", "*.txt"), ("所有文件", "*.*")])
        if not fname:
            return

        def _do():
            try:
                text = core.collect_diagnostics()
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(text)
                try:
                    self.clipboard_clear()
                    self.clipboard_append(text)
                except Exception:
                    pass
                def done():
                    self._log("诊断报告已保存: %s" % fname)
                    messagebox.showinfo("诊断完成",
                                        "诊断报告已保存到：\n%s\n\n内容也已复制到剪贴板，可直接粘贴发给技术人员。" % fname)
                self.after(0, done)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("诊断失败", str(e)))
        threading.Thread(target=_do, daemon=True).start()


    def _on_alert(self, text, category="failure"):
        """守护告警 → 托盘通知 (守护线程调用, 线程安全)"""
        def _notify():
            if not core.notification_enabled(self.cfg, category):
                return
            if core.send_system_notification(text):
                return
            if HAS_TRAY and getattr(self, "_tray", None):
                try:
                    self._tray.notify(text, "校园网连接管家")
                    return
                except Exception:
                    pass
            self._log("通知: " + text)
        try:
            self.after(0, _notify)
        except Exception:
            pass


    def _watchdog(self):
        """守护看门狗: 守护线程意外退出时自动重启"""
        try:
            want = getattr(self, "_guard_want", False)
            if want and self.daemon and not self.daemon.is_alive():
                self._log("检测到守护异常退出, 自动重启...")
                self.daemon = None
                self.set_guard(False)
                try:
                    core.release_lock()
                except Exception:
                    pass
                self.start_daemon(silent=True)
        except Exception:
            pass
        self.after(3000, self._watchdog)


    def stop_daemon(self):
        if self.daemon and self.daemon.is_alive():
            self.daemon.stop()
            self.daemon = None
        # 合盖保活与守护解耦: 仅当偏好关闭时才停 caffeinate
        if not self.cfg.get("keep_awake"):
            core.keep_awake_stop()
        core.release_lock()
        self.set_guard(False)
        self.dot_net.configure(fg=MUTED)
        self.lbl_net.configure(text="网络: 已停止检测")


    def check_now(self):
        threading.Thread(target=self._do_check, daemon=True).start()


    def detect_auth(self):
        known = [self.cmb_auth.get().strip(), core.DEFAULT_AUTH_URL]
        known.extend(self.cfg.get("auth_history") or [])
        known.extend(p.get("auth_url", "") for p in self.cfg.get("profiles", []))
        self.btn_detect.configure(text="探测中...", state="disabled")
        threading.Thread(target=self._do_detect, args=(known,), daemon=True).start()


    def _do_detect(self, known_urls):
        try:
            report = core.discover_auth_servers(known_urls)
        except Exception as e:
            report = {"candidates": [], "online": False}
            err = str(e)
            self.after(0, lambda: self._log("探测异常: %s" % err))
        def done():
            self.btn_detect.configure(text="探测", state="normal")
            candidates = report.get("candidates") or []
            if candidates:
                urls = [item["url"] for item in candidates]
                existing = list(self.cmb_auth.cget("values"))
                merged = list(dict.fromkeys(urls + existing))[:15]
                self.cmb_auth.configure(values=merged)
                self.cmb_auth.set(urls[0])
                history = list(dict.fromkeys(urls + (self.cfg.get("auth_history") or [])))[:15]
                self.cfg["auth_history"] = history
                core.save_config(self.cfg)
                for item in candidates:
                    self._log("发现认证服务器: %s（%s，可信度 %d）" % (
                        item["url"], item["source"], item["confidence"]))
                if len(candidates) > 1:
                    messagebox.showinfo(
                        "发现多个认证服务器",
                        "共发现 %d 个候选地址，已选择可信度最高的一项。\n\n%s\n\n"
                        "其他地址已加入认证服务器下拉框，可以直接切换。" % (
                            len(candidates), "\n".join("• %s（%s）" % (i["url"], i["source"])
                                                       for i in candidates)))
                elif report.get("online"):
                    messagebox.showinfo(
                        "探测完成",
                        "当前已经联网，但仍通过认证页特征验证到：\n%s\n\n"
                        "因此不需要先断开校园网认证。" % urls[0])
            else:
                messagebox.showwarning(
                    "未探测到认证服务器",
                    ("多个 HTTP/204 探针均显示当前网络已经联网，但没有识别出认证页特征。\n\n"
                     "请保留已有地址，或在未认证状态下重新探测。"
                     if report.get("online") else
                     "没有从多组 HTTP/204 探针、重定向、认证页特征和历史地址中发现认证服务器。\n\n"
                     "请确认已连接校园网，或手动输入一次真实认证页地址。"))
        self.after(0, done)


    def _do_check(self):
        self._log("[%s] 手动检测..." % core.now_str())
        mode, ssid = core.get_connection_mode()
        gw = core.get_gateway()
        profile = core.match_profile(self.cfg, ssid, gw)
        auth_url = profile.get("auth_url", core.DEFAULT_AUTH_URL) if profile else core.DEFAULT_AUTH_URL
        in_campus = core.auth_reachable(auth_url)
        self._on_env(mode, ssid, gw, profile["name"] if profile else None, in_campus)
        if not in_campus:
            self._log("结果: 非校园网环境, 不进行登录")
            return
        if profile is None:
            self._log("结果: 校园网环境但未配置档案")
            return
        authed = core.check_auth(auth_url)
        paths = core.check_network_paths()
        campus_internet = paths["physical"] if paths["vpn"] and core.IS_MACOS else paths["current"]
        self._on_status(paths, authed, core.now_str())
        if authed and campus_internet:
            if paths["vpn"] and not paths["current"]:
                self._log("结果: 校园网在线，VPN/系统路径异常")
            elif paths["vpn"]:
                self._log("结果: VPN 与校园网均在线")
            else:
                self._log("结果: 在线正常")
        elif authed:
            self._log("结果: 校园网认证在线，但物理出口异常")
        else:
            self._log("结果: 未登录/掉线")


    def _refresh_env(self):
        def work():
            mode, ssid = core.get_connection_mode()
            gw = core.get_gateway()
            profile = core.match_profile(self.cfg, ssid, gw)
            auth_url = profile.get("auth_url", core.DEFAULT_AUTH_URL) if profile else core.DEFAULT_AUTH_URL
            in_campus = core.auth_reachable(auth_url)
            self._on_env(mode, ssid, gw, profile["name"] if profile else None, in_campus)
        threading.Thread(target=work, daemon=True).start()


    def _auto_start(self):
        try:
            self.cfg = core.load_config()
            if not any(p.get("username") and p.get("password") for p in self.cfg.get("profiles", [])):
                self._restore_preferences()
                self.after(800, self.show_wizard)
                return
            self._restore_preferences()
            if core.acquire_lock():
                core.release_lock()
                self.start_daemon(silent=True)
        except Exception:
            pass
        self.after(5000, self._startup_update_check)



