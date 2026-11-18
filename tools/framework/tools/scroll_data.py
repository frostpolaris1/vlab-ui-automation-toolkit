# -*- coding: utf-8 -*-
"""Scroll the data table to a canonical state (thumb-aware, fronted, verified).

Usage:
    py -3 -I tools/scroll_data.py top|bottom [--pid PID]

Why: clicking the scrollbar TRACK only pages once; the thumb must be grabbed.
The data window must be foregrounded or the drag is silently dropped.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

STATES = {
    "top": {
        "label": "选择测量带孔薄板长度的仪器",
        "range": (350, 430),
        "thumb_top": 52,
    },
    "bottom": {
        "label": "选择测量100张纸长度的仪器",
        "range": (80, 170),
        "thumb_top": 668,
    },
    # full paper B-class table visible (scroll up a little from bottom)
    "paper_b": {
        "label": "2. 测量一张纸的体积",
        "range": (70, 140),
        "thumb_top": 600,
    },
}

THUMB_RE = re.compile(r"Thumb name=\[\] aid=\[\] @(\d+),(-?\d+),(\d+)x(\d+)")
LABEL_RE = re.compile(r"@\d+,(-?\d+),")


def dump(tc: Toolchain, pid: int, name: str) -> str:
    out = ROOT / "logs" / f"uia_{name}.txt"
    tc.uia_dump(pid, str(out))
    return out.read_text(encoding="utf-8", errors="replace")


def find_thumb(text: str):
    m = THUMB_RE.search(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))


def find_label_y(text: str, label: str):
    for line in text.splitlines():
        if label in line:
            m = LABEL_RE.search(line)
            return int(m.group(1)) if m else None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("state", choices=sorted(STATES))
    ap.add_argument("--pid", type=int, default=0)
    args = ap.parse_args()
    spec = STATES[args.state]

    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    data = tc.find("实验数据表格")
    if not data:
        print("data window not found")
        return 1
    pid = args.pid or data["pid"]

    target_top = spec["thumb_top"]
    for attempt in range(1, 5):
        tc.front(data["hwnd"])          # critical: drag is dropped when not foreground
        tc.sleep(0.3)
        text = dump(tc, pid, f"scroll_{args.state}")
        thumb = find_thumb(text)
        ref = find_label_y(text, spec["label"])
        lo, hi = spec["range"]
        print(f"attempt {attempt}: thumb={thumb} ref_y={ref} target_range={lo}..{hi}")
        if ref is not None and lo <= ref <= hi:
            print(f"OK {args.state}: ref_y={ref}")
            return 0
        if not thumb:
            print("ERROR: scrollbar thumb not found")
            return 2
        x, top, w, h = thumb
        # content moves ~3.8 px per thumb px; adjust the desired THUMB TOP
        if ref is not None:
            desired = (lo + hi) // 2
            target_top = int(max(52, min(668, target_top + (ref - desired) / 3.8)))
        tc.drag(x + w // 2, top + h // 2, x + w // 2, target_top + h // 2)
        tc.sleep(0.6)

    print(f"FAILED to reach {args.state}")
    return 3


if __name__ == "__main__":
    sys.exit(main())
