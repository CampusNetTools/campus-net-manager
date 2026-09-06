# -*- coding: utf-8 -*-
"""偏好设置/自启/导入导出 Mixin (自 app_gui.py 拆分)"""
import os  # noqa: F401
import queue  # noqa: F401
import threading  # noqa: F401
import webbrowser  # noqa: F401
import tkinter as tk  # noqa: F401
from tkinter import ttk, messagebox, filedialog  # noqa: F401

import keepalive_core as core  # noqa: F401
from core import history  # noqa: F401
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


class PreferencesMixin:
    def _update_auto_btn(self):
        on = self.var_auto.get()
        self.btn_auto.configure(text="开机自启：开启" if on else "开机自启：关闭",
                                style="AutoOn.TButton" if on else "AutoOff.TButton")


    def _toggle_autostart(self):
        previous = self.var_auto.get()
        target = not previous
        ok = core.set_autostart(target)
        if not ok:
            self.var_auto.set(previous)
            messagebox.showerror("失败", "修改开机自启失败（可能需要权限）")
        else:
            self.var_auto.set(target)
            self._log("开机自启: %s" % ("已开启" if target else "已关闭"))
        self._update_auto_btn()


    def export_config(self):
        path = filedialog.asksaveasfilename(
            title="导出配置", defaultextension=".json",
            initialfile="校园网连接管家配置.json",
            filetypes=[("JSON 配置", "*.json")])
        if not path:
            return
        try:
            import json
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(core.config_for_export(self.cfg), handle, ensure_ascii=False, indent=2)
            messagebox.showinfo("已导出", "配置已导出到：\n%s\n\n为保护账号安全，导出文件不包含密码。" % path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))


    def import_config(self):
        path = filedialog.askopenfilename(
            title="导入配置", filetypes=[("JSON 配置", "*.json")])
        if not path:
            return
        try:
            import json
            with open(path, "r", encoding="utf-8") as handle:
                imported = json.load(handle)
            for profile in imported.get("profiles", []):
                profile.pop("secret_id", None)
                profile.pop("password_store", None)
            core.ensure_lida_profile(imported)
            core.ensure_preferences(imported)
            core.save_config(imported, sync_secrets=True)
            self.cfg = core.load_config()
            self._refresh_profile_list()
            self._load_form_from_current()
            self._log("配置已导入: %s" % path)
            messagebox.showinfo("已导入", "配置导入成功。\n未包含密码的档案需要重新填写密码；重启守护后生效。")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))


    def show_preferences(self):
        """网络记录/系统通知/软件更新集中设置, 不再单独开更新窗口。"""
        core.ensure_preferences(self.cfg)
        # 启动后立刻把 cfg 的 history_log_path 同步到 history 模块, 让 reader 也用新路径
        self._sync_history_log_path()

        win = tk.Toplevel(self)
        win.title("偏好设置")
        win.configure(bg=BG)
        win.geometry("680x800")
        win.resizable(False, True)
        win.minsize(640, 660)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(26, 24))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        # 保存 card 引用供内联「立即更新」按钮挂靠
        self._pref_card = card
        ttk.Label(card, text="偏好设置", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="只记录连接状态，不记录浏览内容、账号或密码。",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 14))
        ttk.Label(card, text="绿色对号表示已选择；点击“保存设置”后正式生效。",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        var_history = tk.BooleanVar(value=self.cfg.get("history_enabled", False))
        var_keep_awake = tk.BooleanVar(value=self.cfg.get("keep_awake", False))
        var_kick_guard = tk.BooleanVar(value=self.cfg.get("kick_guard", True))
        var_auto_update = tk.BooleanVar(value=self.cfg.get("auto_update_check", True))
        notifications = self.cfg.get("notifications", {})
        var_notify = tk.BooleanVar(value=notifications.get("enabled", True))
        category_vars = {
            "disconnect": tk.BooleanVar(value=notifications.get("disconnect", True)),
            "recovery": tk.BooleanVar(value=notifications.get("recovery", True)),
            "failure": tk.BooleanVar(value=notifications.get("failure", True)),
            "device": tk.BooleanVar(value=notifications.get("device", True)),
        }
        # 历史存储: 单选行 (checkbox + 路径标签 + 改路径按钮)
        history_row = ttk.Frame(card, style="Inner.TFrame")
        history_row.pack(fill="x", anchor="w")
        chk_history = ttk.Checkbutton(history_row, text="保存网络稳定性历史",
                                       variable=var_history, style="Checkmark.TCheckbutton")
        chk_history.pack(side="left")
        self._lbl_history_path = ttk.Label(history_row, text="",
                                            style="Muted.TLabel", wraplength=320,
                                            justify="left")
        self._lbl_history_path.pack(side="left", padx=(8, 0))
        self._btn_history_change = ttk.Button(history_row, text="更改", style="Quiet.TButton")
        self._btn_history_change.pack(side="left", padx=(6, 0))

        def _refresh_history_path_label():
            path = (self.cfg.get("history_log_path") or "").strip()
            enabled = bool(var_history.get())
            if enabled and path:
                self._lbl_history_path.configure(text="  → " + path)
            elif enabled:
                self._lbl_history_path.configure(text="  → 默认 (应用数据目录)")
            else:
                self._lbl_history_path.configure(text="")
            self._btn_history_change.configure(state="normal" if enabled else "disabled")

        def _pick_history_path():
            """弹文件对话框让用户选择保存位置; 取消则保持 var_history 不变。"""
            initial = (self.cfg.get("history_log_path") or "").strip() \
                      or os.path.join(os.path.expanduser("~"), "Downloads",
                                      "campus_net_history.jsonl")
            if not initial.endswith(".jsonl"):
                initial = os.path.join(initial, "campus_net_history.jsonl")
            path = filedialog.asksaveasfilename(
                title="选择网络稳定性历史保存位置",
                defaultextension=".jsonl",
                initialfile=os.path.basename(initial),
                initialdir=os.path.dirname(initial) or os.path.expanduser("~"),
                filetypes=[("稳定性历史 (*.jsonl)", "*.jsonl"),
                           ("文本文件 (*.txt)", "*.txt"),
                           ("所有文件", "*.*")])
            if not path:
                return
            self.cfg["history_log_path"] = path
            history.set_log_path(path)
            # 给一个空事件, 让文件存在 + 用户马上能看到
            history.record_network_history(
                self.cfg, "online", "稳定性历史已启用",
                at_path=path, by=os.environ.get("USER", "user"))
            _refresh_history_path_label()
            self._log("网络稳定性历史保存位置: %s" % path)

        def _on_history_toggle():
            """勾选时立刻弹保存对话框; 取消则在弹窗时回滚勾选; 同时刷新网络报告段。"""
            if not var_history.get():
                # 取消勾选 -> 报告段回到"需先开启"灰显提示
                if hasattr(self, "_refresh_report_status"):
                    self._refresh_report_status()
                return
            # 勾选 -> 询问保存位置(取消则回滚为 False)
            previous_path = self.cfg.get("history_log_path", "")
            _pick_history_path()
            if not (self.cfg.get("history_log_path") or "").strip():
                # 用户在对话框点了取消 -> 回滚勾选
                var_history.set(False)
                self.cfg["history_log_path"] = previous_path
            _refresh_history_path_label()
            if hasattr(self, "_refresh_report_status"):
                self._refresh_report_status()

        chk_history.configure(command=_on_history_toggle)
        self._btn_history_change.configure(command=_pick_history_path)
        _refresh_history_path_label()

        keep_awake_hint = "合盖/系统空闲时继续保活（需 macOS，用 caffeinate 防止睡眠）" if core.IS_MACOS else "合盖/系统睡眠时继续保活（当前平台仅部分支持）"
        ttk.Checkbutton(card, text="合盖/休眠时保持运行", variable=var_keep_awake,
                        style="Checkmark.TCheckbutton").pack(anchor="w", pady=(8, 0))
        ttk.Label(card, text=keep_awake_hint, style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(card, text="防踢保活（名额满时优先保住本机，不让新设备挤掉）",
                        variable=var_kick_guard, style="Checkmark.TCheckbutton").pack(anchor="w")
        ttk.Label(card, text="周期性刷新登录会话，让本机/路由器保持最新，第 3 台设备登录时被挤掉的是别人",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Checkbutton(card, text="启动时自动检查新版本（GitHub Release）",
                        variable=var_auto_update, style="Checkmark.TCheckbutton").pack(anchor="w")

        # 软件更新入口(取代独立「软件更新」窗口): 当前版本 + 立即检查 + 内联结果 + 立即更新按钮
        ttk.Label(card, text="软件更新", style="Section.TLabel").pack(anchor="w", pady=(20, 8))
        upd_row = ttk.Frame(card, style="Inner.TFrame")
        upd_row.pack(fill="x")
        platform_tag = "macOS" if core.IS_MACOS else ("Windows" if core.IS_WINDOWS else "Linux")
        ttk.Label(upd_row, text="当前版本 v%s（%s）" % (core.APP_VERSION, platform_tag),
                  style="Card.TLabel").pack(side="left")
        self._btn_pref_check = ttk.Button(upd_row, text="立即检查", style="Accent.TButton",
                                          command=self._pref_check_update)
        self._btn_pref_check.pack(side="right")
        self._lbl_pref_upd = ttk.Label(card, text="点击「立即检查」联网访问 GitHub Release。",
                                       style="Muted.TLabel", wraplength=600, justify="left")
        self._lbl_pref_upd.pack(anchor="w", pady=(8, 0))
        # 立即更新按钮: 有新版本时显示, 没有时隐藏
        self._btn_pref_update_now = None
        self._pref_update_info = None

        ttk.Label(card, text="系统通知", style="Section.TLabel").pack(anchor="w")
        master_notify = ttk.Checkbutton(
            card, text="允许校园网连接管家发送通知", variable=var_notify,
            style="Checkmark.TCheckbutton")
        master_notify.pack(
            anchor="w", pady=(8, 4))
        categories = ttk.Frame(card, style="Inner.TFrame")
        categories.pack(fill="x")
        category_buttons = []
        for index, (key, text) in enumerate((
                ("disconnect", "检测到掉线"), ("recovery", "网络恢复"),
                ("failure", "自动恢复失败"), ("device", "新设备请求共享"))):
            child = ttk.Checkbutton(categories, text=text, variable=category_vars[key],
                                    style="Checkmark.TCheckbutton")
            # 单列纵向排列, 避免长文案被窗口宽度截断
            child.pack(anchor="w", pady=3)
            category_buttons.append(child)

        def sync_notification_children():
            enabled = bool(var_notify.get())
            if not enabled:
                for value in category_vars.values():
                    value.set(False)
            for child in category_buttons:
                child.configure(state="normal" if enabled else "disabled")

        master_notify.configure(command=sync_notification_children)
        sync_notification_children()

        # ---------- 网络报告段（融入偏好设置） ----------
        # history_enabled=False 时整段灰显+提示; 反之刷新报告。
        report_card = ttk.Frame(card, style="Inner.TFrame")
        report_card.pack(fill="both", expand=True, anchor="w", pady=(20, 0))
        report_header = ttk.Frame(report_card, style="Inner.TFrame")
        report_header.pack(fill="x")
        ttk.Label(report_header, text="网络报告", style="Section.TLabel").pack(side="left")
        self._lbl_report_status = ttk.Label(report_header, text="",
                                             style="Muted.TLabel",
                                             wraplength=460, justify="left")
        self._lbl_report_status.pack(side="left", padx=(12, 0))
        report_body = ttk.Frame(report_card, style="Inner.TFrame")
        report_body.pack(fill="both", expand=True, pady=(10, 0))
        self._lbl_report = ttk.Label(report_body, text="", style="Card.TLabel",
                                     wraplength=600, justify="left")
        self._lbl_report.pack(fill="both", expand=True, anchor="nw")
        report_btns = ttk.Frame(report_card, style="Inner.TFrame")
        report_btns.pack(fill="x", pady=(12, 0))
        self._btn_report_refresh = ttk.Button(report_btns, text="刷新报告",
                                              style="Gray.TButton",
                                              command=self._pref_refresh_report)
        self._btn_report_refresh.pack(side="left")
        self._btn_report_export = ttk.Button(report_btns, text="导出诊断",
                                             style="Gray.TButton",
                                             command=self.export_diag)
        self._btn_report_export.pack(side="left", padx=(10, 0))

        # ---------- 诊断与帮助段(融入偏好设置) ----------
        help_card = ttk.Frame(card, style="Inner.TFrame")
        help_card.pack(fill="x", anchor="w", pady=(20, 0))
        ttk.Label(help_card, text="诊断与帮助", style="Section.TLabel").pack(anchor="w")
        ttk.Label(help_card, text="导出诊断 = 脱敏的网络状态/档案/日志, 给技术人员时使用；"
                                  "使用帮助 = 三种上网方式 + 常见问题速查。",
                  style="Muted.TLabel", wraplength=600, justify="left").pack(
            anchor="w", pady=(4, 10))
        help_btns = ttk.Frame(help_card, style="Inner.TFrame")
        help_btns.pack(fill="x")
        ttk.Button(help_btns, text="导出诊断", style="Gray.TButton",
                   command=self.export_diag).pack(side="left")
        ttk.Button(help_btns, text="使用帮助", style="Gray.TButton",
                   command=self.show_help).pack(side="left", padx=(8, 0))

        def refresh_report_status():
            enabled = bool(var_history.get())
            if not enabled:
                self._lbl_report_status.configure(text="（需先开启保存网络稳定性历史）")
                for w in (self._lbl_report, self._btn_report_refresh, self._btn_report_export):
                    try:
                        w.configure(state="disabled")
                    except Exception:
                        pass
                self._lbl_report.configure(
                    text="开启『保存网络稳定性历史』后，软件会在这里用普通人能读懂的方式说明"
                         "最近 7 天的网络稳定性，并列出每次断网的开始 / 恢复 / 持续时长。\n\n"
                         "（提示）即便暂时不开, 你仍可在「主界面宫格 → 网络控制台」"
                         "实时看当前连接状态。")
                return
            self._lbl_report_status.configure(text="最近 7 天 · 仅本地记录")
            for w in (self._lbl_report, self._btn_report_refresh, self._btn_report_export):
                try:
                    w.configure(state="normal")
                except Exception:
                    pass
            self._pref_refresh_report()

        self._refresh_report_status = refresh_report_status

        def save_preferences():
            self.cfg["history_enabled"] = bool(var_history.get())
            self.cfg["history_log_path"] = (self.cfg.get("history_log_path") or "").strip()
            self.cfg["keep_awake"] = bool(var_keep_awake.get())
            self.cfg["kick_guard"] = bool(var_kick_guard.get())
            self.cfg["auto_update_check"] = bool(var_auto_update.get())
            self.cfg["notifications"] = core.normalized_notification_settings(
                bool(var_notify.get()), {key: bool(value.get()) for key, value in category_vars.items()})
            core.save_config(self.cfg)
            # 同步到 history 模块, 让 reader(summarize/analyze_outage_timeline) 也切到新路径
            self._sync_history_log_path()
            # 开关「合盖/休眠保持运行」: 立即启停 caffeinate
            if self.cfg.get("keep_awake"):
                ok = core.keep_awake_start()
            else:
                ok = core.keep_awake_stop() or True
            self._log("偏好设置已保存：网络历史%s，系统通知%s，合盖保持运行%s，防踢保活%s" % (
                "开启" if var_history.get() else "关闭",
                "开启" if var_notify.get() else "关闭",
                "开启" if var_keep_awake.get() else "关闭",
                "开启" if var_kick_guard.get() else "关闭"))
            if self.cfg.get("keep_awake") and not ok:
                self._log("警告: 合盖保持运行启动失败 (可能非 macOS 或 caffeinate 不可用)")
            win.destroy()

        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.pack(fill="x", side="bottom", pady=(20, 0))
        ttk.Button(actions, text="测试通知", style="Gray.TButton",
                   command=lambda: core.send_system_notification("通知设置工作正常")).pack(side="left")
        ttk.Button(actions, text="保存设置", style="Accent.TButton", command=save_preferences).pack(side="right")

        # 首次进入: 按当前 history_enabled 渲染网络报告段
        refresh_report_status()

    # ---------- 系统托盘 ----------

    def _check_update_now(self):
        """偏好设置内联更新检查: 点击即查, 结果写回标签, 发现新版内联给「立即更新」。"""
        self._log("手动检查更新")
        self._set_update_text("正在检查…")

        def on_result(info):
            self.after(0, lambda: self._render_update_result(info))
        self._bg_check_update(manual=True, on_result=on_result)

    def _set_update_text(self, text):
        try:
            self._lbl_update.configure(text=text)
        except Exception:
            pass

    def _render_update_result(self, info):
        if not info:
            self._set_update_text("✓ 已是最新版本 v%s" % core.APP_VERSION)
            # 已有立即更新按钮时收起, 避免状态与按钮语义不符
            btn = getattr(self, "_btn_update_now", None)
            if btn is not None:
                btn.pack_forget()
            return
        self._update_info = info
        self._set_update_text("发现新版本 %s" % info["tag"])
        if getattr(self, "_btn_update_now", None) is None:
            self._btn_update_now = ttk.Button(
                self._upd_line_frame, text="立即更新", style="Accent.TButton",
                command=lambda: self._do_update(self._update_info))
        self._btn_update_now.pack(side="right")

    def _restore_preferences(self):
        """App 启动即恢复独立偏好: 合盖/休眠保持运行不依赖守护是否启动。
        用户在偏好设置开启后, 即使还没配置账号/守护未运行, 合盖保活也生效。"""
        try:
            self.cfg = core.load_config()
            self._sync_history_log_path()
            if self.cfg.get("keep_awake") and not core.keep_awake_enabled():
                if core.keep_awake_start():
                    self._log("已恢复合盖/休眠保持运行 (caffeinate)")
                else:
                    self._log("警告: 合盖保持运行启动失败")
        except Exception:
            pass

    # ---------- 软件更新 (内联入口, 替代独立更新窗口) ----------

    def _sync_history_log_path(self):
        """把 cfg['history_log_path'] 同步到 history 模块, 让 summarize/analyze 也读新路径。"""
        try:
            target = history.effective_log_path(self.cfg)
            history.set_log_path(target)
        except Exception:
            pass

    def _pref_refresh_report(self):
        """偏好设置内联『网络报告』刷新按钮: 同步 history 路径后, 重读摘要 + 断网时间线。

        history_enabled=False 时调用刷新也无害(显示提示文案)。"""
        try:
            self._sync_history_log_path()
            data = core.summarize_network_history(7)
            c = data["counts"]
            stable = ("%.0f%%" % data["stable_percent"] if data["stable_percent"] is not None
                      else "暂无")
            text = (
                "%s\n\n"
                "记录 %d 条 · 正常比例 %s · 掉线 %d 次 · 自动恢复 %d 次 · "
                "恢复失败 %d 次 · VPN 异常 %d 次" % (
                    data["summary"], data["events"], stable, c["disconnect"], c["recovery"],
                    c["failure"], c["vpn_issue"]))
            outages = core.analyze_outage_timeline(7)
            if outages:
                text += "\n\n—— 断网时间线（最近 7 天）——\n"
                for idx, o in enumerate(outages, 1):
                    text += "%d. %s 断网 → %s 恢复（持续 %s）\n" % (
                        idx, o["start"], o["end"], o["duration"])
                text += ("\n（提示：若断网集中在固定时段，多为路由器过热/链路问题；"
                         "持续多次请检查路由器散热或考虑重启）")
            self._lbl_report.configure(text=text)
        except Exception as exc:
            try:
                self._lbl_report.configure(text="读取历史记录失败：%s" % exc)
            except Exception:
                pass

    def _pref_check_update(self):
        """偏好设置里的「立即检查」按钮: 异步检查, 结果用内联 Label 呈现, 不再弹窗。"""
        try:
            if self._btn_pref_check is not None:
                self._btn_pref_check.configure(state="disabled", text="检查中…")
        except Exception:
            pass
        self._set_pref_upd_text("正在检查 GitHub Release…")
        self._log("偏好设置中: 手动检查更新")

        def on_result(info):
            self.after(0, lambda: self._render_pref_update_result(info))
        self._bg_check_update(manual=True, on_result=on_result)

    def _set_pref_upd_text(self, text):
        try:
            self._lbl_pref_upd.configure(text=text)
        except Exception:
            pass

    def _render_pref_update_result(self, info):
        try:
            if self._btn_pref_check is not None:
                self._btn_pref_check.configure(state="normal", text="立即检查")
        except Exception:
            pass
        if not info:
            self._set_pref_upd_text("✓ 已是最新版本 v%s" % core.APP_VERSION)
            # 清理残留的立即更新按钮
            btn = getattr(self, "_btn_pref_update_now", None)
            if btn is not None:
                try:
                    btn.destroy()
                except Exception:
                    pass
                self._btn_pref_update_now = None
            self._pref_update_info = None
            return
        self._pref_update_info = info
        self._set_pref_upd_text("发现新版本 %s（当前 v%s）。检查按钮已自动切换为「立即更新」，点一下自动下载并重启完成替换。" % (
            info["tag"], core.APP_VERSION))
        # 把 "立即检查" 按钮原地变身为 "立即更新" —— 用户无需再找按钮
        if getattr(self, "_btn_pref_check", None) is not None:
            try:
                self._btn_pref_check.configure(
                    text="立即更新",
                    command=lambda: self._do_update(self._pref_update_info),
                    style="Accent.TButton")
            except Exception:
                pass
        if getattr(self, "_btn_pref_update_now", None) is None:
            # parent 必须挂到偏好设置 card 上, 否则 pack 到根窗口会被埋在底层看不见
            parent = getattr(self, "_pref_card", None) or self
            self._btn_pref_update_now = ttk.Button(
                parent, text="立即更新", style="Accent.TButton",
                command=lambda: self._do_update(self._pref_update_info))
            try:
                self._btn_pref_update_now.pack(anchor="w", pady=(10, 0))
            except Exception:
                pass


