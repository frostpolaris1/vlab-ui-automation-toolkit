# -*- coding: utf-8 -*-
"""Find the micrometer lock knob hit area by scanning right-clicks.

Detects the lock pointer orientation from the screenshot:
  locked   -> short vertical bar below the knob circle
  unlocked -> short horizontal bar to the right of the knob circle
"""
import json
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

CX, CY = 680, 495            # visual knob center, view-relative
DOWN = (CX - 7, CY + 8, CX + 7, CY + 24)
RIGHT = (CX + 9, CY - 7, CX + 26, CY + 7)


def dark(img, box):
    g = img.crop(box).convert("L")
    return sum(1 for p in g.getdata() if p < 100)


def main() -> int:
    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    view = tc.find("带孔薄板")
    if not view:
        print("view not found")
        return 1
    ox, oy = view["rect"][0], view["rect"][1]
    shot = ROOT / "logs" / "mic_knob_probe.png"

    def state():
        tc.shot(str(shot), [ox, oy, 1406, 1096])
        im = Image.open(shot)
        return dark(im, DOWN), dark(im, RIGHT)

    tc.front(view["hwnd"])
    print("baseline down,right =", state())
    for y in range(CY - 20, CY + 21, 8):
        for x in range(CX - 24, CX + 25, 8):
            tc.rightclick(ox + x, oy + y)
            time.sleep(0.15)
            d, r = state()
            if r > d + 2:
                print(f"UNLOCKED by right-click at view ({x},{y}); down={d} right={r}")
                return 0
    print("not unlocked; last down,right =", state())
    return 2


if __name__ == "__main__":
    sys.exit(main())
