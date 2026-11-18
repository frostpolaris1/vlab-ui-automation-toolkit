# -*- coding: utf-8 -*-
"""
Win32 controller for the VLab framework.

Design:
- All input is real SendInput via the proven input.exe / input2.exe (DPI-aware).
- Window discovery/pinning via ui.exe.
- UIA is read-only (read_vals.ps1 / uia_dump.ps1); no process injection, no memory writes.
- Every method is a thin, auditable wrapper; no arbitrary shell.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

WINS_RE = re.compile(
    r"^(?P<hwnd>\d+) pid=(?P<pid>\d+) rect=(?P<l>-?\d+),(?P<t>-?\d+),(?P<r>-?\d+),(?P<b>-?\d+) title=(?P<title>.*)$"
)


class Toolchain:
    def __init__(self, tool_dir: str, timeout: float = 30.0):
        self.tool_dir = Path(tool_dir)
        self.input = self.tool_dir / "input.exe"
        self.input2 = self.tool_dir / "input2.exe"
        self.ui = self.tool_dir / "ui.exe"
        self.read_vals = self.tool_dir / "read_vals.ps1"
        self.uia_dump = self.tool_dir / "uia_dump.ps1"
        self.timeout = timeout
        for p in (self.input, self.input2, self.ui, self.read_vals, self.uia_dump):
            if not p.exists():
                raise FileNotFoundError(f"toolchain missing: {p}")

    # ---------- low level ----------
    def _run(self, exe: Path, *args: Any, timeout: Optional[float] = None) -> str:
        cmd = [str(exe)] + [str(a) for a in args]
        # ui.exe / read_vals.ps1 emit Chinese in the Windows ANSI codepage (GBK).
        p = subprocess.run(
            cmd, capture_output=True, text=True, encoding="mbcs", errors="replace",
            timeout=timeout or self.timeout,
        )
        if p.returncode != 0:
            raise RuntimeError(f"{cmd[0]} {cmd[1:]} failed rc={p.returncode}: {p.stderr.strip()}")
        return p.stdout.strip()

    def _ps(self, script: str, timeout: Optional[float] = None) -> str:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, encoding="mbcs", errors="replace",
            timeout=timeout or self.timeout,
        )
        if p.returncode != 0:
            raise RuntimeError(f"powershell failed: {p.stderr.strip()}")
        return p.stdout.strip()

    # ---------- windows ----------
    def wins(self) -> list[dict]:
        out = self._run(self.ui, "wins")
        rows = []
        for line in out.splitlines():
            m = WINS_RE.match(line.strip())
            if not m:
                continue
            rows.append({
                "hwnd": int(m.group("hwnd")),
                "pid": int(m.group("pid")),
                "rect": [int(m.group("l")), int(m.group("t")), int(m.group("r")), int(m.group("b"))],
                "title": m.group("title"),
            })
        return rows

    def find(self, title_substr: str, pid: Optional[int] = None) -> Optional[dict]:
        for w in self.wins():
            if title_substr in w["title"] and (pid is None or w["pid"] == pid):
                return w
        return None

    def front(self, hwnd: int) -> None:
        self._run(self.ui, "front", hwnd)

    def move(self, hwnd: int, x: int, y: int) -> None:
        self._run(self.input, "winmove", hwnd, x, y)

    def origin(self, hwnd: int) -> tuple[int, int]:
        w = next((w for w in self.wins() if w["hwnd"] == hwnd), None)
        if not w:
            raise RuntimeError(f"hwnd {hwnd} not found")
        return w["rect"][0], w["rect"][1]

    def shot(self, path: str, rect: Optional[list[int]] = None) -> str:
        args = ["shot", path] + ([str(v) for v in rect] if rect else [])
        return self._run(self.ui, *args)

    def shot_window(self, hwnd: int, path: str) -> str:
        self.front(hwnd)
        w = next((w for w in self.wins() if w["hwnd"] == hwnd), None)
        if not w:
            raise RuntimeError(f"hwnd {hwnd} not found")
        l, t, r, b = w["rect"]
        return self.shot(path, [l, t, max(1, r - l), max(1, b - t)])

    # ---------- mouse / keyboard ----------
    def click(self, x: int, y: int) -> None:
        self._run(self.input, "click", x, y)

    def dblclick(self, x: int, y: int) -> None:
        self._run(self.input, "dblclick", x, y)

    def rightclick(self, x: int, y: int) -> None:
        # input2 hold with right button for 50 ms == right click
        self._run(self.input2, "hold", x, y, 50, 1)

    def drag(self, x1: int, y1: int, x2: int, y2: int, ms: int = 700) -> None:
        self._run(self.input, "drag", x1, y1, x2, y2, ms)

    def hold(self, x: int, y: int, ms: int = 800, right: bool = False) -> None:
        self._run(self.input2, "hold", x, y, ms, 1 if right else 0)

    def wheel(self, x: int, y: int, notches: int) -> None:
        self._run(self.input, "wheel", x, y, notches)

    def key(self, vk: int) -> None:
        self._run(self.input, "key", vk)

    def chord(self, mod_vk: int, key_vk: int) -> None:
        self._run(self.input, "chord", mod_vk, key_vk)

    def type_text(self, text: str) -> None:
        # input.exe typestr supports digits, '.', '-', A-Z; other chars are skipped.
        self._run(self.input, "typestr", text)

    def ctrl_a(self) -> None:
        self.chord(0x11, 0x41)

    def ctrl_v(self) -> None:
        self.chord(0x11, 0x56)

    def enter(self) -> None:
        self.key(0x0D)

    # ---------- clipboard ----------
    def clipboard_set(self, text: str) -> None:
        tmp = Path(tempfile.gettempdir()) / "vlab_clip.txt"
        tmp.write_text(text, encoding="utf-8")
        self._ps(f"Get-Content -Raw -Encoding UTF8 '{tmp}' | Set-Clipboard")

    def clipboard_codepoints(self) -> list[int]:
        out = self._ps("$s = Get-Clipboard; ($s.ToCharArray() | ForEach-Object { [int]$_ }) -join ','")
        out = out.strip()
        return [int(x) for x in out.split(",")] if out else []

    # ---------- UIA (read-only) ----------
    def uia_read(self, pid: int) -> dict[str, str]:
        out = self._run(self.read_vals, "-Pid_", pid)
        state = {}
        for line in out.splitlines():
            m = re.match(r"^(ValueText|ValueText2|MessageText) = \[(.*)\]$", line.strip())
            if m:
                state[m.group(1)] = m.group(2)
        return state

    def uia_dump(self, pid: int, out_path: str, max_nodes: int = 4000) -> str:
        return self._run(self.uia_dump, "-Pid_", pid, "-Out", out_path, "-MaxNodes", max_nodes)

    # ---------- convenience ----------
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def wait_window(self, title_substr: str, timeout: float = 15.0, interval: float = 0.5) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            w = self.find(title_substr)
            if w:
                return w
            time.sleep(interval)
        raise TimeoutError(f"window not found: {title_substr}")
