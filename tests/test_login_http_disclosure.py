import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISCLOSURE = "HTTP"


class LoginHttpDisclosureTests(unittest.TestCase):
    def test_desktop_profile_form_discloses_http_login(self):
        source = (ROOT / "gui" / "feature_windows.py").read_text(encoding="utf-8")
        self.assertIn(DISCLOSURE, source)
        self.assertIn("校园网络可见", source)
        self.assertIn("账号和密码", source)
        self.assertIn("HTTPS 地址会按配置使用且不会降级", source)

    def test_android_login_form_discloses_http_login(self):
        source = (ROOT / "mobile" / "main.py").read_text(encoding="utf-8")
        self.assertIn(DISCLOSURE, source)
        self.assertIn("校园网络可见", source)
        self.assertIn("账号和密码", source)
        self.assertIn("HTTPS 地址会按配置使用且不会降级", source)

    def test_user_docs_disclose_http_login(self):
        for relative in ("docs/用户使用手册.md", "mobile/README.md"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(DISCLOSURE, source, relative)
            self.assertIn("账号和密码", source, relative)
            self.assertIn("只在可信校园网登录", source, relative)
            self.assertIn("不会自动降级", source, relative)


if __name__ == "__main__":
    unittest.main()
