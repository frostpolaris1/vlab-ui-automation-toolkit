# -*- coding: utf-8 -*-
"""Probe caliper outer-jaw drop grid; detect acceptance by the object leaving the box."""
import json
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

VIEW_TITLE = "带孔薄板"
BOX = (45, 550, 250, 740)  # view-relative crop of the object box


def dark_pixels(path):
    im = Image.open(path).convert("L").crop(BOX)
    return sum(1 for p in im.getdata() if p < 140)


def main() -> int:
    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    view = tc.find(VIEW_TITLE)
    if not view:
        print("view not found")
        return 1
    ox, oy = view["rect"][0], view["rect"][1]
    pid = view["pid"]
    shot = ROOT / "logs" / "probe_box.png"
    tc.front(view["hwnd"])
    tc.shot(str(shot), [ox, oy, 1406, 1096])
    base = dark_pixels(shot)
    print("box dark baseline", base)

    candidates = [(x, y) for y in (160, 220, 280, 340, 400, 460, 520) for x in (300, 360, 420, 480, 540, 600, 660, 720)]
    for x, y in candidates:
        # object center in the box (vertical plate in width mode)
        tc.drag(ox + 146, oy + 637, ox + x, oy + y)
        time.sleep(0.6)
        tc.shot(str(shot), [ox, oy, 1406, 1096])
        d = dark_pixels(shot)
        vals = tc.uia_read(pid)
        print(f"drop ({x},{y}) box_dark={d} ValueText={vals.get('ValueText')} Msg={vals.get('MessageText')}")
        if d < base * 0.6:
            print("ACCEPTED at", x, y)
            return 0
    print("no acceptance")
    return 2


if __name__ == "__main__":
    sys.exit(main())
