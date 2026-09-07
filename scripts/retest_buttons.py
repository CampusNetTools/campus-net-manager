# -*- coding: utf-8 -*-
"""v5.0.8 针对性复测: 上轮审计可疑 DEAD 按钮逐个复测(等待 5s + 截图)。"""
import sys, os, time, json, subprocess
sys.path.insert(0, "/Users/nanyu/Desktop/校园连接助手")
os.chdir("/Users/nanyu/Desktop/校园连接助手")

import tkinter as tk
import Quartz
from app_gui import App

app = None
OUT = {}

def esc():
    for key in (53, 36):
        for down in (True, False):
            e = Quartz.CGEventCreateKeyboardEvent(None, key, down)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
            time.sleep(0.04)

def click(w):
    w.update_idletasks()
    x = w.winfo_rootx() + w.winfo_width() // 2
    y = w.winfo_rooty() + w.winfo_height() // 2
    for t in (Quartz.kCGEventMouseMoved, Quartz.kCGEventLeftMouseDown,
              Quartz.kCGEventLeftMouseUp):
        e = Quartz.CGEventCreateMouseEvent(None, t, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
        time.sleep(0.06)

def find_btn(win, sub):
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, (tk.Button, tk.ttk.Button)):
                try:
                    if sub in str(c.cget("text")):
                        return c
                except Exception:
                    pass
            r = walk(c)
            if r is not None:
                return r
    r = walk(win)
    return r if r is not None else (None if True else None)

def walk_all(win):
    for c in win.winfo_children():
        yield c
        yield from walk_all(c)

def find_btn2(win, sub):
    for c in walk_all(win):
        if isinstance(c, (tk.Button, tk.ttk.Button)):
            try:
                if sub in str(c.cget("text")):
                    return c
            except Exception:
                pass

def snapshot():
    app.update()
    tops = [w.title() for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
    try:
        log = app.txt_log.get("1.0", "end")
    except Exception:
        log = ""
    texts = {}
    for c in walk_all(app):
        cn = type(c).__name__
        if cn == "Text":
            try:
                texts[str(c)] = c.get("1.0", "end")
            except Exception:
                pass
    return tops, len(log), texts

def retest(label, open_fn, btn_text, wait=5.0, shot=None):
    def job():
        pre_tops, pre_log, pre_texts = snapshot()
        if open_fn:
            open_fn()
        app.update(); time.sleep(0.8); app.update()
        # 在(可能新开的)窗口里找按钮
        target_root = None
        tops = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]
        for w in [app] + tops:
            b = find_btn2(w, btn_text)
            if b is not None and b.winfo_ismapped():
                target_root = w
                break
        if target_root is None:
            OUT[label] = {"result": "BTN-NOT-FOUND"}
            app.after(200, lambda: done(shot))
            return
        target_root.attributes("-topmost", True); target_root.lift()
        app.update()
        pre2_log = snapshot()[1]
        b = find_btn2(target_root, btn_text)
        click(b)
        deadline = time.time() + wait
        result = "DEAD"
        note = ""
        while time.time() < deadline:
            app.update(); time.sleep(0.2)
            tops, log, texts = snapshot()
            if log > pre2_log:
                result, note = "OK-log", ""; break
            try:
                if str(b.cget("text")) != btn_text:
                    result, note = "OK-toggle", ""; break
            except Exception:
                pass
            new_t = [t for t in tops if t not in pre_tops]
            if new_t:
                result, note = "OK-window", new_t[0]; break
            for k, v in texts.items():
                if pre_texts.get(k) != v and v.strip():
                    result, note = "OK-content", v[:40].replace("\n", " "); break
            if result != "DEAD":
                break
        if shot and result == "DEAD":
            subprocess.run(["screencapture", "-x", shot])
        OUT[label] = {"result": result, "note": note}
        print(label, "->", result, note, flush=True)
        done(shot)

    def done(shot):
        app.after(300, next_job)

    return job

JOBS = []

def next_job():
    if JOBS:
        j = JOBS.pop(0)
        app.after(400, j)
    else:
        print(json.dumps(OUT, ensure_ascii=False, indent=1), flush=True)
        os._exit(0)

def start():
    app.report_callback_exception = lambda et, ev, tb: print(
        "CB-EXC %s: %s" % (et.__name__, ev), flush=True)
    JOBS.extend([
        retest("main-展开", None, "展开", wait=3.0),
        retest("prefs-使用帮助", app.show_preferences, "使用帮助"),
        retest("prefs-保存设置", app.show_preferences, "保存设置", wait=4.0),
        retest("proxy-生成PAC", app.show_router_proxy_window, "生成 PAC", wait=8.0,
               shot="/tmp/retest_genpac.png"),
        retest("relay-生成分步路径", app.show_router_relay_window, "生成分步路径",
               wait=8.0, shot="/tmp/retest_genpath.png"),
        retest("relay-查询官方适配", app.show_router_relay_window, "查询官方适配",
               wait=8.0, shot="/tmp/retest_lookup.png"),
        retest("wizard-C隧道共享", app.show_wizard, "C：隧道共享", wait=6.0),
    ])
    next_job()

app = App()
app.report_callback_exception = lambda et, ev, tb: print(
    "CB-EXC %s: %s" % (et.__name__, ev), flush=True)
app.after(1500, start)
app.mainloop()
