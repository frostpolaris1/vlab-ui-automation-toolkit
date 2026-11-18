# -*- coding: utf-8 -*-
"""Fill the visible GB section (Choose1-4 + 6x grid) with known coordinates."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402


def main() -> int:
    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    data = tc.find("实验数据表格")
    if not data:
        print("data window not found")
        return 1
    ox, oy = data["rect"][0], data["rect"][1]
    vals = json.loads((ROOT / "fill_values.json").read_text(encoding="utf-8"))
    tc.front(data["hwnd"])

    # preflight: GB Choose2 label must be near y=388 (top scroll state)
    import re
    dump = ROOT / "logs" / "uia_gb_preflight.txt"
    tc.uia_dump(data["pid"], str(dump))
    label_y = None
    for line in dump.read_text(encoding="utf-8", errors="replace").splitlines():
        if "选择测量带孔薄板长度的仪器" in line:
            m = re.search(r"@\d+,(-?\d+),", line)
            if m:
                label_y = int(m.group(1))
            break
    if label_y is None or not (350 <= label_y <= 430):
        print("PREFLIGHT FAIL: GB Choose2 label y=%s (expected ~388). "
              "Scroll the data table to the TOP first: grab the scroll THUMB "
              "(not the track) and drag to y≈90." % label_y)
        return 2

    # Choose1-4 edit centers (data-relative): x=900, y=401/456/511/566
    for i, y in enumerate([401, 456, 511, 566]):
        tc.dblclick(ox + 900, oy + y)
        tc.select_all()
        tc.chord(0x10, ord(vals["choose"][i]))
        tc.enter()
        time.sleep(0.15)

    # GB 6x grid: first cell (L,1) center (288,696), cell pitch 140x38
    rows = ["L", "B", "H", "D"]
    for r, k in enumerate(rows):
        for c in range(6):
            x = ox + 288 + c * 140
            y = oy + 696 + r * 38
            tc.dblclick(x, y)
            tc.select_all()
            tc.type_text(vals["gb"]["data"][k][c])
            tc.enter()
            time.sleep(0.12)

    tc.shot_window(data["hwnd"], str(ROOT / "logs" / "shots" / "fill_gb_done.png"))
    print("GB visible section filled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
