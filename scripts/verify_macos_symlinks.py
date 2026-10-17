#!/usr/bin/env python3
"""Fail a macOS release if ditto did not preserve app/framework symlinks in ZIP."""
import os
import stat
import sys
import zipfile


def verify(app_path, archive_path):
    symlinks = []
    for root, dirs, files in os.walk(app_path, followlinks=False):
        for name in dirs + files:
            source = os.path.join(root, name)
            if os.path.islink(source):
                relative = os.path.relpath(source, os.path.dirname(app_path))
                symlinks.append(relative.replace(os.sep, "/"))
    framework_links = [name for name in symlinks if ".framework/" in name]
    if not symlinks:
        raise RuntimeError("app bundle contains no symlinks to validate")

    with zipfile.ZipFile(archive_path) as archive:
        entries = {entry.filename: entry for entry in archive.infolist()}
    missing = [name for name in symlinks if name not in entries]
    flattened = [name for name in symlinks if name in entries and
                 not stat.S_ISLNK(entries[name].external_attr >> 16)]
    if missing or flattened:
        raise RuntimeError("ZIP symlink validation failed; missing=%r flattened=%r" %
                           (missing[:10], flattened[:10]))
    print("Verified %d app symlinks (%d framework symlinks) in %s" %
          (len(symlinks), len(framework_links), archive_path))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_macos_symlinks.py APP_PATH ARCHIVE.zip")
    verify(sys.argv[1], sys.argv[2])
