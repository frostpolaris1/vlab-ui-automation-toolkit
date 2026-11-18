# -*- coding: utf-8 -*-
"""
Recognition layer: UIA state + stability/message probes + evidence capture.

UIA facts (from prior sessions):
- ValueText2: micrometer live reading (e.g. "读数：7.501mm").
- ValueText:  caliper/ruler readout (may be static/placeholder; never trust alone).
- MessageText: transient messages such as "物体放不进去".
- Values can be stale after reset -> always re-read after an action and confirm visually.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def read_state(tc, pid: int) -> dict[str, str]:
    return tc.uia_read(pid)


def extract_number(text: str) -> Optional[float]:
    if not text:
        return None
    m = NUM_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def wait_stable(
    tc,
    pid: int,
    key: str = "ValueText2",
    timeout: float = 12.0,
    interval: float = 0.25,
    stable_polls: int = 4,
) -> dict:
    """
    Poll UIA until `key` stops changing for `stable_polls` polls.
    Returns {"ok": bool, "value": str, "state": dict, "reason": str}.
    """
    deadline = time.time() + timeout
    last = None
    same = 0
    last_state = {}
    while time.time() < deadline:
        state = read_state(tc, pid)
        last_state = state
        val = state.get(key, "")
        msg = state.get("MessageText", "")
        if msg and ("放不进去" in msg or "请" in msg):
            return {"ok": False, "value": val, "state": state, "reason": f"message:{msg}"}
        if val == last and val != "":
            same += 1
            if same >= stable_polls:
                return {"ok": True, "value": val, "state": state, "reason": "stable"}
        else:
            same = 0
            last = val
        time.sleep(interval)
    return {"ok": False, "value": last or "", "state": last_state, "reason": "timeout"}


def wait_message(tc, pid: int, substr: str, timeout: float = 6.0, interval: float = 0.2) -> dict:
    deadline = time.time() + timeout
    last_state = {}
    while time.time() < deadline:
        state = read_state(tc, pid)
        last_state = state
        msg = state.get("MessageText", "")
        if substr in msg:
            return {"ok": True, "message": msg, "state": state}
        time.sleep(interval)
    return {"ok": False, "message": last_state.get("MessageText", ""), "state": last_state}


def save_evidence(tc, hwnd: int, path: str, state: Optional[dict] = None) -> str:
    tc.shot_window(hwnd, path)
    if state is not None:
        Path(path).with_suffix(".json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return path


def needs_agent(
    out_dir: str,
    task: str,
    reason: str,
    screenshot: Optional[str] = None,
    state: Optional[dict] = None,
    context: Optional[dict] = None,
) -> str:
    """
    Write a machine-readable fallback request. The agent reads it, inspects the
    screenshot/state, fixes the issue manually or updates anchors, then resumes.
    """
    p = Path(out_dir) / "needs_agent.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "task": task,
        "reason": reason,
        "screenshot": screenshot,
        "state": state or {},
        "context": context or {},
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)
