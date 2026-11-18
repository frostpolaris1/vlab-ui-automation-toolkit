# -*- coding: utf-8 -*-
"""Fill the visible paper section (Choose5-7 + 6x grid + stats)."""
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
    p = json.loads((ROOT / "fill_values.json").read_text(encoding="utf-8"))["paper"]
    tc.front(data["hwnd"])

    # preflight: paper Choose5 label must be near y=118 (bottom scroll state)
    import re
    dump = ROOT / "logs" / "uia_paper_preflight.txt"
    tc.uia_dump(data["pid"], str(dump))
    label_y = None
    for line in dump.read_text(encoding="utf-8", errors="replace").splitlines():
        if "选择测量100张纸长度的仪器" in line:
            m = re.search(r"@\d+,(-?\d+),", line)
            if m:
                label_y = int(m.group(1))
            break
    if label_y is None or not (80 <= label_y <= 170):
        print("PREFLIGHT FAIL: paper Choose5 label y=%s (expected ~118). "
              "Scroll the data table to the bottom first: grab the scroll THUMB "
              "(not the track) and drag to y≈900; repeat until Choose5 y≈118." % label_y)
        return 2

    # Choose5-7 at (870,133/198/263)
    for i, y in enumerate([132, 187, 242]):
        tc.click(ox + 874, oy + y)
        tc.select_all()
        tc.chord(0x10, ord(["A", "A", "C"][i]))
        time.sleep(0.12)

    # 6x grid: first cell center (L,1) at data-relative (288,372), cell 140x38
    for r, k in enumerate(["L", "B", "H"]):
        for c in range(6):
            x = ox + 288 + c * 140
            y = oy + 372 + r * 38
            tc.dblclick(x, y)
            tc.select_all()
            tc.type_text(p["data"][k][c])
            tc.enter()
            time.sleep(0.1)

    # stats (6)-(12): click centers measured from UIA
    stats = [
        (510, p["avg"]["L"]), (565, p["avg"]["B"]), (620, p["avg"]["H"]),
        (675, p["V"]), (730, p["rel"]), (785, p["dV"]), (841, p["expr"]),
    ]
    for y, val in stats:
        tc.click(ox + 500, oy + y)
        tc.select_all()
        if "±" in val:
            tc.clipboard_set(val)
            tc.ctrl_v()
        else:
            tc.type_text(val)
        time.sleep(0.1)

    tc.shot_window(data["hwnd"], str(ROOT / "logs" / "shots" / "fill_paper_done.png"))
    print("paper section filled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
