"""Kivy must use app-writable storage before its package is imported."""
import ast
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MOBILE_MAIN = ROOT / "mobile" / "main.py"


def load_configurer():
    tree = ast.parse(MOBILE_MAIN.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_configure_kivy_home"
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {"os": os}
    exec(compile(module, str(MOBILE_MAIN), "exec"), namespace)
    return namespace["_configure_kivy_home"]


class MobileKivyHomeTests(unittest.TestCase):
    def test_android_uses_writable_parent_of_extracted_source(self):
        env = {"ANDROID_APP_PATH": "/data/user/0/example/files/app"}

        load_configurer()(env)

        self.assertEqual(env["KIVY_HOME"], "/data/user/0/example/files/.kivy")

    def test_existing_kivy_home_is_preserved(self):
        env = {
            "ANDROID_APP_PATH": "/data/user/0/example/files/app",
            "KIVY_HOME": "/data/user/0/example/custom-kivy",
        }

        load_configurer()(env)

        self.assertEqual(env["KIVY_HOME"], "/data/user/0/example/custom-kivy")

    def test_non_android_environment_is_unchanged(self):
        env = {"HOME": "/Users/test"}

        load_configurer()(env)

        self.assertEqual(env, {"HOME": "/Users/test"})

    def test_configuration_runs_before_any_kivy_import(self):
        tree = ast.parse(MOBILE_MAIN.read_text(encoding="utf-8"))
        config_index = next(
            index for index, node in enumerate(tree.body)
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_configure_kivy_home"
        )
        kivy_imports = [
            index for index, node in enumerate(tree.body)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and (
                (isinstance(node, ast.ImportFrom) and node.module
                 and (node.module == "kivy" or node.module.startswith("kivy.")))
                or (isinstance(node, ast.Import) and any(
                    alias.name == "kivy" or alias.name.startswith("kivy.")
                    for alias in node.names
                ))
            )
        ]

        self.assertTrue(kivy_imports)
        self.assertLess(config_index, min(kivy_imports))


if __name__ == "__main__":
    unittest.main()
