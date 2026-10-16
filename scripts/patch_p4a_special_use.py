#!/usr/bin/env python3
"""Add the Android-required special-use explanation to the pinned p4a template."""
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


def patch_template(path):
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return False
    if source.count(OLD) != 1:
        raise RuntimeError("p4a manifest template changed; refusing an unsafe patch")
    path.write_text(source.replace(OLD, NEW), encoding="utf-8")
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


if __name__ == "__main__":
    main()
