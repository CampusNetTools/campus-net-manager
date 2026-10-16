#!/usr/bin/env python3
"""Apply Android API 36 and clean-build fixes to the pinned p4a checkout."""
import argparse
from pathlib import Path


OLD = '''                 android:process=":service_{{ name }}" />'''
NEW = '''                 android:process=":service_{{ name }}"
                 {% if name == "campusguard" %}>
            <property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"
                      android:value="User-enabled periodic campus-network authentication keepalive." />
        </service>
                 {% else %}/>
                 {% endif %}'''
MARKER = "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"
VENV_MARKER = "shprint(host_python, '-m', 'venv', '--clear', 'venv')"
OLD_VENV = "shprint(host_python, '-m', 'venv', 'venv')"


def patch_template(path):
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return False
    if source.count(OLD) != 1:
        raise RuntimeError("p4a manifest template changed; refusing an unsafe patch")
    path.write_text(source.replace(OLD, NEW), encoding="utf-8")
    return True


def patch_build(path):
    """Clear p4a's cached pure-Python venv before reinstalling pip.

    p4a v2026.05.09 reuses build/venv after interrupted/cached runs. That can
    leave mixed pip files, causing pip's own upgrade to fail before packaging.
    """
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    if VENV_MARKER in source:
        return False
    if source.count(OLD_VENV) != 1:
        raise RuntimeError("p4a build.py changed; refusing an unsafe venv patch")
    path.write_text(source.replace(OLD_VENV, VENV_MARKER), encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("p4a", type=Path, help="python-for-android checkout")
    args = parser.parse_args()
    template = args.p4a / "pythonforandroid/bootstraps/_sdl_common/build/templates/AndroidManifest.tmpl.xml"
    if not template.is_file():
        raise SystemExit("p4a SDL manifest template not found: %s" % template)
    changed = patch_template(template)
    print("special-use manifest subtype %s" % ("patched" if changed else "already present"))
    build = args.p4a / "pythonforandroid/build.py"
    if not build.is_file():
        raise SystemExit("p4a build module not found: %s" % build)
    changed = patch_build(build)
    print("p4a temporary venv reset %s" % ("patched" if changed else "already present"))


if __name__ == "__main__":
    main()
