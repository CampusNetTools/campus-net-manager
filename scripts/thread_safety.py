# -*- coding: utf-8 -*-
"""工作线程里的 tkinter 调用检查器（v5.4.3）。

用途
----
静态找出"**真的会在工作线程里执行**的 tkinter 调用"。tkinter 不是线程安全的:
从工作线程碰控件(mainloop 没跑、或窗口已 destroy 时)会抛
``RuntimeError: main thread is not in main loop``, 轻则这次界面更新被静默丢掉,
重则异常顺着工作线程冒出去把业务逻辑带崩。

本机实测(Tk 8.6 / Python 3.11):

  ====================================  ==================================
  场景                                  工作线程里 widget.after / configure
  ====================================  ==================================
  mainloop 正在跑(窗口开着)             不抛异常(200 次全过), 但属"碰巧能用"
  没有 mainloop(初始化/测试)            RuntimeError
  窗口已 destroy() 之后                 RuntimeError
  ====================================  ==================================

怎么用
------
    python scripts/thread_safety.py            # 扫描全仓库, 有问题则退出码 1
    from scripts.thread_safety import scan     # 供测试调用

判定要点(三条都踩过坑, 别删)
----------------------------
1. 本仓库 worker 多是**方法内嵌的嵌套函数**, 且入口常写成
   ``Thread(target=self.method)`` → 必须建"作用域树含 ClassDef", 否则漏检/0 命中;
2. 传给 ``self._clash_ui(lambda: ...)`` / ``widget.after(...)`` 的回调是在**主线程**
   执行的 → 绝不能下钻, 否则一片误报(DEFER_HINTS);
3. 传给 ``pool.map(lambda ...)`` 的 lambda 在线程池里跑 → 必须下钻(POOL_HINTS)。
"""
import ast
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TK_METHODS = {
    "after", "after_idle", "after_cancel", "winfo_exists", "winfo_width",
    "winfo_height", "winfo_reqwidth", "destroy", "deiconify", "iconify", "lift",
    "focus_force", "focus_set", "configure", "config", "update",
    "update_idletasks", "clipboard_clear", "clipboard_append", "selection",
    "selection_set", "see", "insert", "delete", "item", "heading", "column",
    "bind", "unbind", "protocol", "geometry", "title", "mainloop", "wait_window",
    "grab_set", "grab_release", "transient", "attributes", "state",
    "get_children", "exists", "yview", "grid", "pack", "place", "tk",
    "winfo_children",
}
TK_MODULES = {"messagebox", "simpledialog", "filedialog", "colorchooser"}

# 把回调"甩回主线程"的调用: 其参数里的回调不能算作工作线程可达
DEFER_HINTS = ("_ui", "after", "after_idle", "post", "defer", "schedule", "submit_ui")
# 在线程池里跑回调的调用: 其参数里的 lambda 必须下钻
POOL_HINTS = ("map", "submit", "imap", "starmap")

# tkinter 的方法名和别的东西大量重名: socket.bind / dict.update / list.insert /
# bytes.delete 都不存在但自定义类常有。所以除了方法名, 还要看**接收者像不像控件**:
#   - 直接写在 self 上(self.configure)            → 算
#   - 写在 self.xxx 上且 xxx 像控件名(self.lbl)   → 算
#   - 其它局部名(s.bind / profile.update)          → 需要名字里有控件词根才算
# 宁可少报也不误报: 这个检查器是 CI 卡口, 误报会直接挡掉正常提交。
WIDGET_HINTS = (
    "lbl", "label", "btn", "button", "entry", "tree", "box", "text", "bar",
    "status", "frame", "card", "canvas", "listbox", "combo", "scroll", "win",
    "root", "top", "body", "title", "wrap", "panel", "summary", "head",
    "detail", "acts", "filt", "tabs", "grid", "dialog", "popup", "menu",
)

SKIP_DIRS = {".git", "__pycache__", "dist", "build", ".workbuddy"}


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def looks_like_widget(receiver):
    """判断 `receiver.method(...)` 里的 receiver 像不像 tkinter 控件。"""
    if receiver is None:
        return False
    if receiver == "self":
        return True
    tail = receiver.split(".")[-1].lower()
    return any(h in tail for h in WIDGET_HINTS)


def tk_call_reason(callee):
    """返回这条调用被判为"碰 tkinter"的原因; 不算则返回 None。"""
    if not callee or "." not in callee:
        return None
    head = callee.split(".")[0]
    if head in TK_MODULES:
        return "弹窗(阻塞主线程)"
    parts = callee.split(".")
    method = parts[-1]
    if method not in TK_METHODS:
        return None
    receiver = ".".join(parts[:-1])
    if looks_like_widget(receiver):
        return "tkinter 方法"
    return None


def is_defer(callee):
    if not callee:
        return False
    name = callee.split(".")[-1]
    return any(name == h or name.endswith(h) for h in DEFER_HINTS)


def is_pool(callee):
    return bool(callee) and callee.split(".")[-1] in POOL_HINTS


def _contains(outer, inner):
    return any(n is inner for n in ast.walk(outer))


def _depth(scope):
    d = 0
    while scope is not None:
        d += 1
        scope = scope["parent"]
    return d


