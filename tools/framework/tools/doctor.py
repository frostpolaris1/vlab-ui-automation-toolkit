# -*- coding: utf-8 -*-
"""One-shot environment report for a zero-context agent.

Checks platform HTTP, client processes, windows/rects, platform page info
(account/lab/start button via UIA, no screenshots), data-table fill count,
optional session truth, and tool availability. Writes logs/doctor.json.

Usage: py -3 -I tools/doctor.py [--pid PID] [--no-truth]
"""
import argparse
import json
import re
import subprocess
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

PLATFORM = "http://PLATFORM_HOST/"
MEM6 = Path(r"<local-research>/mem/mem6.exe")
TRUTH_KEYS = ("PaperLength", "PaperWidth", "PaperThickness",
              "GBLength", "GBWidth", "GBThickness", "GBDiameter")


def http_status(url: str, timeout: float = 8.0) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except Exception as e:  # noqa: BLE001
        return f"ERR:{e}"


def procs() -> list[dict]:
    ps = (
        "Get-Process Main,WebLabClient -ErrorAction SilentlyContinue | "
        "Select-Object Id,ProcessName,StartTime | ConvertTo-Json -Compress"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, encoding="mbcs", errors="replace")
    try:
        data = json.loads(r.stdout.strip() or "[]")
    except Exception:
        return []
    return data if isinstance(data, list) else [data]


def truth(pid: int) -> dict:
    if not MEM6.exists():
        return {"error": f"missing {MEM6}"}
    out = ROOT / "logs" / "doctor_truth.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(MEM6), str(pid), str(out)], capture_output=True)
    if r.returncode != 0:
        return {"error": r.stderr.decode("mbcs", "replace")[:200]}
    vals, cur = {}, None
    for line in out.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("ParaName = "):
            cur = line.split("=", 1)[1].strip()
        elif line.startswith("ParaValue = ") and cur in TRUTH_KEYS:
            vals[cur] = line.split("=", 1)[1].strip()
            cur = None
    return {k: vals.get(k) for k in TRUTH_KEYS}


def count_nonempty_edits(tc: Toolchain, pid: int) -> int:
    out = ROOT / "logs" / "doctor_table.txt"
    tc.uia_dump(pid, str(out))
    text = out.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(r"VALUE=\[[^\]]+\]", text))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--no-truth", action="store_true")
    args = ap.parse_args()

    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])

    # platform page info through UIA (no screenshot)
    subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "platform_info.py")],
                   capture_output=True)
    pinfo = {}
    pj = ROOT / "logs" / "platform.json"
    if pj.exists():
        pinfo = json.loads(pj.read_text(encoding="utf-8"))

    ps = procs()
    main_proc = next((p for p in ps if p.get("ProcessName", "").lower() == "main"), None)
    pid = args.pid or (main_proc or {}).get("Id", 0)

    wins = tc.wins()
    data = next((w for w in wins if w["title"] == "实验数据表格"), None)
    views = [w for w in wins if w["title"] in ("带孔薄板", "100张纸")]
    main_win = next((w for w in wins if w["title"] == "误差配套实验"), None)

    report = {
        "platform_http": http_status(PLATFORM),
        "processes": ps,
        "platform": pinfo,
        "windows": {
            "main": main_win,
            "data": data,
            "views": views,
        },
        "table_nonempty_edits": count_nonempty_edits(tc, pid) if pid and data else None,
        "truth": {} if args.no_truth or not pid else truth(pid),
        "tools": {
            "input": str(tc.input), "ui": str(tc.ui),
            "mem6": str(MEM6), "mem6_exists": MEM6.exists(),
        },
    }
    out = ROOT / "logs" / "doctor.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f'platform={report["platform_http"]} account={pinfo.get("account")} lab={pinfo.get("lab")}')
    print(f'processes={[ (p.get("Id"), p.get("ProcessName")) for p in ps ]}')
    print(f'main={main_win and main_win["rect"]} data={data and data["rect"]} views={len(views)}')
    print(f'table_nonempty_edits={report["table_nonempty_edits"]}')
    if report["truth"]:
        print(f'truth={report["truth"]}')
    print(f'WROTE {out}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
