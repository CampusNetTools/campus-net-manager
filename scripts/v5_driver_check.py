# -*- coding: utf-8 -*-
"""v5.0.0 实机驱动验证: 像用户一样逐个打开功能窗口, 并对每个窗口做裁切审计。

审计规则:
  - 文本类控件(Label/Button/Entry/Combobox/Checkbutton): winfo_width() < winfo_reqwidth()-2 → 文字被截断
  - 任何控件超出窗口可视边界 → 被裁切
输出: JSON 结果到 /tmp/v5_driver_result.json
"""
import json
import os
import socket
import sys
import time
import urllib.request

sys.path.insert(0, "/Users/nanyu/Desktop/校园连接助手")
os.chdir("/Users/nanyu/Desktop/校园连接助手")

import tkinter as tk  # noqa: E402
import shared_proxy  # noqa: E402

RESULTS = {"steps": [], "clipped_windows": {}, "proxy_test": None, "errors": []}

TEXT_WIDGETS = (tk.Label, ttk.Label if False else object())  # placeholder, real check below


def _is_text_widget(w):
    cn = type(w).__name__
    return cn in ("Label", "TLabel", "Button", "TButton", "Entry", "TEntry",
                  "Combobox", "TCombobox", "Checkbutton", "TCheckbutton",
                  "Radiobutton", "TRadiobutton")


def _all_descendants(w):
    out = []
    for c in w.winfo_children():
        out.append(c)
        out.extend(_all_descendants(c))
    return out


def audit_window(app, win, name):
    """审计一个窗口(含 Toplevel): 找出文字截断与越界控件。"""
    issues = []
    try:
        win.update_idletasks()
        wx, wy = win.winfo_rootx(), win.winfo_rooty()
        ww, wh = win.winfo_width(), win.winfo_height()
    except Exception as e:
        return {"error": str(e)}
    for wdg in _all_descendants(win):
        try:
            if not wdg.winfo_ismapped():
                continue
            cn = type(wdg).__name__
            # 文字截断检查
            if _is_text_widget(wdg):
                actual_w = wdg.winfo_width()
                req_w = wdg.winfo_reqwidth()
                actual_h = wdg.winfo_height()
                req_h = wdg.winfo_reqheight()
                txt = ""
                try:
                    txt = str(wdg.cget("text"))[:40]
                except Exception:
                    try:
                        txt = wdg.get()[:40] if hasattr(wdg, "get") else ""
                    except Exception:
                        txt = ""
                if actual_w > 1 and req_w > actual_w + 2:
                    issues.append({"kind": "text_clipped_w", "widget": cn,
                                   "text": txt, "actual": actual_w, "need": req_w})
                if actual_h > 1 and req_h > actual_h + 6:
                    issues.append({"kind": "text_clipped_h", "widget": cn,
                                   "text": txt, "actual": actual_h, "need": req_h})
            # 越界检查(相对窗口可视区)
            x = wdg.winfo_rootx() - wx
            y = wdg.winfo_rooty() - wy
            if x + wdg.winfo_width() > ww + 4 or y + wdg.winfo_height() > wh + 4:
                issues.append({"kind": "out_of_bounds", "widget": cn,
                               "x": x, "y": y,
                               "w": wdg.winfo_width(), "h": wdg.winfo_height(),
                               "win_w": ww, "win_h": wh})
        except Exception:
            continue
    RESULTS["clipped_windows"][name] = {"win_size": [ww, wh], "issues": issues,
                                        "issue_count": len(issues)}
    return issues


def step(app, title, fn):
    try:
        fn()
        RESULTS["steps"].append({"step": title, "ok": True})
    except Exception as e:
        RESULTS["steps"].append({"step": title, "ok": False, "error": repr(e)})
        RESULTS["errors"].append("%s: %r" % (title, e))


def find_toplevels(app):
    return [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]


