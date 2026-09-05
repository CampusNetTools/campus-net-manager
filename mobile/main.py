# -*- coding: utf-8 -*-
"""校园网连接管家 · 手机版 (Android / Kivy)

手机直连校园网 WiFi 时:
- 一键登录 Dr.COM (复用桌面端 core.auth 的登录实现)
- 前台保活: App 打开期间定时检测认证/外网, 掉线自动重登
- 档案保存: 账号/运营商/认证服务器存应用私有目录

注意: Android 后台保活需要前台服务, 当前版本 App 在前台时保活生效;
锁屏/切后台后系统可能挂起定时器 (后续版本接 foreground service)。
"""
import json
import os
import threading
import traceback

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                       # 打包后 core/ 与 main.py 同目录
sys.path.insert(0, os.path.dirname(_HERE))      # 开发时 core/ 在仓库根
from core import auth, config  # noqa: E402

APP_TITLE = "校园网连接管家"
METHODS = [("cmcc", "移动"), ("unicom", "联通"), ("teacher", "教师")]
BG = (0.043, 0.071, 0.125, 1)
CARD = (0.075, 0.114, 0.180, 1)
ACCENT = (0.310, 0.486, 1.0, 1)
GREEN = (0.196, 0.769, 0.553, 1)
RED = (0.941, 0.392, 0.471, 1)
MUTED = (0.561, 0.631, 0.729, 1)

KEEPALIVE_INTERVAL = 60  # 秒


class Root(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=14, spacing=8, **kwargs)
        self.app = app

        self.lbl_status = Label(text="正在检测网络环境…", size_hint_y=None, height=64,
                                color=GREEN, font_size="16sp")
        self.add_widget(self.lbl_status)
        self.lbl_env = Label(text="", size_hint_y=None, height=28, color=MUTED,
                             font_size="12sp")
        self.add_widget(self.lbl_env)

        form = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, height=300)
        self.in_user = self._field(form, "账号（学号）")
        self.in_pass = self._field(form, "密码", password=True)
        form.add_widget(Label(text="运营商", size_hint_y=None, height=24,
                              color=MUTED, halign="left", text_size=(None, None)))
        self.sp_method = Spinner(text="移动", values=[name for _, name in METHODS],
                                 size_hint_y=None, height=44)
        form.add_widget(self.sp_method)
        self.in_auth = self._field(form, "认证服务器", text=auth.DEFAULT_AUTH_URL)
        self.add_widget(form)

        row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.btn_login = Button(text="立即登录", background_color=ACCENT)
        self.btn_login.bind(on_release=lambda *_a: self.app.manual_login())
        self.btn_guard = Button(text="开启保活", background_color=GREEN)
        self.btn_guard.bind(on_release=lambda *_a: self.app.toggle_guard())
        row.add_widget(self.btn_login)
        row.add_widget(self.btn_guard)
        self.add_widget(row)

        self.lbl_log = Label(text="", color=MUTED, font_size="11sp",
                             halign="left", valign="top")
        scroll = ScrollView()
        scroll.add_widget(self.lbl_log)
        self.add_widget(scroll)
        self.lbl_log.bind(texture_size=lambda _w, ts: setattr(
            self.lbl_log, "height", max(ts[1], 200)))

    def _field(self, parent, hint, password=False, text=""):
        ti = TextInput(hint_text=hint, multiline=False, password=password,
                       size_hint_y=None, height=44, text=text)
        parent.add_widget(ti)
        return ti

    def log(self, msg):
        def _upd(_dt):
            lines = (self.lbl_log.text.split("\n") + [msg])[-120:]
            self.lbl_log.text = "\n".join(lines)
        Clock.schedule_once(_upd)

    def set_status(self, text, ok=None):
        def _upd(_dt):
            self.lbl_status.text = text
            self.lbl_status.color = MUTED if ok is None else (GREEN if ok else RED)
        Clock.schedule_once(_upd)


