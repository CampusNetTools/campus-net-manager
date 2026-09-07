# -*- coding: utf-8 -*-
"""v5.0.7 全界面按钮级真实点击审计。

方法: 驱动 App 实例, 遍历主窗 + 各功能窗口内所有 Button,
用 Quartz 合成鼠标真实点击(等价用户点击), 按 4 类可观测响应判定:
  window=点击后出现新窗口 / toggle=按钮文字翻转 / log=运行日志新增 /
  text=任意 Text/Label 内容变化
均无 → 记为 DEAD(疑似无效按钮)。
危险/外跳/阻塞类按钮(删除/退出/下载/开网页/文件对话框等)按 DENY 跳过。
结果输出: /tmp/click_audit.json
"""
import sys, os, time, json, subprocess
sys.path.insert(0, "/Users/nanyu/Desktop/校园连接助手")
os.chdir("/Users/nanyu/Desktop/校园连接助手")

import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as mb
import tkinter.filedialog as fd
import webbrowser
import Quartz

# 审计模式下弹窗全部自动应答: 不阻塞点击流, 便于逐按钮判定
mb.showinfo = lambda *a, **k: "ok"
mb.showerror = lambda *a, **k: None
mb.showwarning = lambda *a, **k: "ok"
mb.askyesno = lambda *a, **k: True
mb.askokcancel = lambda *a, **k: True
mb.askquestion = lambda *a, **k: "yes"
fd.askopenfilename = lambda **k: ""
fd.asksaveasfilename = lambda **k: ""
webbrowser.open = lambda *a, **k: True

from app_gui import App

app = None
Q = []          # 待执行队列: ("click", widget) / ("open", name, builder) / ("end",)
RESULTS = []
SKIPPED = []

DENY_EXACT = {"删除", "新建", "退出", "取消", "完成", "稍后", "跳过此版本", "立即更新",
              "导入配置", "导出配置", "更改", "导出诊断", "报告导出", "停止共享",
              "保存并应用", "开始测速", "开始", "重新测速", "一键部署", "立即检查"}
DENY_SUB = ("删除", "退出", "停止", "下载固件", "打开厂商", "OpenWrt", "去 Release",
            "打开 WiFi", "打开路由器", "打开 macOS", "打开热点", "一键部署",
            "导入", "导出", "电脑地址", "开始测速", "下载", "立即更新")

NAV = [  # 右栏导航: (按钮文字子串, fwin 名)
    ("路由器中继", "router_relay"), ("路由器代理", "router_proxy"),
    ("路由器检测", "router"), ("网络测速", "speed"),
    ("新手向导", "wizard"), ("偏好设置", "prefs"),
]


def esc():
    # Escape(53) 关不掉单 OK 的 NSAlert; 再补 Return(36) 触发默认按钮
    for key in (53, 36):
        for down in (True, False):
            e = Quartz.CGEventCreateKeyboardEvent(None, key, down)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
            time.sleep(0.04)


def click(w):
    try:
        w.update_idletasks()
        x = w.winfo_rootx() + w.winfo_width() // 2
        y = w.winfo_rooty() + w.winfo_height() // 2
    except Exception:
        return
    for t, d in ((Quartz.kCGEventMouseMoved, None),
                 (Quartz.kCGEventLeftMouseDown, None),
                 (Quartz.kCGEventLeftMouseUp, None)):
        e = Quartz.CGEventCreateMouseEvent(None, t, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
        time.sleep(0.06)


def all_btns(win):
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, (tk.Button, ttk.Button)) and c not in out:
                out.append(c)
            walk(c)
    walk(win)
    return out


def toplevels():
    return [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)]


def snapshot():
    app.update()
    tops = {id(w): (w.title() if hasattr(w, 'title') else '') for w in toplevels()}
    try:
        log = app.txt_log.get("1.0", "end")
    except Exception:
        log = ""
    texts = {}
    def walk(w):
        for c in w.winfo_children():
            cn = type(c).__name__
            if cn in ("Text",):
                try:
                    texts[str(c)] = c.get("1.0", "end")
                except Exception:
                    pass
            elif cn in ("Label", "TLabel"):
                try:
                    texts[str(c)] = c.cget("text")
                except Exception:
                    pass
            walk(c)
    walk(app)
    return tops, len(log), texts


def parent_toplevel(w):
    p = w.winfo_toplevel()
    return p


