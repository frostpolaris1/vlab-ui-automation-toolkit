# -*- coding: utf-8 -*-
"""Verify the filled data table against fill_values.json using a UIA dump.

Usage:
    py -3 -I tools/verify_table.py [--pid PID] [--fill fill_values.json]

Checks every non-empty Edit value in the client's data-table window against the
expected multiset built from fill_values.json (choose + 6x grids + all stats).
Prints OK / missing / unexpected; exits non-zero on mismatch.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = Path(r"%USERPROFILE%\.agents\skills\vlab-experiment-automation\scripts")
if not SKILL_SCRIPTS.exists():
    SKILL_SCRIPTS = ROOT.parent / "skill" / "scripts"


def norm(s: str) -> str:
    s = s.strip().replace("−", "-")
    try:
        return repr(round(float(s), 12))
    except ValueError:
        return s


def dec_count(s: str) -> int:
    s = s.strip()
    return len(s.split(".", 1)[1]) if "." in s else 0


def expected_values(fill: dict) -> list[str]:
    out: list[str] = []
    out.extend(fill["choose"])
    for section, keys in (("gb", "LBHD"), ("paper", "LBH")):
        blk = fill[section]
        for k in keys:
            out.extend(blk["data"][k])
            if section == "gb":
                out.extend([blk["avg"][k], blk["S"][k], blk["dA"][k],
                            blk["dB"][k], blk["d"][k]])
            else:
                out.append(blk["avg"][k])
        out.extend([blk["V"], blk["rel"], blk["dV"], blk["expr"]])
    # 0-point B-class tables (thin plate 3x4, paper 3x3) - now filled too
    for tbl in (fill.get("table1"), fill.get("table3")):
        if tbl:
            for r in ("ruler", "caliper", "mic"):
                out.extend(tbl[r])
    return out


def actual_values(pid: int) -> list[str]:
    dump = Path(tempfile.gettempdir()) / "vlab_verify_uia.txt"
    script = SKILL_SCRIPTS / "uia_dump.ps1"
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
         "-Pid_", str(pid), "-Out", str(dump)],
        check=True, capture_output=True,
    )
    vals: list[str] = []
    in_data = False
    for line in dump.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.lstrip("\ufeff")
        if line.startswith("===== WINDOW"):
            in_data = "实验数据表格" in line
            continue
        if not in_data or "VALUE=[" not in line:
            continue
        v = line.split("VALUE=[", 1)[1].split("]", 1)[0]
        if v.strip():
            vals.append(v)
    return vals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--fill", default=str(ROOT / "fill_values.json"))
    args = ap.parse_args()

    pid = args.pid
    if not pid:
        for p in ("Main",):
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"(Get-Process {p} -ErrorAction SilentlyContinue).Id"],
                               capture_output=True, text=True)
            if r.stdout.strip():
                pid = int(r.stdout.strip().splitlines()[0])
                break
    if not pid:
        print("Main.exe not running; pass --pid")
        return 2

    fill = json.loads(Path(args.fill).read_text(encoding="utf-8"))
    exp = Counter(norm(v) for v in expected_values(fill))
    act_list = actual_values(pid)
    act = Counter(norm(v) for v in act_list)

    missing = exp - act
    extra = act - exp
    print(f"expected={sum(exp.values())} actual={sum(act.values())}")
    if missing:
        print("MISSING:")
        for v, n in sorted(missing.items()):
            print(f"  {n} x {v}")
    if extra:
        print("UNEXPECTED:")
        for v, n in sorted(extra.items()):
            print(f"  {n} x {v}")

    # hidden checks depend on DECIMAL PLACES, not just numeric value
    dec_fail = []
    for section, key, want_dec in (("gb", "B", 2), ("gb", "H", 3), ("paper", "H", 3)):
        want = float(fill[section]["data"][key][0])
        same = [v for v in act_list if norm(v) == repr(round(want, 12))]
        good = [v for v in same if dec_count(v) == want_dec]
        if len(good) < 6:
            dec_fail.append((section, key, want_dec, len(good), same[:3]))
    if dec_fail:
        print("DECIMAL FAIL (hidden checks):")
        for sec, key, d, n, sample in dec_fail:
            print(f"  {sec}.{key}: need >=6 values with exactly {d} decimals, got {n}; sample={sample}")
        return 1

    if not missing and not extra:
        print("OK: all expected values present, no unexpected non-empty cells")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
