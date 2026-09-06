# -*- coding: utf-8 -*-
"""偏好设置/自启/导入导出 Mixin (自 app_gui.py 拆分)"""
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
        """网络记录和系统通知集中设置，避免继续挤占主界面。"""
        core.ensure_preferences(self.cfg)
        win = tk.Toplevel(self)
        win.title("偏好设置")
        win.configure(bg=BG)
        win.geometry("560x620")
        win.resizable(False, True)
        win.minsize(540, 560)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(22, 18))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card, text="偏好设置", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="只记录连接状态，不记录浏览内容、账号或密码。",
                  style="Muted.TLabel").pack(anchor="w", pady=(3, 12))
        ttk.Label(card, text="绿色对号表示已选择；点击“保存设置”后正式生效。",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

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
        ttk.Checkbutton(card, text="保存网络稳定性历史", variable=var_history,
                        style="Checkmark.TCheckbutton").pack(anchor="w")
        keep_awake_hint = "合盖/系统空闲时继续保活（需 macOS，用 caffeinate 防止睡眠）" if core.IS_MACOS else "合盖/系统睡眠时继续保活（当前平台仅部分支持）"
        ttk.Checkbutton(card, text="合盖/休眠时保持运行", variable=var_keep_awake,
                        style="Checkmark.TCheckbutton").pack(anchor="w", pady=(4, 0))
        ttk.Label(card, text=keep_awake_hint, style="Muted.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(card, text="防踢保活（名额满时优先保住本机，不让新设备挤掉）",
                        variable=var_kick_guard, style="Checkmark.TCheckbutton").pack(anchor="w")
        ttk.Label(card, text="周期性刷新登录会话，让本机/路由器保持最新，第 3 台设备登录时被挤掉的是别人",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(card, text="启动时自动检查新版本（GitHub Release）",
                        variable=var_auto_update, style="Checkmark.TCheckbutton").pack(anchor="w")

        ttk.Label(card, text="系统通知", style="Section.TLabel").pack(anchor="w")
        master_notify = ttk.Checkbutton(
            card, text="允许校园网连接管家发送通知", variable=var_notify,
            style="Checkmark.TCheckbutton")
        master_notify.pack(
            anchor="w", pady=(6, 3))
        categories = ttk.Frame(card, style="Inner.TFrame")
        categories.pack(fill="x")
        category_buttons = []
        for index, (key, text) in enumerate((
                ("disconnect", "检测到掉线"), ("recovery", "网络恢复"),
                ("failure", "自动恢复失败"), ("device", "新设备请求共享"))):
            child = ttk.Checkbutton(categories, text=text, variable=category_vars[key],
                                    style="Checkmark.TCheckbutton")
            # 单列纵向排列, 避免长文案被窗口宽度截断
            child.pack(anchor="w", pady=2)
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

        def save_preferences():
            self.cfg["history_enabled"] = bool(var_history.get())
            self.cfg["keep_awake"] = bool(var_keep_awake.get())
            self.cfg["kick_guard"] = bool(var_kick_guard.get())
            self.cfg["auto_update_check"] = bool(var_auto_update.get())
            self.cfg["notifications"] = core.normalized_notification_settings(
                bool(var_notify.get()), {key: bool(value.get()) for key, value in category_vars.items()})
            core.save_config(self.cfg)
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
        actions.pack(fill="x", side="bottom", pady=(14, 0))
        ttk.Button(actions, text="测试通知", style="Gray.TButton",
                   command=lambda: core.send_system_notification("通知设置工作正常")).pack(side="left")
        ttk.Label(actions, text="网络报告与软件更新已移到独立窗口（主界面宫格入口）",
                  style="Muted.TLabel").pack(side="left", padx=(12, 0))
        ttk.Button(actions, text="保存设置", style="Accent.TButton", command=save_preferences).pack(side="right")

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
            if self.cfg.get("keep_awake") and not core.keep_awake_enabled():
                if core.keep_awake_start():
                    self._log("已恢复合盖/休眠保持运行 (caffeinate)")
                else:
                    self._log("警告: 合盖保持运行启动失败")
        except Exception:
            pass