def audit_button(btn):
    try:
        if str(btn.cget("state")) == "disabled":
            return "disabled", ""
        if not btn.winfo_ismapped():
            return "skip-unmapped", ""
        text = str(btn.cget("text"))
    except Exception:
        return "gone", ""
    if text in DENY_EXACT or any(d in text for d in DENY_SUB):
        return "skip-denied", text
    # 已处理过同一实例
    if getattr(btn, "_audited", False):
        return "skip-dup", text
    btn._audited = True

    top = parent_toplevel(btn)
    try:
        top.attributes("-topmost", True); top.lift()
    except Exception:
        pass
    app.update()
    pre_tops, pre_log, pre_texts = snapshot()
    click(btn)
    deadline = time.time() + 2.6
    resp = "DEAD"
    note = ""
    while time.time() < deadline:
        app.update()
        time.sleep(0.15)
        post_tops, post_log, post_texts = snapshot()
        new_tops = [t for k, t in post_tops.items() if k not in pre_tops]
        if new_tops:
            resp = "OK-window"; note = new_tops[0]
            break
        if post_log > pre_log:
            resp = "OK-log"; break
        if str(btn.cget("text")) != text:
            resp = "OK-toggle"; break
        for k, v in post_texts.items():
            if pre_texts.get(k) != v and len(v) > 0:
                resp = "OK-content"; break
        if resp != "DEAD":
            break
    # 清理弹出的对话框/新窗口(保留原功能窗口)
    post_tops, _, _ = snapshot()
    for k, title in post_tops.items():
        if k not in pre_tops:
            for w in toplevels():
                if id(w) in post_tops and (w.title() if hasattr(w,'title') else '') == title and title not in (
                        "隧道共享",):
                    try:
                        w.destroy()
                    except Exception:
                        pass
    esc(); app.update()
    return resp, note


def scan_window(win, label):
    for b in all_btns(win):
        resp, note = audit_button(b)
        try:
            t = str(b.cget("text"))[:36]
        except Exception:
            t = "?"
        entry = {"win": label, "btn": t, "result": resp, "note": str(note)[:40]}
        if resp.startswith("skip"):
            SKIPPED.append(entry)
        else:
            RESULTS.append(entry)
            print("BTN %-22s %-12s %s" % (t, resp, note), flush=True)


def clean_stale_fwin():
    try:
        for k in list(app._fwin_map):
            if not app._fwin_map[k].winfo_exists():
                app._fwin_map.pop(k, None)
    except Exception:
        pass


def t_main():
    print("== pass1: main window ==", flush=True)
    scan_window(app, "main")
    # 依次打开各功能窗口并扫描其内部按钮
    queue = list(NAV)
    def next_win():
        if not queue:
            print("== done ==", flush=True)
            with open("/tmp/click_audit.json", "w", encoding="utf-8") as f:
                json.dump({"results": RESULTS, "skipped": SKIPPED}, f,
                          ensure_ascii=False, indent=1)
            os._exit(0)
        text_sub, name = queue.pop(0)
        btn = None
        for b in all_btns(app):
            try:
                if text_sub in str(b.cget("text")) and not str(b.cget("text")).startswith("路由器 LAN"):
                    btn = b; break
            except Exception:
                pass
        if btn is None:
            print("MISS nav", text_sub, flush=True)
            app.after(100, next_win); return
        pre = {id(w) for w in toplevels()}
        click(btn)
        app.update(); time.sleep(1.0); app.update()
        new = [w for w in toplevels() if id(w) not in pre]
        clean_stale_fwin()
        if not new:
            print("NAV-DEAD", text_sub, flush=True)
            RESULTS.append({"win": "nav", "btn": text_sub, "result": "DEAD", "note": ""})
            app.after(150, next_win); return
        win = new[-1]
        RESULTS.append({"win": "nav", "btn": text_sub, "result": "OK-window",
                        "note": (win.title() if hasattr(win, "title") else "")[:40]})
        print("NAV %-10s OK" % text_sub, flush=True)
        scan_window(win, name or text_sub)
        try:
            win.destroy()
        except Exception:
            pass
        clean_stale_fwin()
        app.update()
        app.after(300, next_win)
    next_win()


app = App()
app.report_callback_exception = lambda et, ev, tb: print(
    'CB-EXC %s: %s' % (et.__name__, ev), flush=True)
app.after(1200, t_main)
app.mainloop()
