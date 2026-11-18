# -*- coding: utf-8 -*-
"""Fill GB stats fields (7)-(30) via Tab order after scrolling to (7)."""
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
    # optional: click point of the first stats field, data-relative
    sx = int(sys.argv[1]) if len(sys.argv) > 1 else 518
    sy = int(sys.argv[2]) if len(sys.argv) > 2 else 873
    v = json.loads((ROOT / "fill_values.json").read_text(encoding="utf-8"))["gb"]
    vals = [
        v["avg"]["L"], v["S"]["L"], v["dA"]["L"], v["dB"]["L"], v["d"]["L"],
        v["avg"]["B"], v["S"]["B"], v["dA"]["B"], v["dB"]["B"], v["d"]["B"],
        v["avg"]["H"], v["S"]["H"], v["dA"]["H"], v["dB"]["H"], v["d"]["H"],
        v["avg"]["D"], v["S"]["D"], v["dA"]["D"], v["dB"]["D"], v["d"]["D"],
        v["V"], v["rel"], v["dV"], v["expr"],
    ]
    tc.front(data["hwnd"])

    # preflight: (7) label must be near y=860 (top scroll state)
    import re
    dump = ROOT / "logs" / "uia_gb_stats_preflight.txt"
    tc.uia_dump(data["pid"], str(dump))
    label_y = None
    for line in dump.read_text(encoding="utf-8", errors="replace").splitlines():
        if "带孔薄板长度L的平均值" in line:
            m = re.search(r"@\d+,(-?\d+),", line)
            if m:
                label_y = int(m.group(1))
            break
    if label_y is None or not (820 <= label_y <= 930):
        print("PREFLIGHT FAIL: GB (7) label y=%s (expected ~860). "
              "Scroll the data table to the TOP first (thumb to y≈90), "
              "then rerun live_fill_gb.py and this script." % label_y)
        return 2

    # first stats field at the given data-relative point
    tc.click(ox + sx, oy + sy)
    tc.ctrl_a()
    for i, val in enumerate(vals):
        if "±" in val:
            tc.clipboard_set(val)
            tc.ctrl_v()
        else:
            tc.type_text(val)
        if i != len(vals) - 1:
            tc.key(0x09)  # Tab
            time.sleep(0.12)
    tc.shot_window(data["hwnd"], str(ROOT / "logs" / "shots" / "fill_gb_stats_done.png"))
    print("GB stats filled:", len(vals), "fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())
