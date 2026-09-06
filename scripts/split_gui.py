#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 app_gui.py 的单类 App 按功能拆成 gui/ Mixin 模块。

App 继承全部 Mixin, 方法体原样搬动, self 互调不受影响。
主题常量抽到 gui/theme.py。
"""
import re

SRC = "app_gui.py"
with open(SRC, encoding="utf-8") as f:
    lines = f.readlines()

CLASS_RE = re.compile(r"^class App\(tk\.Tk\):")
METHOD_RE = re.compile(r"^    def (\w+)\(")
MAIN_RE = re.compile(r'^if __name__ == "__main__":')
THEME_RE = re.compile(r"^# ---------- 深色主题")

class_idx = next(i for i, ln in enumerate(lines) if CLASS_RE.match(ln))
main_idx = next(i for i, ln in enumerate(lines) if MAIN_RE.match(ln))
theme_idx = next(i for i, ln in enumerate(lines) if THEME_RE.match(ln))

header = lines[:theme_idx]            # 导入区
theme = lines[theme_idx:class_idx]    # 主题常量
body = lines[class_idx + 1:main_idx]  # 类体
footer = lines[main_idx:]             # __main__

# 方法区间
methods = []  # (name, [lines])
cur = None
for ln in body:
    m = METHOD_RE.match(ln)
    if m:
        if cur:
            methods.append(cur)
        cur = [m.group(1), [ln]]
    else:
        cur[1].append(ln)
if cur:
    methods.append(cur)

GROUPS = {
    "profile_form": ["_current_profile", "_on_profile_selected", "_on_ptype_change",
                     "_set_ptype_ui", "_refresh_profile_list", "_toggle_pass",
                     "_load_form_from_current", "_form_to_profile",
                     "new_profile", "del_profile", "save_profile"],
    "router_tools": ["open_router_admin", "_do_open_router", "show_router_assessment",
                     "show_hotspot"],
    # NOTE: gui/router_proxy.py 是 v4.0.4 新增的独立 Mixin (RouterProxyMixin),
    #       不在本 GROUPS 内 (split_gui.py 已不再迁移新增 Mixin).
    #       关联方法 show_router_proxy_window 在 App 类里直接声明, 不依赖本脚本.
    "speed_window": ["show_speed_test"],
    "tunnel_ui": ["toggle_share", "_show_tunnel_ready", "_deploy_tunnel",
                  "_get_vpn_upstream", "_show_vpn_upstream_dialog", "_copy_text",
                  "_ask_tunnel_allow", "_poll_allow"],
    "preferences": ["_update_auto_btn", "_toggle_autostart", "export_config",
                    "import_config", "show_preferences", "_restore_preferences"],
    "tray": ["_make_tray_icon", "_hide_to_tray", "_show_from_tray",
             "_quit_from_tray", "on_close"],
    "daemon_ctl": ["set_guard", "set_net", "set_env", "_on_log", "_on_status",
                   "_on_env", "start_daemon", "toggle_daemon", "stop_daemon",
                   "check_now", "detect_auth", "_do_detect", "_on_alert",
                   "_watchdog", "export_diag", "_do_check", "_refresh_env",
                   "_auto_start"],
    "wizard": ["show_wizard", "show_help"],
}
KEEP = ["__init__", "_acquire_instance_lock", "_style", "_build_ui",
        "_scroll_log", "_toggle_log", "_row", "_load_existing_log",
        "_append_log", "_poll_log", "_log"]

TITLES = {
    "profile_form": "连接档案表单",
    "router_tools": "路由器管理/体检/热点",
    "speed_window": "测速窗口",
    "tunnel_ui": "隧道共享 UI",
    "preferences": "偏好设置/自启/导入导出",
    "tray": "系统托盘",
    "daemon_ctl": "守护控制与状态栏",
    "wizard": "新手向导与帮助",
}

assigned = {}
for name, mlines in methods:
    for mod, names in GROUPS.items():
        if name in names:
            assigned.setdefault(mod, []).append((name, mlines))
            break
    else:
        if name not in KEEP:
            raise SystemExit("方法未分组: %s" % name)
        assigned.setdefault("_keep", []).append((name, mlines))

MIXIN_HEADER = '''# -*- coding: utf-8 -*-
"""%(title)s Mixin (自 app_gui.py 拆分)"""
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


'''

import os
os.makedirs("gui", exist_ok=True)
with open("gui/__init__.py", "w", encoding="utf-8") as f:
    f.write("")

# theme.py
with open("gui/theme.py", "w", encoding="utf-8") as f:
    f.write('# -*- coding: utf-8 -*-\n"""深色主题常量 (自 app_gui.py 拆分)"""\n\n')
    f.writelines(theme)

camel = lambda s: "".join(w.capitalize() for w in s.split("_"))  # noqa: E731

for mod, items in assigned.items():
    if mod == "_keep":
        continue
    cls = camel(mod) + "Mixin"
    with open("gui/%s.py" % mod, "w", encoding="utf-8") as f:
        f.write(MIXIN_HEADER % {"title": TITLES[mod]})
        f.write("class %s:\n" % cls)
        for name, mlines in items:
            f.writelines(mlines)
            f.write("\n")
    print("写入 gui/%s.py (%d 方法)" % (mod, len(items)))

# 新 app_gui.py
mixins = [(mod, camel(mod) + "Mixin") for mod in GROUPS]
out = list(header)
out.append("from gui.theme import *  # noqa: F401,F403\n")
for mod, cls in mixins:
    out.append("from gui.%s import %s  # noqa: F401\n" % (mod, cls))
out.append("\n\n")
out.append("class App(%s, tk.Tk):\n" % ", ".join(cls for _, cls in mixins))
for name, mlines in assigned["_keep"]:
    out.extend(mlines)
    out.append("\n")
out.append("\n")
out.extend(footer)
with open(SRC, "w", encoding="utf-8") as f:
    f.writelines(out)
print("重写 app_gui.py (保留 %d 方法 + %d Mixin)" % (len(assigned["_keep"]), len(mixins)))
