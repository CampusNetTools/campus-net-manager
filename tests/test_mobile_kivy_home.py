"""Kivy must use app-writable storage before its package is imported."""
import ast
import os
import posixpath
from pathlib import Path
import tempfile
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
        with tempfile.TemporaryDirectory() as root:
            app_path = posixpath.join(root, "files", "app")
            os.makedirs(app_path)
            env = {"ANDROID_APP_PATH": app_path}

            load_configurer()(env, path_module=posixpath)

            self.assertEqual(
                env["KIVY_HOME"], posixpath.join(root, "files", ".kivy"))

    def test_default_icon_directory_is_precreated_to_skip_optional_copy(self):
        configure = load_configurer()
        with tempfile.TemporaryDirectory() as root:
            app_path = os.path.join(root, "files", "app")
            os.makedirs(app_path)
            env = {"ANDROID_APP_PATH": app_path}

            configure(env)

            self.assertTrue(os.path.isdir(os.path.join(env["KIVY_HOME"], "icon")))

    def test_existing_kivy_home_is_preserved(self):
        env = {
            "ANDROID_APP_PATH": "/data/user/0/example/files/app",
            "KIVY_HOME": "/data/user/0/example/custom-kivy",
        }

        load_configurer()(env)

        self.assertEqual(env["KIVY_HOME"], "/data/user/0/example/custom-kivy")
        self.assertFalse(os.path.exists(os.path.join(env["KIVY_HOME"], "icon")))

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
