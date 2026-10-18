"""Do not start Android background auth with stale/unsaved credentials."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MOBILE_MAIN = ROOT / "mobile" / "main.py"


class MobileGuardSaveGateTests(unittest.TestCase):
    def test_android_guard_returns_when_profile_save_fails(self):
        tree = ast.parse(MOBILE_MAIN.read_text(encoding="utf-8"))
        app = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "CampusNetMobile"
        )
        methods = {
            node.name: node for node in app.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        toggle = methods["toggle_guard"]
        guards = [
            node for node in ast.walk(toggle)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.UnaryOp)
            and isinstance(node.test.op, ast.Not)
            and isinstance(node.test.operand, ast.Call)
            and isinstance(node.test.operand.func, ast.Attribute)
            and node.test.operand.func.attr == "_save_profile"
        ]

        self.assertEqual(len(guards), 1)
        self.assertTrue(any(isinstance(node, ast.Return) for node in guards[0].body))
        notification_request = next(
            node for node in ast.walk(toggle)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_request_notification_permission"
        )
        self.assertGreater(notification_request.lineno, guards[0].lineno)

    def test_profile_save_reports_success_and_failure(self):
        tree = ast.parse(MOBILE_MAIN.read_text(encoding="utf-8"))
        app = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "CampusNetMobile"
        )
        save = next(
            node for node in app.body
            if isinstance(node, ast.FunctionDef) and node.name == "_save_profile"
        )
        return_values = [
            node.value.value for node in ast.walk(save)
            if isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
        ]
        self.assertIn(True, return_values)
        self.assertIn(False, return_values)


if __name__ == "__main__":
    unittest.main()
