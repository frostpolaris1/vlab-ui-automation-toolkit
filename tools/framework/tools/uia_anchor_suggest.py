# -*- coding: utf-8 -*-
"""
Read-only UIA anchor suggestion.

Dumps the UIA tree of the main/data/view windows and prints candidate controls
with window-relative coordinates. Use it to fill anchors.json faster.

Usage:
  python tools/uia_anchor_suggest.py [main|data|view|all]

No clicks, no writes to the client; only UIA reads + a dump file.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

LINE_RE = re.compile(
    r"^\s*(?P<type>\w+) name=\[(?P<name>.*?)\] aid=\[(?P<aid>.*?)\]"
    r"(?: VALUE=\[(?P<value>.*?)\])? @(?P<x>-?\d+),(?P<y>-?\d+),(?P<w>\d+)x(?P<h>\d+)"
)


def parse_dump(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE_RE.match(line)
        if m:
            rows.append(m.groupdict())
    return rows


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    targets = {
        "main": "误差配套实验",
        "data": "实验数据表格",
        "view": "100张纸",
    }
    if which != "all":
        targets = {which: targets[which]}
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)

    for key, title in targets.items():
        w = tc.find(title)
        if not w:
            print(f"== {key}: window not found ({title}) ==")
            continue
        ox, oy = w["rect"][0], w["rect"][1]
        dump = logs / f"uia_{key}.txt"
        tc.uia_dump(w["pid"], str(dump))
        rows = parse_dump(dump)
        print(f"\n== {key} hwnd={w['hwnd']} pid={w['pid']} origin=({ox},{oy}) nodes={len(rows)} ==")
        shown = 0
        for r in rows:
            name = (r["name"] or "").strip()
            aid = (r["aid"] or "").strip()
            val = (r["value"] or "").strip()
            typ = r["type"]
            if not (name or aid or val):
                continue
            # filter: keep interactive/text controls; skip layout noise
            if typ not in ("Button", "RadioButton", "CheckBox", "Edit", "Text", "Image", "Custom", "ListItem", "DataItem"):
                continue
            rel = (int(r["x"]) - ox, int(r["y"]) - oy)
            print(f"  [{typ}] name={name!r} aid={aid!r} value={val!r} rel={rel} size={r['w']}x{r['h']}")
            shown += 1
            if key == "data" and shown >= 80:
                print("  ... (truncated; see logs/uia_data.txt)")
                break
    print("\nTip: anchors.json uses window-relative [x,y]; copy rel values above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
