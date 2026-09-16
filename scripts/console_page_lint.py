# -*- coding: utf-8 -*-
"""路由器工作台页面检查器 (v5.4.4)。

背景
----
``router_assets/console-index.html`` 是浏览器里访问 ``http://<路由器>:8088`` 看到的
工作台。它曾经**根本不在仓库里** —— 只在路由器上存在, 于是:
  * 后端 ``action.sh`` 陆续加了 ``enable_transparent`` / ``disable_transparent`` /
    ``rotate_node``, 页面却一直停在 7 个动作, 新功能在 Web 上完全没有入口;
  * 页面改坏了没有回滚来源, 部署也没有校验。

这个检查器把"页面与后端必须一致"变成可自动验证的约束。

检查项
------
1. HTML 标签配对
2. JS 语法 (``node --check``; 环境里没有 node 时跳过而不是判失败)
3. **页面调用的动作 ⊆ action.sh 的 case 分支** —— 防"按钮调了个后端不认识的 op"
4. **后端支持的动作 ⊆ 页面入口** —— 防"后端加了口子但页面没暴露"(本次踩的坑)
5. JS 引用的元素 id 都在 HTML 里定义
6. 动作名有中文映射(确认框里不能露出 ``enable_transparent`` 这种内部名)

用法
----
    python scripts/console_page_lint.py          # 有问题则退出码 1
    from scripts.console_page_lint import lint   # 供测试调用
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser

# GitHub 的 Windows runner 默认 stdout 编码是 cp1252 —— 直接 print 中文会抛
# UnicodeEncodeError, 脚本以非 0 退出, CI 步骤判失败(而同一份逻辑在单测里是通过的,
# 因为 unittest 不往 stdout 打中文)。统一改成 UTF-8。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PAGE = os.path.join(REPO_ROOT, "router_assets", "console-index.html")
DEFAULT_ACTION = os.path.join(REPO_ROOT, "router_assets", "console-action.sh")

NODE = (os.environ.get("NODE_BIN") or shutil.which("node")
        or r"C:\Users\lugua\.workbuddy\binaries\node\versions\22.22.2-2\node.exe")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class _Pair(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append("第 %d 行 </%s> 没有对应的开始标签" % (self.getpos()[0], tag))
            return
        top, line = self.stack.pop()
        if top != tag:
            self.errors.append("第 %d 行 </%s> 与第 %d 行 <%s> 不匹配"
                               % (self.getpos()[0], tag, line, top))


def _check(rows, name, ok, detail=""):
    rows.append((bool(ok), name, detail))


def lint(page_path=DEFAULT_PAGE, action_path=DEFAULT_ACTION):
    """返回 [(ok, name, detail), ...]"""
    rows = []
    # 必须用 with: 裸 open().read() 依赖 GC 关文件, 在 -W error::ResourceWarning
    # 下会直接炸(而且 Windows 上还会短暂锁住文件)。
    with open(page_path, encoding="utf-8") as fh:
        html = fh.read()
    with open(action_path, encoding="utf-8") as fh:
        sh = fh.read()

    # 1. 标签配对
    p = _Pair()
    p.feed(html)
    leftover = [t for t, _ in p.stack]
    _check(rows, "HTML 标签配对", not p.errors and not leftover,
           "; ".join(p.errors + (["未闭合: " + ",".join(leftover)] if leftover else [])))

    # 2. JS 语法
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    _check(rows, "页面只有一个 <script> 块", len(scripts) == 1, "找到 %d 个" % len(scripts))
    if scripts and os.path.exists(NODE):
        fd, tmp = tempfile.mkstemp(suffix=".js")
        os.close(fd)
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(scripts[0])
            r = subprocess.run([NODE, "--check", tmp], capture_output=True, text=True)
            _check(rows, "JS 语法 (node --check)", r.returncode == 0,
                   "" if r.returncode == 0 else (r.stderr or "").strip()[:200])
        finally:
            os.unlink(tmp)

    # 3/4. 动作名双向一致
    backend = set(re.findall(r"^\s{2}([a-z_]+)\)", sh, re.M))
    used = (set(re.findall(r"act\(\s*'([a-z_]+)'", html))
            | set(re.findall(r"[?&]op=([a-z_]+)", html)))
    _check(rows, "页面动作名都能被后端处理", used <= backend,
           "后端不支持: %s" % sorted(used - backend))
    _check(rows, "后端动作都在页面上有入口", backend <= used,
           "页面未暴露: %s" % sorted(backend - used))

    # 5. id 引用完整
    defined = set(re.findall(r'id="([^"]+)"', html))
    refs = set(re.findall(r"\$\('([^']+)'\)", html))
    _check(rows, "JS 引用的元素 id 都存在", refs <= defined,
           "缺失: %s" % sorted(refs - defined))

    # 6. 中文动作名
    _check(rows, "有中文动作名映射 (OPNAME)", "OPNAME" in html)
    mapped = set(re.findall(r"([a-z_]+):'[^']+'", html))
    _check(rows, "所有动作都有中文名", used <= mapped, "缺: %s" % sorted(used - mapped))

    return rows


def main():
    rows = lint()
    for ok, name, detail in rows:
        print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                           ("  -- " + detail) if detail else ""))
    bad = [r for r in rows if not r[0]]
    print()
    print("共 %d 项, %d 通过, %d 失败" % (len(rows), len(rows) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
