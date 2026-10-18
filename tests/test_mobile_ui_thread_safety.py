"""Keep Kivy form reads on the UI thread in asynchronous mobile workers."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MOBILE_MAIN = ROOT / "mobile" / "main.py"
FORM_READERS = {"_form_data", "_profile", "_save_profile"}
WORKER_METHODS = {"refresh_status", "manual_login", "_guard_tick"}


class MobileUiThreadSafetyTests(unittest.TestCase):
    def test_async_workers_do_not_read_kivy_form_widgets(self):
        tree = ast.parse(MOBILE_MAIN.read_text(encoding="utf-8"))
        class_node = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "CampusNetMobile"
        )
        methods = {
            node.name: node for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        for method_name in sorted(WORKER_METHODS):
            with self.subTest(method=method_name):
                method = methods[method_name]
                worker = next(
                    node for node in method.body
                    if isinstance(node, ast.FunctionDef) and node.name == "work"
                )
                calls = [
                    node.func.attr for node in ast.walk(worker)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in FORM_READERS
                ]
                self.assertEqual(
                    calls, [],
                    "%s worker must snapshot form values before it starts" % method_name,
                )


if __name__ == "__main__":
    unittest.main()