class Analyzer:
    """对单个模块做"工作线程可达的 tkinter 调用"分析。"""

    def __init__(self, tree):
        self.tree = tree
        self.scopes = []

    # ------------------------------------------------------------- 作用域树
    def build(self):
        self.scopes.append({"node": self.tree, "parent": None,
                            "name": "<module>", "defs": {}})
        self._index(self.tree, self.scopes[0])

    def _index(self, node, scope):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                sub = self._mk(child, scope, "<class %s>" % child.name)
                self._index(child, sub)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sub = self._mk(child, scope, child.name)
                scope["defs"].setdefault(child.name, sub)
                sub["defs"][child.name] = sub
                self._index(child, sub)
            elif isinstance(child, ast.Lambda):
                self._index(child, self._mk(child, scope, "<lambda>"))
            else:
                self._index(child, scope)

    def _mk(self, node, parent, name):
        sc = {"node": node, "parent": parent, "name": name, "defs": {}}
        self.scopes.append(sc)
        return sc

    def resolve(self, scope, name):
        while scope is not None:
            if name in scope["defs"]:
                return scope["defs"][name]
            scope = scope["parent"]
        return None

    def scope_of(self, target):
        for sc in self.scopes:
            if sc["node"] is target:
                return sc
        return None

    def enclosing(self, target):
        best = None
        for sc in self.scopes:
            if sc["node"] is self.tree or not _contains(sc["node"], target):
                continue
            if best is None or _depth(sc) > _depth(best):
                best = sc
        return best

    # --------------------------------------------------------------- 遍历
    def calls_of(self, scope):
        """收集作用域函数体里的 Call; 不下钻嵌套 def, 按规则决定是否下钻 lambda。"""
        out = []
        node = scope["node"]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack = list(node.body)
        elif isinstance(node, ast.Lambda):
            stack = [node.body]
        else:
            stack = list(node.body)
        while stack:
            cur = stack.pop()
            if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(cur, ast.Lambda):
                continue                      # lambda 作为独立作用域处理
            if isinstance(cur, ast.Call):
                out.append(cur)
            stack.extend(ast.iter_child_nodes(cur))
        return out

    def reachable(self, scope):
        seen, out, stack = set(), [], [scope]
        while stack:
            sc = stack.pop()
            if id(sc) in seen:
                continue
            seen.add(id(sc))
            out.append(sc)
            for call in self.calls_of(sc):
                # 只有裸名字调用 Name(...) 才可能指到局部/闭包函数;
                # x.y(...) 是属性调用, 不能解析成同名的兄弟函数(会误报)。
                if isinstance(call.func, ast.Name):
                    sub = self.resolve(sc, call.func.id)
                    if sub is not None:
                        stack.append(sub)
                callee = dotted(call.func)
                if is_pool(callee):
                    args = list(call.args) + [k.value for k in call.keywords
                                              if k.arg is None]
                    for arg in args:
                        if isinstance(arg, ast.Lambda):
                            sub = self.scope_of(arg)
                            if sub is not None:
                                stack.append(sub)
        return out

    def tk_hits(self, scopes):
        hits = {}
        for sc in scopes:
            for call in self.calls_of(sc):
                callee = dotted(call.func)
                if not callee or is_defer(callee):
                    continue
                why = tk_call_reason(callee)
                if why:
                    hits.setdefault((callee, why, sc["name"]), call.lineno)
        return hits

    def entries(self):
        """找出所有 Thread(target=...) 的 worker 入口。"""
        out = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call):
                continue
            callee = dotted(node.func) or ""
            if not (callee == "Thread" or callee.endswith("Thread")):
                continue
            for kw in node.keywords:
                if kw.arg != "target":
                    continue
                tgt = kw.value
                env = self.enclosing(node)
                if isinstance(tgt, ast.Name):
                    defn = self.resolve(env, tgt.id) if env else None
                    label = tgt.id
                elif isinstance(tgt, ast.Attribute):
                    nm = dotted(tgt)
                    defn = self.resolve(env, nm.split(".")[-1]) if env else None
                    label = nm
                elif isinstance(tgt, ast.Lambda):
                    defn, label = self.scope_of(tgt), "<lambda>"
                else:
                    defn, label = None, "?"
                out.append((label, node.lineno, defn))
        return out

    def report(self):
        rows = []
        for label, lineno, defn in self.entries():
            if defn is None:
                continue
            for (call, why, owner), ln in self.tk_hits(self.reachable(defn)).items():
                rows.append((lineno, label, ln, owner, call, why))
        return rows


def scan_file(path, rel=None):
    rel = rel or path
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (OSError, SyntaxError):
        return []
    an = Analyzer(tree)
    an.build()
    return [(rel,) + row for row in an.report()]


def iter_py(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if name.endswith(".py"):
                yield os.path.join(base, name)


def scan(root=REPO_ROOT):
    """扫描整棵代码树, 返回 [(相对路径, 入口行, 入口名, 命中行, 所在函数, 调用, 原因)]。"""
    out = []
    for path in iter_py(root):
        rel = os.path.relpath(path, root)
        out.extend(scan_file(path, rel))
    return out


def scan_source(source, name="<fixture>"):
    """扫描一段源码字符串(给测试用的自检夹具)。"""
    tree = ast.parse(source, filename=name)
    an = Analyzer(tree)
    an.build()
    return an.report()


def main():
    rows = scan()
    if not rows:
        print("OK: 没有发现工作线程里的 tkinter 调用")
        return 0
    print("发现 %d 处工作线程里的 tkinter 调用:" % len(rows))
    for rel, entry_ln, label, ln, owner, call, why in rows:
        print("  %s:%d  %s() 在 worker %s(第 %d 行启动) 里调用 %s  [%s]"
              % (rel, ln, owner, label, entry_ln, call, why))
    print("\n修法: 把这次 UI 更新换成 gui.ui_dispatch.post(self, fn) —— 它只做一次"
          "\n受保护的 after 投递, 绝不抛异常; 需要保证顺序/过滤旧窗口时用队列 + 主线程泵"
          "\n(见 gui/clash_nodes_ui.py 的 _clash_ui / _clash_pump)。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
