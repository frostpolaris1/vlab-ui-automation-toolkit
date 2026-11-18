# -*- coding: utf-8 -*-
"""
Compliance guard + audit log.

Hard rules:
- Only whitelisted UI actions.
- Only whitelisted helper scripts (no arbitrary shell, no taskkill/reg/sc, no network).
- No process injection, no memory writes, no ExamConfig rewriting, no signature forgery.
- Submission only via the official client's submit button.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ALLOWED_ACTIONS = {
    "find_windows", "pin_windows", "check_anchors",
    "click", "dblclick", "rightclick", "drag", "hold", "wheel",
    "type", "key", "chord", "clipboard_set", "clipboard_get",
    "uia_read", "wait_stable", "wait_message", "screenshot",
    "measure", "record", "fill", "verify", "submit", "decrypt", "run_script",
    "agent_fallback", "assert", "sleep", "log", "set_var",
}

ALLOWED_SCRIPTS = {
    "build_fill_plan.py",
    "gen_field_map.py",
    "score_estimate.py",
    "check_saved_exam.py",
    "decrypt_examconfig.ps1",
    "verify_table.py",
    "uia_fill_all.py",
}

# Extra guard: reject any action name that smells destructive.
FORBIDDEN_SUBSTRINGS = (
    "taskkill", "reg ", "reg.exe", "sc.exe", "powershell -enc", "invoke-expression",
    "remove-item", "del ", "rmdir", "format ", "bcdedit", "net user", "schtasks",
    "writeprocessmemory", "createremotethread", "setwindowshookex", "sendmessage",
)


def check_action(action: str, params: dict) -> None:
    if action not in ALLOWED_ACTIONS:
        raise PermissionError(f"action not allowed: {action}")
    blob = json.dumps(params, ensure_ascii=False).lower()
    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in blob:
            raise PermissionError(f"forbidden token in params: {bad}")


def check_script(name: str) -> None:
    if name not in ALLOWED_SCRIPTS:
        raise PermissionError(f"script not allowed: {name}")


class AuditLog:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict) -> None:
        event = dict(event)
        event.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
