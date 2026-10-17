# -*- coding: utf-8 -*-
"""校园网连接管家 · 手机版 (Android / Kivy)

手机直连校园网 WiFi 时:
- 一键登录 Dr.COM (复用桌面端 core.auth 的登录实现)
- 前台保活: App 打开期间定时检测认证/外网, 掉线自动重登
- 档案保存: 账号/运营商/认证服务器存应用私有目录

Android 使用独立前台服务运行保活循环；桌面开发环境保留 Kivy 前台定时器回退。
"""
import json
import os
import threading
import traceback


def _configure_kivy_home(environ=None):
    """Keep Kivy's writable cache/config outside p4a's extracted source tree."""
    environ = os.environ if environ is None else environ
    app_path = environ.get("ANDROID_APP_PATH")
    if app_path and not environ.get("KIVY_HOME"):
        # p4a extracts bundled Python sources under files/app, which is not a
        # writable home for Kivy's default .kivy/icon copy. The parent files/
        # directory is app-private and writable by this package.
        environ["KIVY_HOME"] = os.path.join(os.path.dirname(app_path), ".kivy")


_configure_kivy_home()

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput

import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                       # 打包后 core/ 与 main.py 同目录
sys.path.insert(0, os.path.dirname(_HERE))      # 开发时 core/ 在仓库根
from core import auth, config  # noqa: E402
from startup_status import initial_network_status  # noqa: E402

_FONT_PATH = os.path.join(_HERE, "assets", "NotoSansSC.ttf")
_FONT_NAME = _FONT_PATH if os.path.isfile(_FONT_PATH) else "Roboto"

APP_TITLE = "校园网连接管家"
METHODS = [("cmcc", "移动"), ("unicom", "联通"), ("teacher", "教师")]
BG = (0.043, 0.071, 0.125, 1)
CARD = (0.075, 0.114, 0.180, 1)
ACCENT = (0.310, 0.486, 1.0, 1)
GREEN = (0.196, 0.769, 0.553, 1)
RED = (0.941, 0.392, 0.471, 1)
MUTED = (0.561, 0.631, 0.729, 1)

KEEPALIVE_INTERVAL = 60  # 秒
GUARD_STATE_POLL_INTERVAL = 5
ANDROID_SERVICE_CLASS = "org.campusnettools.campusnetmanager.ServiceCampusguard"


class CjkSpinnerOption(SpinnerOption):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", _FONT_NAME)
        super().__init__(**kwargs)


class Root(BoxLayout):
    def __init__(self, app, **kwargs):
        super().__init__(orientation="vertical", padding=14, spacing=8, **kwargs)
        self.app = app

        self.lbl_status = Label(text="正在检测网络环境…", size_hint_y=None, height=64,
                                color=GREEN, font_size="16sp", font_name=_FONT_NAME)
        self.add_widget(self.lbl_status)
        self.lbl_env = Label(text="", size_hint_y=None, height=28, color=MUTED,
                             font_size="12sp", font_name=_FONT_NAME)
        self.add_widget(self.lbl_env)

        form = BoxLayout(orientation="vertical", spacing=6, size_hint_y=None, height=348)
        self.in_user = self._field(form, "账号（学号）")
        self.in_pass = self._field(form, "密码", password=True)
        form.add_widget(Label(text="运营商", size_hint_y=None, height=24,
                              color=MUTED, halign="left", text_size=(None, None),
                              font_name=_FONT_NAME))
        self.sp_method = Spinner(text="移动", values=[name for _, name in METHODS],
                                 size_hint_y=None, height=44,
                                 font_name=_FONT_NAME, option_cls=CjkSpinnerOption)
        form.add_widget(self.sp_method)
        self.in_auth = self._field(form, "认证服务器", text=auth.DEFAULT_AUTH_URL)
        self.lbl_auth_warning = Label(
            text="提醒：若认证地址使用 HTTP，账号和密码会明文发送，校园网络可见；HTTPS 地址会按配置使用且不会降级。只在可信校园网登录。",
            size_hint_y=None, height=48, color=(0.95, 0.68, 0.25, 1),
            font_size="11sp", font_name=_FONT_NAME, halign="left", valign="middle",
        )
        self.lbl_auth_warning.bind(size=lambda widget, size: setattr(
            widget, "text_size", (size[0], None)))
        form.add_widget(self.lbl_auth_warning)
        self.add_widget(form)

        row = BoxLayout(size_hint_y=None, height=48, spacing=8)
        self.btn_login = Button(text="立即登录", background_color=ACCENT,
                                font_name=_FONT_NAME)
        self.btn_login.bind(on_release=lambda *_a: self.app.manual_login())
        self.btn_guard = Button(text="开启保活", background_color=GREEN,
                                font_name=_FONT_NAME)
        self.btn_guard.bind(on_release=lambda *_a: self.app.toggle_guard())
        row.add_widget(self.btn_login)
        row.add_widget(self.btn_guard)
        self.add_widget(row)

        self.lbl_log = Label(text="", color=MUTED, font_size="11sp",
                             font_name=_FONT_NAME,
                             halign="left", valign="top")
        scroll = ScrollView()
        scroll.add_widget(self.lbl_log)
        self.add_widget(scroll)
        self.lbl_log.bind(texture_size=lambda _w, ts: setattr(
            self.lbl_log, "height", max(ts[1], 200)))

    def _field(self, parent, hint, password=False, text=""):
        ti = TextInput(hint_text=hint, multiline=False, password=password,
                       size_hint_y=None, height=44, text=text,
                       font_name=_FONT_NAME)
        parent.add_widget(ti)
        return ti

    def log(self, msg):
        def _upd(_dt):
            lines = (self.lbl_log.text.split("\n") + [msg])[-120:]
            self.lbl_log.text = "\n".join(lines)
        Clock.schedule_once(_upd)

    def set_status(self, text, ok=None, source=None):
        def _upd(_dt):
            self.lbl_status.text = text
            self.lbl_status.color = MUTED if ok is None else (GREEN if ok else RED)
            if source == "network":
                # A non-sensitive readiness marker lets the emulator smoke
                # distinguish a live UI from one stuck on its loading label.
                print("CNM_NETWORK_STATUS_READY: " + text, flush=True)
        Clock.schedule_once(_upd)