class CampusNetMobile(App):
    def build(self):
        self.title = APP_TITLE
        self.root = Root(self)
        self._guard_event = None
        self._load_profile()
        Clock.schedule_once(lambda _dt: self.refresh_status(), 0.5)
        return self.root

    # ---------- 档案 ----------

    @property
    def _cfg_path(self):
        return os.path.join(self.user_data_dir, "profile.json")

    def _load_profile(self):
        try:
            with open(self._cfg_path, encoding="utf-8") as f:
                data = json.load(f)
            self.root.in_user.text = data.get("username", "")
            self.root.in_pass.text = data.get("password", "")
            self.root.in_auth.text = data.get("auth_url", auth.DEFAULT_AUTH_URL)
            name = dict(METHODS).get(data.get("method", "cmcc"), "移动")
            self.root.sp_method.text = name
        except Exception:
            pass

    def _save_profile(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self._cfg_path, "w", encoding="utf-8") as f:
                json.dump(self._form_data(), f, ensure_ascii=False)
        except Exception:
            self.root.log("档案保存失败:\n" + traceback.format_exc(limit=1))

    def _form_data(self):
        method = "cmcc"
        for key, name in METHODS:
            if name == self.root.sp_method.text:
                method = key
        return {"username": self.root.in_user.text.strip(),
                "password": self.root.in_pass.text,
                "method": method,
                "auth_url": self.root.in_auth.text.strip() or auth.DEFAULT_AUTH_URL}

    def _profile(self):
        data = self._form_data()
        profile = config.default_profile("手机档案")
        profile.update(data)
        return profile

    # ---------- 状态检测 ----------

    def refresh_status(self):
        def work():
            auth_url = self._form_data()["auth_url"]
            reachable = auth.auth_reachable(auth_url)
            if not reachable:
                self.root.set_status("非校园网环境（认证服务器不可达）", ok=None)
                self.root.log("认证服务器 %s 不可达，保活休眠" % auth_url)
                return
            authed = auth.check_auth(auth_url)
            internet = auth.check_internet()
            if authed and internet:
                self.root.set_status("校园网在线（已认证 · 可上网）", ok=True)
            elif authed:
                self.root.set_status("已认证但外网不通", ok=False)
            else:
                self.root.set_status("校园网未认证（需要登录）", ok=False)
        threading.Thread(target=work, daemon=True).start()

    # ---------- 登录 / 保活 ----------

    def manual_login(self):
        data = self._form_data()
        if not data["username"] or not data["password"]:
            self.root.set_status("请先填写账号和密码", ok=False)
            return
        self._save_profile()
        self.root.set_status("正在登录…", ok=None)

        def work():
            ok = auth.ensure_login(self._profile(),
                                   on_log=lambda m: self.root.log(m))
            self.root.set_status("登录成功，校园网在线" if ok else "登录失败，请检查账号密码/名额",
                                 ok=ok)
            Clock.schedule_once(lambda _dt: self.refresh_status(), 1)
        threading.Thread(target=work, daemon=True).start()

    def toggle_guard(self):
        if self._guard_event:
            self._guard_event.cancel()
            self._guard_event = None
            self.root.btn_guard.text = "开启保活"
            self.root.log("保活已停止")
            return
        self._save_profile()
        self._guard_event = Clock.schedule_interval(lambda _dt: self._guard_tick(),
                                                    KEEPALIVE_INTERVAL)
        self.root.btn_guard.text = "停止保活"
        self.root.log("保活已开启（每 %d 秒检测，前台有效）" % KEEPALIVE_INTERVAL)
        self._guard_tick()

    def _guard_tick(self):
        def work():
            data = self._form_data()
            auth_url = data["auth_url"]
            if not auth.auth_reachable(auth_url):
                self.root.set_status("非校园网环境，保活休眠", ok=None)
                return
            if not auth.check_auth(auth_url) or not auth.check_internet():
                self.root.log("检测到掉线，自动重登…")
                ok = auth.ensure_login(self._profile(),
                                       on_log=lambda m: self.root.log(m))
                self.root.set_status("掉线已自动恢复" if ok else "自动重登失败", ok=ok)
            else:
                self.root.set_status("校园网在线（保活中）", ok=True)
        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    CampusNetMobile().run()
