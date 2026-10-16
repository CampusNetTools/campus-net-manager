# -*- coding: utf-8 -*-
"""python-for-android entry point for the visible campus keepalive service."""
import json
import os

from jnius import autoclass


PythonService = autoclass("org.kivy.android.PythonService")
PythonService.mService.setAutoRestartService(True)

from guard_service import run_guard_service  # noqa: E402


arguments = json.loads(os.environ.get("PYTHON_SERVICE_ARGUMENT", "{}"))
profile_path = arguments.get("profile_path", "")
state_path = arguments.get("state_path", "") or None
if not profile_path:
    raise RuntimeError("missing keepalive profile path")
run_guard_service(profile_path, state_path)