class CampusNetMobile(App):
    def build(self):
        self.title = APP_TITLE
        self.root = Root(self)
        self._guard_event = None
        self._guard_poll_event = None
        self._android_guard_requested = False
        self._load_profile()
        Clock.schedule_once(lambda _dt: self.refresh_status(), 0.5)
        if self._is_android():
            self._guard_poll_event = Clock.schedule_interval(
                lambda _dt: self._refresh_guard_state(), GUARD_STATE_POLL_INTERVAL)
            Clock.schedule_once(lambda _dt: self._refresh_guard_state(), 0.7)
        return self.root

    @staticmethod
    def _is_android():
        return bool(os.environ.get("ANDROID_ARGUMENT"))

    # ---------- 档案 ----------

    @property
    def _cfg_path(self):
        filename = "profile.enc" if self._is_android() else "profile.json"
        return os.path.join(self.user_data_dir, filename)

    def _load_profile(self):
        try:
            from guard_service import load_android_profile, load_profile_data_if_present
            legacy_path = os.path.join(self.user_data_dir, "profile.json")
            source_path = self._cfg_path
            if self._is_android():
                data, cleanup_pending = load_android_profile(source_path, legacy_path)
                if cleanup_pending:
                    self.root.log("加密档案已加载，但旧明文档案暂时无法删除；请检查应用存储权限后重试。")
            else:
                data = load_profile_data_if_present(source_path)
            self.root.in_user.text = data.get("username", "")
            self.root.in_pass.text = data.get("password", "")
            self.root.in_auth.text = data.get("auth_url", auth.DEFAULT_AUTH_URL)
            name = dict(METHODS).get(data.get("method", "cmcc"), "移动")
            self.root.sp_method.text = name
        except Exception as exc:
            self.root.log("本地档案未加载或迁移失败：%s" % type(exc).__name__)

    def _save_profile(self):
        try:
            from guard_service import write_profile
            write_profile(self._cfg_path, self._form_data())
            return True
        except Exception:
            self.root.log("档案保存失败:\n" + traceback.format_exc(limit=1))
            return False

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
        # Kivy widgets belong to the UI thread. Snapshot values before starting
        # the worker instead of reading TextInput/Spinner properties there.
        auth_url = self._form_data()["auth_url"]

        def work():
            status, healthy, error_type = initial_network_status(auth, auth_url)
            if error_type:
                self.root.log("网络状态检测失败：%s" % error_type)
            self.root.set_status(status, ok=healthy, source="network")
        threading.Thread(target=work, daemon=True).start()

    # ---------- 登录 / 保活 ----------

    def manual_login(self):
        data = self._form_data()
        if not data["username"] or not data["password"]:
            self.root.set_status("请先填写账号和密码", ok=False)
            return
        self._save_profile()
        profile = self._profile()
        self.root.set_status("正在登录…", ok=None)

        def work():
            ok = auth.ensure_login(profile,
                                   on_log=lambda m: self.root.log(m))
            self.root.set_status("登录成功，校园网在线" if ok else "登录失败，请检查账号密码/名额",
                                 ok=ok)
            Clock.schedule_once(lambda _dt: self.refresh_status(), 1)
        threading.Thread(target=work, daemon=True).start()

    def toggle_guard(self):
        if self._is_android():
            if self._android_guard_requested:
                self._stop_android_guard()
            else:
                data = self._form_data()
                if not data["username"] or not data["password"]:
                    self.root.set_status("请先填写账号和密码", ok=False)
                    return
                if not self._save_profile():
                    self.root.set_status("档案保存失败，后台保活未开启", ok=False)
                    return
                self._request_notification_permission(self._start_android_guard)
            return
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

    def _request_notification_permission(self, continuation):
        """Request the notification permission before starting a user-visible FGS."""
        try:
            from jnius import autoclass
            sdk = int(autoclass("android.os.Build$VERSION").SDK_INT)
            if sdk < 33:
                continuation(True)
                return
            from android.permissions import check_permission, request_permissions
            permission = "android.permission.POST_NOTIFICATIONS"
            if check_permission(permission):
                continuation(True)
                return

            def completed(_permissions, grants):
                granted = bool(grants and int(grants[0]) == 0)
                Clock.schedule_once(lambda _dt: continuation(granted))

            request_permissions([permission], completed)
        except Exception as exc:
            self.root.log("无法检查通知权限：%s" % type(exc).__name__)
            self.root.set_status("需要允许通知，才能开启后台保活", ok=False)

    def _start_android_guard(self, permission_granted):
        if not permission_granted:
            self.root.set_status("未允许通知，后台保活未开启", ok=False)
            return
        try:
            from jnius import autoclass
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            service = autoclass(ANDROID_SERVICE_CLASS)
            argument = json.dumps({"profile_path": self._cfg_path,
                                   "state_path": self._guard_state_path},
                                  ensure_ascii=False)
            service.start(activity, "icon", "校园网连接管家",
                          "校园网保活正在运行", argument)
            self._android_guard_requested = True
            self.root.btn_guard.text = "停止保活"
            self.root.set_status("后台保活服务正在启动…", ok=None)
            self.root.log("已启动 Android 前台保活服务")
            Clock.schedule_once(lambda _dt: self._refresh_guard_state(), 1)
        except Exception as exc:
            self._android_guard_requested = False
            self.root.set_status("后台保活启动失败：%s" % type(exc).__name__, ok=False)
            self.root.log("请检查通知权限和 Android 前台服务配置")

    def _stop_android_guard(self):
        try:
            from jnius import autoclass
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            service = autoclass(ANDROID_SERVICE_CLASS)
            service.stop(activity)
        except Exception as exc:
            self.root.log("停止后台保活时出现问题：%s" % type(exc).__name__)
        self._android_guard_requested = False
        self.root.btn_guard.text = "开启保活"
        self.root.set_status("正在停止后台保活…", ok=None)

        def mark_stopped(_dt):
            try:
                from guard_service import write_state
                write_state(self._guard_state_path, {
                    "enabled": False, "status": "stopped",
                    "message": "校园网保活已停止。"})
            except Exception:
                pass
            self._refresh_guard_state()

        Clock.schedule_once(mark_stopped, 0.8)

    @property
    def _guard_state_path(self):
        return os.path.join(self.user_data_dir, "guard-state.json")

    def _refresh_guard_state(self):
        if not self._is_android():
            return
        try:
            from guard_service import state_is_fresh
            with open(self._guard_state_path, encoding="utf-8") as stream:
                state = json.load(stream)
            active = state_is_fresh(state)
            self._android_guard_requested = active
            self.root.btn_guard.text = "停止保活" if active else "开启保活"
            if active:
                self.root.set_status(state.get("message", "后台保活运行中"),
                                     ok=state.get("status") == "online")
            elif state.get("status") == "stopped":
                self.root.set_status("校园网保活已停止", ok=None)
            else:
                self.root.set_status("后台保活状态未知或服务已停止", ok=False)
        except (OSError, ValueError):
            self._android_guard_requested = False
            self.root.btn_guard.text = "开启保活"

    def _guard_tick(self):
        profile = self._profile()
        auth_url = profile["auth_url"]

        def work():
            if not auth.auth_reachable(auth_url):
                self.root.set_status("非校园网环境，保活休眠", ok=None)
                return
            if not auth.check_auth(auth_url) or not auth.check_internet():
                self.root.log("检测到掉线，自动重登…")
                ok = auth.ensure_login(profile,
                                       on_log=lambda m: self.root.log(m))
                self.root.set_status("掉线已自动恢复" if ok else "自动重登失败", ok=ok)
            else:
                self.root.set_status("校园网在线（保活中）", ok=True)
        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    CampusNetMobile().run()
