# -*- coding: utf-8 -*-
"""
One-shot calibration helper (read-only + window moves).

- Finds the main/data/view windows.
- Pins main (0,0), data (1900,0), view (1900,1000) if present.
- Saves screenshots to logs/shots/calib_*.png.
- Copies anchors.example.json -> anchors.json if missing.
- Prints the anchor keys to fill; set "calibrated": true when done.

The agent uses the screenshots to fill window-relative coordinates.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402


def main() -> int:
    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    exp = iface["experiments"][0]
    anchors_path = ROOT / exp["anchors"]
    example = anchors_path.with_name("anchors.example.json")
    if not anchors_path.exists() and example.exists():
        shutil.copyfile(example, anchors_path)
        print(f"created {anchors_path} from example")

    main = tc.find("误差配套实验")
    data = tc.find("实验数据表格")
    if not main or not data:
        print("ERROR: start the experiment first (main/data window not found)")
        return 1
    tc.move(main["hwnd"], 0, 0)
    tc.move(data["hwnd"], 1900, 0)
    shots = ROOT / "logs" / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    tc.shot_window(main["hwnd"], str(shots / "calib_main.png"))
    tc.shot_window(data["hwnd"], str(shots / "calib_data.png"))
    print("saved", shots / "calib_main.png")
    print("saved", shots / "calib_data.png")

    view = tc.find("100张纸") or tc.find("带孔薄板")
    if view:
        tc.move(view["hwnd"], 1900, 1000)
        tc.shot_window(view["hwnd"], str(shots / "calib_view.png"))
        print("saved", shots / "calib_view.png")
    else:
        print("view window not open: double-click the paper/plate first, then re-run")

    anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
    print("\nFill these window-relative anchors in", anchors_path)
    print("  paper/gb: main_icon, radio_*, instrument_*, lock, ratchet, jaw_*, object_box, gap, caliper_place, ruler_band, btn_out")
    print("  data: gb_grid/paper_grid origin+cell_w+cell_h, choose1..7, gb_*/paper_* fields, submit")
    print("Tip: run `python tools/uia_anchor_suggest.py` to list control names/relative rects")
    print("Then set \"calibrated\": true and run: python -m core.runner")
    return 0


if __name__ == "__main__":
    sys.exit(main())
