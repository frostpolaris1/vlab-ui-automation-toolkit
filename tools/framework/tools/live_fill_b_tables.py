# -*- coding: utf-8 -*-
"""Fill the two 0-point B-class uncertainty tables (thin plate 3x4, paper 3x3).

Values come from fill_values.json -> table1 / table3 (client ToUncertainty format).
Uses UIA ValuePattern.SetValue on the table cells, so it works regardless of the
data-table scroll position (no clicking/offscreen risk).

Usage:
    py -3 -I tools/live_fill_b_tables.py [--pid PID] [--fill fill_values.json]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

ROWS = ["ruler", "caliper", "mic"]


def flatten(table: dict, ncols: int) -> list[str]:
    """UIA tree order is column-major: for each column, the 3 instrument rows."""
    out: list[str] = []
    for c in range(ncols):
        for r in ROWS:
            out.append(str(table[r][c]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--fill", default=str(ROOT / "fill_values.json"))
    args = ap.parse_args()

    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    data = tc.find("实验数据表格")
    if not data:
        print("data window not found")
        return 1
    pid = args.pid or data["pid"]

    fill = json.loads(Path(args.fill).read_text(encoding="utf-8"))
    payload = {
        "gb": flatten(fill["table1"], 4),
        "paper": flatten(fill["table3"], 3),
    }
    out_json = ROOT / "logs" / "b_tables_values.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    tc.front(data["hwnd"])
    script = ROOT / "tools" / "uia_set_b_tables.ps1"
    res = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
         "-Pid_", str(pid), "-JsonPath", str(out_json),
         "-DataTitle", "实验数据表格",
         "-HeaderLike", "根据参数计算下列B类不确定度"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print((res.stdout or "").strip())
    if res.returncode != 0:
        print("STDERR:", (res.stderr or "").strip()[:500])
        return res.returncode
    print("B-class tables filled: gb=12 paper=9 (UIA readback OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
