# -*- coding: utf-8 -*-
"""连接档案表单 Mixin (自 app_gui.py 拆分)"""
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


class ProfileFormMixin:
    def _current_profile(self):
        """当前档案: 优先读档案窗口下拉框(已打开时); 窗口关闭时退回 cfg 的 active_profile。
        守护进程/Web 控制台可能在档案窗口未打开时调用, 不能依赖界面控件。"""
        name = None
        cmb = getattr(self, "cmb_profile", None)
        if cmb is not None:
            try:
                if cmb.winfo_exists():
                    disp = cmb.get()
                    name = getattr(self, "_profile_map", {}).get(disp, disp)
            except Exception:
                name = None
        if name is None:
            name = self.cfg.get("active_profile", "") if getattr(self, "cfg", None) else ""
        for p in self.cfg.get("profiles", []):
            if p["name"] == name:
                return p
        return None


    def _on_profile_selected(self, event=None):
        """下拉框切换档案: 同步更新 active_profile 并保存, 否则守护读到旧档案。"""
        try:
            p = self._current_profile()
            if not p:
                return
            old = self.cfg.get("active_profile")
            new = p["name"]
            if new != old:
                self.cfg["active_profile"] = new
                core.save_config(self.cfg)
                self._log("已切换档案: %s" % new)
            self._load_form_from_current()
        except Exception:
            self._load_form_from_current()


    def _on_ptype_change(self, event=None):
        """切换档案类型: 「普通WiFi」清空账号/认证服务器并置灰; 「校园网」恢复。"""
        wifi = self.cmb_ptype.get() == "普通WiFi/热点（只检测断网）"
        state = "disabled" if wifi else "normal"
        for ent in (self.ent_user, self.ent_pass, self.cmb_auth):
            try:
                ent.configure(state=state)
            except Exception:
                pass
        if wifi:
            self.cmb_auth.set("")
            self.btn_detect.configure(text="识别网络", state="normal")
        else:
            self.btn_detect.configure(text="探测", state="normal")
        # 提示文案
        hint = ("此档案不登录校园网，守护只检测是否断网，断网时通知你。"
                if wifi else "此档案会登录校园网并保活，认证服务器必填。")
        if hasattr(self, "lbl_ptype_hint"):
            self.lbl_ptype_hint.configure(text=hint)


    def _set_ptype_ui(self, profile):
        """根据档案类型初始化类型下拉框和字段状态(加载档案时调用)。"""
        wifi = core.profile_is_wifi(profile)
        self.cmb_ptype.set("普通WiFi/热点（只检测断网）" if wifi else "校园网认证（登录保活）")
        self._on_ptype_change()
        if hasattr(self, "lbl_ptype_hint"):
            self.lbl_ptype_hint.configure(
                text="此档案不登录校园网，守护只检测是否断网，断网时通知你。" if wifi
                else "此档案会登录校园网并保活，认证服务器必填。")


    def _refresh_profile_list(self):
        self._profile_map = {}
        displays = []
        for p in self.cfg.get("profiles", []):
            if p.get("ssid") or p.get("gateway"):
                d = "%s (%s)" % (p["name"], p.get("ssid") or p.get("gateway"))
            else:
                d = "任意网络使用"
            if p.get("preset") == core.LIDA_PROFILE_ID:
                d = "立达专属 · " + d
            self._profile_map[d] = p["name"]
            displays.append(d)
        cmb = getattr(self, "cmb_profile", None)
        try:
            alive = cmb is not None and cmb.winfo_exists()
        except Exception:
            alive = False
        if not alive:
            # 档案窗口未打开: 只需维护映射, 界面写入等窗口打开时进行
            if not displays and self.cfg.get("profiles"):
                self.cfg["active_profile"] = self.cfg["profiles"][0]["name"]
            return
        cmb["values"] = displays
        active = self.cfg.get("active_profile")
        if active and active in self._profile_map.values():
            for d, n in self._profile_map.items():
                if n == active:
                    cmb.set(d)
                    break
        elif displays:
            cmb.set(displays[0])


    def _toggle_pass(self):
        self.ent_pass.configure(show="" if self.ent_pass.cget("show") else "●")


    def _load_form_from_current(self):
        p = self._current_profile()
        if not p:
            return
        cmb = getattr(self, "cmb_profile", None)
        try:
            if cmb is not None and not cmb.winfo_exists():
                cmb = None
        except Exception:
            cmb = None
        if cmb is None:
            # 档案窗口未打开: 表单控件不存在, 无需填充(下次打开时 open_profile_window 会重新填充)
            return
        def setv(ent, v):
            ent.delete(0, "end")
            ent.insert(0, str(v or ""))
        setv(self.ent_name, p.get("name", ""))
        setv(self.ent_ssid, p.get("ssid", ""))
        setv(self.ent_gw, p.get("gateway", ""))
        setv(self.ent_user, p.get("username", ""))
        setv(self.ent_pass, p.get("password", ""))
        self.cmb_interval.set(str(p.get("interval", 1800)))
        history = self.cfg.get("auth_history") or []
        # 任意网络使用档案: 不强制预填学校认证服务器, 留空让用户探测/自行填写。
        is_any = not p.get("ssid") and not p.get("gateway") and not p.get("username")
        cur = "" if is_any else (p.get("auth_url", "") or "")
        # 若档案存了 auth_url 则用它; 否则留空(任意网络可探测)
        saved_auth = p.get("auth_url", "")
        if is_any and not saved_auth:
            cur = ""
        elif saved_auth:
            cur = saved_auth
        if cur and cur not in history:
            history = [cur] + history
        self.cmb_auth["values"] = history[-15:]
        self.cmb_auth.set(cur)
        lt = p.get("login_type", "cmcc")
        self.cmb_type.current({"cmcc": 0, "unicom": 1, "teacher": 2}.get(lt, 0))
        # 初始化档案类型下拉框并同步字段可用状态
        self._set_ptype_ui(p)


    def _form_to_profile(self):
        lt = {0: "cmcc", 1: "unicom", 2: "teacher"}[self.cmb_type.current()]
        return {
            "name": self.ent_name.get().strip(),
            "ssid": self.ent_ssid.get().strip(),
            "gateway": self.ent_gw.get().strip(),
            "username": self.ent_user.get().strip(),
            "password": self.ent_pass.get().strip(),
            "login_type": lt,
            # 档案类型: 校园网认证(campus) / 普通WiFi热点(wifi)
            "profile_type": "wifi" if self.cmb_ptype.get() == "普通WiFi/热点（只检测断网）" else "campus",
            # 普通WiFi档案不填认证服务器
            "auth_url": (self.cmb_auth.get().strip() or core.DEFAULT_AUTH_URL)
            if self.cmb_ptype.get() != "普通WiFi/热点（只检测断网）" else "",
            "interval": max(10, int(self.cmb_interval.get() or 1800)),
        }


    def new_profile(self):
        base = "新档案"
        i = 1
        names = [p["name"] for p in self.cfg.get("profiles", [])]
        while base + str(i) in names:
            i += 1
        self.cfg.setdefault("profiles", []).append(core.default_profile(base + str(i)))
        self.cfg["active_profile"] = base + str(i)
        core.save_config(self.cfg)
        self._refresh_profile_list()
        self._load_form_from_current()
        self._log("已新建档案: %s" % (base + str(i)))


    def del_profile(self):
        p = self._current_profile()
        if not p:
            return
        if p.get("preset") == core.LIDA_PROFILE_ID:
            messagebox.showinfo("内置档案", "立达校园网是内置专属档案，不能删除。\n账号、密码和运营商可以自由修改。")
            return
        if len(self.cfg["profiles"]) <= 1:
            messagebox.showwarning("提示", "至少保留一个档案")
            return
        if not messagebox.askyesno("删除档案", "确定删除档案「%s」吗？" % p["name"]):
            return
        core.keychain_delete(p.get("secret_id"))
        self.cfg["profiles"].remove(p)
        self.cfg["active_profile"] = self.cfg["profiles"][0]["name"]
        core.save_config(self.cfg)
        self._refresh_profile_list()
        self._load_form_from_current()
        self._log("已删除档案: %s" % p["name"])


    def save_profile(self):
        try:
            data = self._form_to_profile()
            if not data["name"]:
                messagebox.showwarning("提示", "档案名称不能为空")
                return
            if not data["username"] or not data["password"]:
                messagebox.showwarning("提示", "账号和密码不能为空")
                return
            p = self._current_profile()
            if p:
                p.update(data)
            self.cfg["active_profile"] = data["name"]
            # 记录认证服务器历史
            hist = [h for h in (self.cfg.get("auth_history") or []) if h != data["auth_url"]]
            self.cfg["auth_history"] = [data["auth_url"]] + hist
            self.cfg["auth_history"] = self.cfg["auth_history"][-15:]
            core.save_config(self.cfg, sync_secrets=True)
            self._refresh_profile_list()
            self._log("档案已保存: %s (%s)" % (data["name"], data["ssid"] or "默认"))
            secure_note = "\n密码已安全保存到 macOS 钥匙串。" if core.IS_MACOS else ""
            messagebox.showinfo("已保存", "档案「%s」已保存。%s\n\n换网络后 App 会根据 WiFi 自动匹配对应档案。" % (
                data["name"], secure_note))
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


