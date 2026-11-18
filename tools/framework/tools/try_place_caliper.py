# -*- coding: utf-8 -*-
"""One-shot caliper placement probe (agent-assisted coordinates).

Coordinates are IMAGE pixels of the 1406x1096 big-view screenshot; the window
origin is added automatically. Prints UIA state after each phase and saves shots.

Usage:
  py -3 -I tools/try_place_caliper.py --pid 26744 \
     --knob 565,350 --drag 645,497 --drop 526,275 --opening 37.9
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--view", default="带孔薄板")
    ap.add_argument("--knob", required=True, help="image x,y of lock knob")
    ap.add_argument("--drag", required=True, help="image x,y of drag area")
    ap.add_argument("--drop", required=True, help="image x,y to drop the object")
    ap.add_argument("--box", default="145,635", help="image x,y of object in box")
    ap.add_argument("--opening", type=float, default=37.9)
    ap.add_argument("--shots", default="logs/caliper_probe")
    args = ap.parse_args()

    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    view = tc.find(args.view, pid=args.pid)
    if not view:
        print("view not found")
        return 1
    ox, oy = view["rect"][0], view["rect"][1]
    out = Path(args.shots)
    out.mkdir(parents=True, exist_ok=True)

    def pt(s):
        x, y = (int(v) for v in s.split(","))
        return ox + x, oy + y

    def state(tag):
        vals = tc.uia_read(args.pid)
        print(tag, json.dumps(vals, ensure_ascii=False))
        tc.shot(str(out / f"{tag}.png"), [ox, oy, 1406, 1096])

    tc.front(view["hwnd"])
    time.sleep(0.4)
    state("00_before")

    # unlock (right-click) and report
    tc.rightclick(*pt(args.knob))
    time.sleep(0.5)
    state("01_after_unlock")

    # open to the target value: DragRect moves ~3.86 px per mm
    dx, dy = pt(args.drag)
    tc.drag(dx, dy, dx + int(args.opening * 3.86), dy)
    time.sleep(0.8)
    state("02_after_open")

    # drag the object from the box to the agent-provided drop point
    bx, by = pt(args.box)
    px, py = pt(args.drop)
    tc.drag(bx, by, px, py)
    time.sleep(1.0)
    state("03_after_place")
    return 0


if __name__ == "__main__":
    sys.exit(main())
