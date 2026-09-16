# -*- coding: utf-8 -*-
"""v5.4.4 敏感值扫描器自检。

背景: 本仓库是 public, 而 ``HANDOFF.md`` 曾明文写着路由器令牌(同时是 WiFi 密码)。
     `scripts/secret_scan.py` 是防重犯的卡口, 但它本身是纯正则匹配 —— 最危险的失败
     模式是"静默报无问题"。所以这里先用夹具断言它**必须抓得到**、并且**不误报占位值**,
     再接一个"真实仓库必须干净"的断言。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.secret_scan import scan, scan_text  # noqa: E402


class TestScannerCatches(unittest.TestCase):
    def test_catches_token_assignment(self):
        rows = scan_text("x.py", 'TOKEN = "9f3a71bc"\n')
        self.assertTrue(rows, "明文令牌赋值没被检出")

    def test_catches_json_style(self):
        rows = scan_text("x.json", '{"token": "88273911"}\n')
        self.assertTrue(rows, "JSON 形式的令牌没被检出")

    def test_catches_chinese_keyword(self):
        rows = scan_text("x.md", "路由器口令：77033129\n")
        self.assertTrue(rows, "中文关键词 + 数字没被检出")

    def test_catches_known_word(self):
        rows = scan_text("x.md", "这里写了 24681357 这个值\n", words=["24681357"])
        self.assertTrue(rows, "已知值模式没生效")
        self.assertTrue(rows[0][2].startswith("已知值"))

    def test_ignores_placeholders(self):
        for line in ('token = "12345678"\n', 'password: "000000"\n',
                     'pwd = "changeme"\n', 'secret = "password"\n'):
            self.assertFalse(scan_text("x.py", line), "占位值被误报: %s" % line.strip())

    def test_ignores_variable_reference(self):
        for line in ('token = section.get("token") or ""\n',
                     'url = "op=" + op + "&token=" + conf["token"]\n',
                     '"token":"<工作台令牌>"\n'):
            self.assertFalse(scan_text("x.py", line), "变量引用被误报: %s" % line.strip())


class TestRepoIsClean(unittest.TestCase):
    def test_no_secret_literals_in_tracked_files(self):
        """受版本控制的文件里不得出现"敏感关键词 + 具体值"。

        CI 上没有词表, 跑的是通用模式; 本地若有 .secrets.local 会连真实口令一起查。
        两种情况下当前仓库都必须是干净的。
        """
        hits = scan()
        self.assertFalse(hits, "以下位置疑似泄露敏感值:\n" + "\n".join(
            "  %s:%d [%s] %s" % (h[0], h[1], h[2], h[3]) for h in hits))


if __name__ == "__main__":
    unittest.main()
