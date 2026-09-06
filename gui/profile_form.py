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
        """类型切换由 feature_windows._profile_rebuild_form 接管(动态重建)。
        保留此方法仅为不破坏既有 patch 调用; 不再尝试"原地变灰", 那体验不好。"""
        try:
            host = getattr(self, "_profile_form_host", None)
            if host is not None:
                self._profile_rebuild_form()
        except Exception:
            pass


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
        """重建表单字段并填充当前档案值(顶层入口, 由 _fwin_open 调用)。
        内部不递归 _profile_rebuild_form, 而是走 _fill_form_for_current_profile。"""
        p = self._current_profile()
        cmb = getattr(self, "cmb_profile", None)
        try:
            if cmb is not None and not cmb.winfo_exists():
                cmb = None
        except Exception:
            cmb = None
        if cmb is None or p is None:
            return
        try:
            wifi = core.profile_is_wifi(p)
            self.cmb_ptype.set("普通WiFi/热点（只检测断网）" if wifi
                               else "校园网认证（登录保活）")
        except Exception:
            pass
        self._profile_rebuild_form()  # 重建字段区
        self._fill_form_for_current_profile()

    def _fill_form_for_current_profile(self):
        """按当前档案类型填充已构建好的表单控件。不再触发 rebuild, 避免递归。"""
        p = self._current_profile()
        if p is None:
            return
        wifi = core.profile_is_wifi(p)
        if wifi:
            if self.ent_name is not None:
                self.ent_name.delete(0, "end")
                self.ent_name.insert(0, p.get("name", ""))
            if self.ent_ssid is not None:
                self.ent_ssid.delete(0, "end")
                self.ent_ssid.insert(0, p.get("ssid", ""))
            if self.ent_gw is not None:
                self.ent_gw.delete(0, "end")
                self.ent_gw.insert(0, p.get("gateway", ""))
            if self.cmb_interval is not None:
                self.cmb_interval.set(str(p.get("interval", 60)))
            return
        # 校园网档案
        if self.ent_name is not None:
            self.ent_name.delete(0, "end")
            self.ent_name.insert(0, p.get("name", ""))
        if self.ent_user is not None:
            self.ent_user.delete(0, "end")
            self.ent_user.insert(0, p.get("username", ""))
        if self.ent_pass is not None:
            self.ent_pass.delete(0, "end")
            self.ent_pass.insert(0, p.get("password", ""))
        if self.ent_ssid is not None:
            self.ent_ssid.delete(0, "end")
            self.ent_ssid.insert(0, p.get("ssid", ""))
        if self.ent_gw is not None:
            self.ent_gw.delete(0, "end")
            self.ent_gw.insert(0, p.get("gateway", ""))
        if self.cmb_interval is not None:
            self.cmb_interval.set(str(p.get("interval", 1800)))
        if self.cmb_type is not None:
            lt = p.get("login_type", "cmcc")
            self.cmb_type.current({"cmcc": 0, "unicom": 1, "teacher": 2}.get(lt, 0))
        if self.cmb_auth is not None:
            history = list(self.cfg.get("auth_history") or [])
            cur = p.get("auth_url", "")
            if cur and cur not in history:
                history = [cur] + history
            self.cmb_auth["values"] = history[-15:]
            self.cmb_auth.set(cur)


    def _form_to_profile(self):
        is_wifi = self._is_wifi_form()
        data = {
            "name": self.ent_name.get().strip() if self.ent_name else "",
            "profile_type": "wifi" if is_wifi else "campus",
            "interval": max(10, int(self.cmb_interval.get() or 1800)),
        }
        # 普通WiFi档案: 只记 ssid / gateway(至少一个), 其他一律不写(避免空字段堆积)
        if is_wifi:
            data["ssid"] = self.ent_ssid.get().strip() if self.ent_ssid else ""
            data["gateway"] = self.ent_gw.get().strip() if self.ent_gw else ""
            return data
        # 校园网档案: 完整字段
        data["ssid"] = self.ent_ssid.get().strip() if self.ent_ssid else ""
        data["gateway"] = self.ent_gw.get().strip() if self.ent_gw else ""
        data["username"] = self.ent_user.get().strip() if self.ent_user else ""
        data["password"] = self.ent_pass.get().strip() if self.ent_pass else ""
        data["login_type"] = {0: "cmcc", 1: "unicom", 2: "teacher"}.get(
            self.cmb_type.current(), "cmcc") if self.cmb_type else "cmcc"
        data["auth_url"] = (self.cmb_auth.get().strip() or core.DEFAULT_AUTH_URL) \
            if self.cmb_auth else core.DEFAULT_AUTH_URL
        return data


    def _is_wifi_form(self):
        """判断当前窗口选中的档案类型 — wifi 类型整个表单结构不同。"""
        try:
            return bool(self.cmb_ptype) and self.cmb_ptype.winfo_exists() \
                and self.cmb_ptype.get() == "普通WiFi/热点（只检测断网）"
        except Exception:
            return False

    def new_profile(self):
        base = "新档案"
        i = 1
        names = [p["name"] for p in self.cfg.get("profiles", [])]
        while base + str(i) in names:
            i += 1
        # 默认建 wifi 档案(更贴近新用户: 家庭/热点只想检测断网)
        # 立达专属档案在 ensure_lida_profile 里已存在
        self.cfg.setdefault("profiles", []).append(
            core.default_profile(base + str(i), profile_type="wifi"))
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
            if data["profile_type"] == "wifi":
                # 普通WiFi档案: 必须绑定 SSID 或 网关 之一, 否则没有任何网络可匹配
                if not data["ssid"] and not data["gateway"]:
                    messagebox.showwarning("提示",
                        "请绑定一个 WiFi 名称(SSID)或网关，否则守护找不到对应网络。")
                    return
                # wifi 档案不写 username/password/auth_url/login_type(避免堆积空字段)
                data["username"] = ""
                data["password"] = ""
                data["auth_url"] = ""
                data["login_type"] = ""
            else:
                # 校园网档案: 必须有账号密码
                if not data["username"] or not data["password"]:
                    messagebox.showwarning("提示", "校园网档案需要填写账号和密码")
                    return
                if not data["auth_url"]:
                    messagebox.showwarning("提示", "请填写认证服务器地址，或点「探测」自动寻找")
                    return
            p = self._current_profile()
            if p:
                p.update(data)
            else:
                self.cfg.setdefault("profiles", []).append(data)
            self.cfg["active_profile"] = data["name"]
            # 认证服务器历史(只对校园网有意义)
            if data["profile_type"] == "campus" and data.get("auth_url"):
                hist = [h for h in (self.cfg.get("auth_history") or [])
                        if h != data["auth_url"]]
                self.cfg["auth_history"] = [data["auth_url"]] + hist
                self.cfg["auth_history"] = self.cfg["auth_history"][-15:]
            core.save_config(self.cfg, sync_secrets=True)
            self._refresh_profile_list()
            self._log("档案已保存: %s (%s)" % (data["name"], data["ssid"] or "默认"))
            if data["profile_type"] == "campus":
                secure_note = "\n密码已安全保存到 macOS 钥匙串。" if core.IS_MACOS else ""
                messagebox.showinfo("已保存",
                    "档案「%s」已保存。%s\n\n换网络后 App 会根据 WiFi 自动匹配对应档案。" % (
                        data["name"], secure_note))
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


