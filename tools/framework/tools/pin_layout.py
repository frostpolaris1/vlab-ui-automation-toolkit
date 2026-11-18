# -*- coding: utf-8 -*-
"""Pin the VLab windows to the canonical absolute layout.

Usage:
    py -3 -I tools/pin_layout.py            # pin + print
    py -3 -I tools/pin_layout.py --check    # only report current rects

Canonical layout (physical screen px, 3840x2160 @175%):
    主窗   误差配套实验      -> (0, 0)
    数据表 实验数据表格      -> (1900, 0)
    大视图 带孔薄板/100张纸  -> (1900, 1000)
With this layout every control has a stable ABSOLUTE coordinate; scripts may
use either absolute coords or data-window-relative coords + (1900,0).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

LAYOUT = {
    "main": {"title": "误差配套实验", "pos": (0, 0), "required": True},
    "data": {"title": "实验数据表格", "pos": (1900, 0), "required": True},
    "view_gb": {"title": "带孔薄板", "pos": (1900, 1000), "required": False},
    "view_paper": {"title": "100张纸", "pos": (1900, 1000), "required": False},
}


def main() -> int:
    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    check_only = "--check" in sys.argv

    # optional: wait for required windows that appear a few seconds after Main.exe starts
    wait_s = 0.0
    for i, a in enumerate(sys.argv):
        if a == "--wait" and i + 1 < len(sys.argv):
            wait_s = float(sys.argv[i + 1])
        elif a.startswith("--wait="):
            wait_s = float(a.split("=", 1)[1])
    if wait_s > 0:
        deadline = time.time() + wait_s
        while time.time() < deadline:
            missing = [k for k, s in LAYOUT.items()
                       if s.get("required") and not tc.find(s["title"])]
            if not missing:
                break
            time.sleep(1.0)

    result = {}
    for key, spec in LAYOUT.items():
        w = tc.find(spec["title"])
        if not w:
            result[key] = {"found": False, "title": spec["title"],
                           "required": spec.get("required", False)}
            print(f'{key:10s} SKIP (not open, required={spec.get("required", False)})')
            continue
        if not check_only:
            tc.move(w["hwnd"], *spec["pos"])
            w = tc.find(spec["title"]) or w
        result[key] = {
            "found": True,
            "title": spec["title"],
            "hwnd": w["hwnd"],
            "rect": w["rect"],
            "target": list(spec["pos"]),
            "required": spec.get("required", False),
        }
        print(f'{key:10s} hwnd={w["hwnd"]} rect={w["rect"]} -> {spec["pos"]}')

    out = ROOT / "logs" / "layout.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", out)

    strict = "--strict" in sys.argv
    ok = all(v.get("found") for v in result.values() if strict or v.get("required"))
    if not ok:
        print("ERROR: required window(s) missing (main/data). Start the experiment first.")
        return 1
    if not strict and any(not v.get("found") for v in result.values()):
        print("NOTE: optional view window(s) not open; fast fill path does not need them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
