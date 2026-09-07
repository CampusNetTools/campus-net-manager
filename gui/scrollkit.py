# -*- coding: utf-8 -*-
"""小屏适配工具: 窗口高度钳制 + 纵向滚动容器 (v5.0.1)。

背景: 13/14 寸 Mac 逻辑分辨率下, 应用可视高度往往只有 650-700px,
窗口若按设计高度(780-880)打开, 底部内容会被截在屏幕外, 无法到达。
- fit_geometry: 把窗口打开高度钳制到屏幕可视区, 超出部分交给内部滚动。
- make_scrollable: 把窗口内容装进纵向滚动容器, 任何屏幕高度都能触达全部控件。
"""
import tkinter as tk
from tkinter import ttk


def fit_geometry(win, w, h, min_h=480, reserve=110):
    """返回钳制后的 "WxH" geometry 字符串。

    reserve: 菜单栏 + Dock + 标题栏 + 安全边距的预算。
    min_h:  下限, 防止在超大屏上被意外压扁(一般用不到)。
    """
    try:
        sh = win.winfo_screenheight()
    except Exception:
        return "%dx%d" % (w, h)
    h2 = min(h, max(min_h, sh - reserve))
    return "%dx%d" % (w, h2)


def make_scrollable(win, pad=(24, 22), inner_bg_style="Card.TFrame",
                    wheel_targets=("Frame", "TFrame", "Label", "TLabel",
                                   "Checkbutton", "TCheckbutton",
                                   "Radiobutton", "TRadiobutton")):
    """把 win 变成纵向滚动窗口, 返回内容 frame (后续控件 pack/grid 到它上面)。

    - 内容宽度自动跟随窗口宽度。
    - 滚轮: 在空白/标签/勾选框上滚动页面; Entry/Text/Combobox/Button 上保持原生行为
      (Text 自带滚动, Combobox 滚轮切值, 避免双滚动打架)。
    """
    try:
        bg = win.cget("bg")          # tk.Toplevel / tk.Frame 有 bg
    except Exception:
        from gui.theme import BG     # ttk.Frame 走样式, 取主题底色
        bg = BG
    canvas = tk.Canvas(win, bg=bg, highlightthickness=0)
    sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas, style=inner_bg_style, padding=pad)
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_canvas_conf(e):
        canvas.itemconfigure(win_id, width=e.width)
    canvas.bind("<Configure>", _on_canvas_conf)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    def _wheel(e):
        try:
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        except Exception:
            pass
        return "break"
    canvas.bind("<MouseWheel>", _wheel)
    inner.bind("<MouseWheel>", _wheel)

    def _bind_tree(w):
        for c in w.winfo_children():
            try:
                if type(c).__name__ in wheel_targets:
                    c.bind("<MouseWheel>", _wheel)
            except Exception:
                pass
            _bind_tree(c)
    # 延迟绑定: 等调用方把内容塞进 inner 之后再遍历
    win.after(250, lambda: _bind_tree(inner))
    win.after(900, lambda: _bind_tree(inner))
    return inner