def main():
    from app_gui import App
    app = App()

    def t1():
        app.update()
        time.sleep(1.0)
        app.update()
        audit_window(app, app, "main_window")
    app.after(600, t1)

    def t2():
        # 用户点「隧道共享」
        step(app, "toggle_share", app.toggle_share)

        def after_share():
            app.update()
            toplevels = find_toplevels(app)
            RESULTS["steps"].append({"step": "tunnel_window_opened",
                                     "ok": bool(toplevels),
                                     "count": len(toplevels)})
            for w in toplevels:
                audit_window(app, w, "tunnel_ready_window")
            # 端口监听
            listening = False
            s = socket.socket()
            s.settimeout(1)
            try:
                s.connect(("127.0.0.1", 8080))
                listening = True
            except Exception:
                pass
            finally:
                s.close()
            RESULTS["steps"].append({"step": "port_8080_listening", "ok": listening})
            # 走代理访问外网 (模拟手机流量, 不带 X-Shared-Key — v5 默认无口令)
            try:
                ips = shared_proxy.get_lan_ips()
                proxy_ip = ips[0] if ips else "127.0.0.1"
                handler = urllib.request.ProxyHandler(
                    {"http": "http://%s:8080" % proxy_ip})
                opener = urllib.request.build_opener(handler)
                req = urllib.request.Request(
                    "http://connect.rom.miui.com/generate_204",
                    headers={"User-Agent": "v5-driver"})
                resp = opener.open(req, timeout=10)
                RESULTS["proxy_test"] = {"ok": True, "code": resp.status,
                                         "via": proxy_ip}
            except Exception as e:
                RESULTS["proxy_test"] = {"ok": False, "error": repr(e)}
            # 关闭隧道
            step(app, "stop_share", app._stop_share)
        app.after(1200, after_share)

    app.after(1800, t2)

    def t3():
        # 打开各功能窗口并审计
        def open_audit(builder, name):
            def _f():
                before = {id(w) for w in find_toplevels(app)}
                builder()
                app.update()
                time.sleep(0.4)
                app.update()
                new = [w for w in find_toplevels(app) if id(w) not in before]
                RESULTS["steps"].append({"step": "open_" + name,
                                         "ok": bool(new)})
                if new:
                    audit_window(app, new[-1], name)
                    try:
                        new[-1].destroy()
                        app.update()
                    except Exception:
                        pass
            return _f
        step(app, "open_router_assessment",
             open_audit(app.show_router_assessment, "router_assessment"))
        step(app, "open_speed", open_audit(app.show_speed_test, "speed_window"))
        step(app, "open_wizard", open_audit(app.show_wizard, "wizard_window"))
        step(app, "open_prefs", open_audit(app.show_preferences, "prefs_window"))
        step(app, "open_relay", open_audit(app.show_router_relay_window, "relay_window"))
    app.after(5200, t3)

    def t4():
        # 日志展开/收起 + VPN 预设 + 档案类型切换
        def log_toggle():
            step(app, "log_expand", app._toggle_log)
            app.update()
            audit_window(app, app, "main_log_expanded")
            step(app, "log_collapse", app._toggle_log)
            app.update()
        step(app, "log_section", log_toggle)

        def vpn():
            step(app, "vpn_preset", app._vpn_preset_local)
            app.update()
            RESULTS["steps"].append({
                "step": "vpn_status_label",
                "ok": "已启用" in str(app.lbl_vpn.cget("text"))})
            step(app, "vpn_disable", app._vpn_disable)
            app.update()
            RESULTS["steps"].append({
                "step": "vpn_disabled_label",
                "ok": "未启用" in str(app.lbl_vpn.cget("text"))})
        step(app, "vpn_section", vpn)

        def ptype_switch():
            app.cmb_ptype.set("普通WiFi/热点（只检测断网）")
            app._profile_rebuild_form()
            app.update()
            audit_window(app, app, "main_wifi_form")
            app.cmb_ptype.set("校园网认证（登录保活）")
            app._profile_rebuild_form()
            app.update()
            audit_window(app, app, "main_campus_form")
        step(app, "ptype_switch", ptype_switch)
    app.after(11500, t4)

    def t9():
        with open("/tmp/v5_driver_result.json", "w", encoding="utf-8") as f:
            json.dump(RESULTS, f, ensure_ascii=False, indent=1)
        try:
            app.on_close()
        except Exception:
            pass
        try:
            app.destroy()
        except Exception:
            pass
        os._exit(0)
    app.after(15000, t9)

    app.mainloop()


if __name__ == "__main__":
    main()
