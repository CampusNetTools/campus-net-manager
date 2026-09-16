# -*- coding: utf-8 -*-
"""敏感值扫描 (v5.4.4)。

由来
----
本仓库是 **public** 的。2026-09-16 发现 ``HANDOFF.md`` 与 ``core/clash_api.py`` 里
明文写着路由器工作台令牌, 而那个令牌同时是**路由器管理密码、SSH 密码和家里 WiFi 密码**
—— 等于把 WiFi 密码挂在了公网上。清理完当前版本后, 加这道卡口防止重犯。

两种模式
--------
1. **通用模式** (CI 会跑, 无需任何外部输入)
   找"敏感关键词 + 具体值"的写法, 例如 ``令牌 = "12345678"``。
   纯占位值 (12345678 / 000000 之类) 会被忽略。

2. **已知值模式** (本地跑, 用于确认某个具体口令有没有漏进仓库)
   词表从环境变量 ``SECRET_WORDS`` (逗号分隔) 或本地文件 ``.secrets.local`` 读。
   这两个来源都**不进仓库**, 所以词表本身不会泄露。

用法
----
    python scripts/secret_scan.py              # 只跑通用模式
    SECRET_WORDS=abc,def python scripts/secret_scan.py   # 连具体值一起查
"""
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SUFFIXES = (".py", ".md", ".sh", ".json", ".txt", ".yml", ".yaml", ".cfg", ".ini")

# 敏感关键词
KEYWORDS = r"(?:token|密码|口令|passwd|password|secret|pwd|令牌|密钥|api[_-]?key)"

# 关键词 + 紧跟的具体值。
# 值的判定要同时满足"抓得到"和"不误报", 三种写法都必须覆盖:
#     TOKEN = "9f3a71bc"          (英文关键词 + 等号 + 带引号)      secret-scan:allow
#     路由器口令：77033129        (中文关键词 + 全角冒号 + 不带引号) secret-scan:allow
#     {"token": "88273911"}       (JSON: 关键词后面先跟一个引号)     secret-scan:allow
#   ↑ 这三行是解释规则的文档示例, 自身会被规则命中, 所以显式豁免。
# 而 ``token = section.get("token")`` 这类**变量引用**不能算 —— 所以要求值里
# 必须含数字, 否则 ``section`` 这种 7 位标识符会被当成口令。
_VALUE = (r"("
          r"[0-9]{6,}"                                      # 纯数字, 如 12345678
          r"|(?=[0-9A-Za-z_\-]*[0-9])[0-9A-Za-z_\-]{8,}"    # 8 位以上且含数字
          r")")
PATTERN = re.compile(
    KEYWORDS + r"['\"]?\s*[=:：]?\s*['\"]?" + _VALUE + r"['\"]?", re.I)

# 明显是占位/示例的值, 不算泄露
PLACEHOLDER = {
    "12345678", "123456789", "1234567890", "000000", "00000000", "111111", "11111111",
    "87654321", "123456", "88888888", "66666666", "yourpassword", "changeme",
    "password", "secret", "testkey123", "1234", "abcdefgh",
}

# 这些文件里出现"像密码"的字符串属于文档示例, 但仍然是重点观察对象
HINT_FILES = ("HANDOFF.md", "README.md", "CHANGELOG.md")

# 行内豁免标记: 测试夹具里的假值等, 在该行写这个注释即可跳过
ALLOW_MARK = "secret-scan:allow"


def tracked_files():
    """受版本控制的文件 + **未跟踪但未被忽略**的文件。

    为什么必须包含后者: 新写的文件在 `git add` 之前是 untracked 状态, 而那恰恰是
    "刚粘进来一个口令"最可能的时刻。只看 `git ls-files`(已跟踪) 会让扫描器在开发
    过程中形同虚设 —— v5.4.4 第一次推 CI 就是这样: 本地跑显示干净(新文件还没提交,
    不在扫描范围内), CI 上却红了(文件已 checkout 成 tracked)。
    被 `.gitignore` 排除的文件(.secrets.local / config.json 等)仍然不扫。
    """
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT, capture_output=True, text=True).stdout.split()
    return [f for f in out if f.endswith(SUFFIXES)]


def load_secret_words():
    words = set()
    env = os.environ.get("SECRET_WORDS", "")
    if env.strip():
        words.update(w.strip() for w in env.split(",") if w.strip())
    local = os.path.join(REPO_ROOT, ".secrets.local")
    if os.path.exists(local):
        with open(local, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    words.add(line)
    return {w for w in words if len(w) >= 6}


def scan_text(rel, text, words=()):
    """扫描一段文本, 返回 [(文件, 行号, 类型, 片段), ...]。抽出来是为了能被单测自检。"""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        # 测试夹具里出现"像密码的假值"是合理需求, 用行内标记豁免
        if ALLOW_MARK in line:
            continue
        for m in PATTERN.finditer(line):
            val = m.group(1)
            if val.lower() in PLACEHOLDER or val in PLACEHOLDER:
                continue
            hits.append((rel, i, "通用模式", m.group(0).strip()))
        for w in words:
            if w in line:
                hits.append((rel, i, "已知值(%s…)" % w[:3], line.strip()[:80]))
    return hits


def scan():
    """返回 [(文件, 行号, 类型, 片段), ...]"""
    hits = []
    words = load_secret_words()
    for rel in tracked_files():
        path = os.path.join(REPO_ROOT, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        hits.extend(scan_text(rel, text, words))
    return hits


def main():
    strict = "--strict" in sys.argv
    hits = scan()
    words = load_secret_words()
    print("扫描 %d 个受版本控制的文件" % len(tracked_files()))
    print("已知值词表: %s" % ("%d 个" % len(words) if words else "(未提供, 仅跑通用模式)"))
    print()
    if not hits:
        print("未发现疑似敏感值。")
        return 0
    for rel, line_no, kind, frag in hits:
        mark = "!!" if kind.startswith("已知值") else " ?"
        print("%s %s:%d  [%s]" % (mark, rel, line_no, kind))
        print("     %s" % frag[:110])
    print()
    print("共 %d 处。确属占位示例的可在该行加 `# %s` 豁免。" % (len(hits), ALLOW_MARK))
    known = any(h[2].startswith("已知值") for h in hits)
    if known:
        return 1
    # --strict: 通用模式命中也算失败 (CI 用)。本仓库当前 0 命中。
    return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
