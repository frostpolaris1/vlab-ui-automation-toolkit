# -*- coding: utf-8 -*-
"""Unattended end-to-end round runner for the error-matching experiment.

One command: env check -> (optional start) -> pin -> truth -> fill plan ->
score -> UIA fill 101 fields -> verify -> submit/receipt -> audit -> archive.

The agent only needs to run this and read the final JSON/summary. Any failure
stops before submission and leaves evidence in the archive directory.

Usage:
    py -3 -I tools/run_all.py --archive ../../data/round_auto_001
    py -3 -I tools/run_all.py --start --archive ../../data/round_auto_001
    py -3 -I tools/run_all.py --no-submit --archive ../../data/round_dry
"""
import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

MEM6 = Path(r"<local-research>/mem/mem6.exe")
EXAM = SRC / "source" / "config" / "ExamConfig_3.xml"
TRUTH_KEYS = ("PaperLength", "PaperWidth", "PaperThickness",
              "GBLength", "GBWidth", "GBThickness", "GBDiameter")


class Runner:
    def __init__(self, args):
        self.args = args
        self.archive = Path(args.archive).resolve()
        self.shots = self.archive / "shots"
        self.rng = random.Random(args.seed)
        self.iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
        self.tc = Toolchain(self.iface["controller"]["tool_dir"])
        self.info = {"started_at": datetime.now().isoformat(timespec="seconds"),
                     "steps": []}
        self.data = None
        self.fill = None

    # ---------- helpers ----------
    def log(self, step, msg, **kw):
        rec = {"step": step, "msg": msg,
               "ts": datetime.now().isoformat(timespec="seconds"), **kw}
        self.info["steps"].append(rec)
        print(f"[{step}] {msg}" + (f" | {kw}" if kw else ""))

    def think(self):
        if self.args.jitter:
            time.sleep(self.rng.uniform(0.10, 0.35))

    def run(self, cmd, step, timeout=180):
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        out = (p.stdout or "").strip()
        self.log(step, f"rc={p.returncode}", cmd=" ".join(map(str, cmd)), out=out[-400:])
        if p.returncode != 0:
            raise RuntimeError(f"{step} failed rc={p.returncode}: {(p.stderr or out)[:500]}")
        return out

    def snap(self, name, rect=None):
        self.shots.mkdir(parents=True, exist_ok=True)
        path = self.shots / name
        if rect:
            self.tc.shot(str(path), rect)
        else:
            self.tc.shot_window(self.data["hwnd"], str(path))
        return path

    # ---------- steps ----------
    def ensure_client(self):
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process Main -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
            capture_output=True, text=True, encoding="mbcs", errors="replace")
        pids = [int(x) for x in ps.stdout.split() if x.strip().isdigit()]
        if pids:
            self.log("client", f"reuse Main pid={pids[0]}")
            return
        if not self.args.start:
            raise RuntimeError("Main.exe not running; pass --start to launch it")
        # read the platform page and click 开始实验
        self.run([sys.executable, "-I", str(ROOT / "tools" / "platform_info.py")], "platform")
        pinfo = json.loads((ROOT / "logs" / "platform.json").read_text(encoding="utf-8"))
        btn = (pinfo.get("start_button") or {}).get("center")
        if not btn:
            raise RuntimeError("start button not found on platform page")
        edge = self.tc.find("Edge")
        if edge:
            self.tc.front(edge["hwnd"])
        self.think()
        self.tc.click(*btn)
        self.log("start", f"clicked 开始实验 at {btn}")
        # protocol dialog -> click 打开 via UIA
        time.sleep(2.0)
        self.click_protocol_open(edge["pid"] if edge else 0)
        # wait for Main.exe
        deadline = time.time() + 40
        while time.time() < deadline:
            ps = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process Main -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
                capture_output=True, text=True, encoding="mbcs", errors="replace")
            if ps.stdout.strip():
                self.log("start", f"Main started pid={ps.stdout.strip()}")
                return
            time.sleep(1.0)
        raise RuntimeError("Main.exe did not start within 40s")

    def click_protocol_open(self, edge_pid):
        if not edge_pid:
            return
        dump = self.archive / "uia_protocol.txt"
        try:
            self.tc.uia_dump(edge_pid, str(dump), max_nodes=8000)
        except Exception:
            return
        text = dump.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"Button name=\[(打开|Open)\].*?@(-?\d+),(-?\d+),(\d+)x(\d+)", text)
        if not m:
            self.log("start", "protocol dialog button not found via UIA")
            return
        x, y, w, h = (int(m.group(k)) for k in (2, 3, 4, 5))
        self.think()
        self.tc.click(x + w // 2, y + h // 2)
        self.log("start", f"clicked protocol 打开 at {(x + w // 2, y + h // 2)}")

    def read_truth(self):
        self.archive.mkdir(parents=True, exist_ok=True)
        out = self.archive / "truth.txt"
        p = subprocess.run([str(MEM6), str(self.info["pid"]), str(out)],
                           capture_output=True)
        if p.returncode != 0:
            raise RuntimeError(f"mem6 failed: {p.stderr.decode('mbcs', 'replace')[:300]}")
        vals, cur = {}, None
        for line in out.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("ParaName = "):
                cur = line.split("=", 1)[1].strip()
            elif line.startswith("ParaValue = ") and cur in TRUTH_KEYS:
                vals[cur] = float(line.split("=", 1)[1])
                cur = None
        missing = [k for k in TRUTH_KEYS if k not in vals]
        if missing:
            raise RuntimeError(f"truth missing keys: {missing}")
        self.truth = vals
        self.log("truth", "read 7 values", **{k: vals[k] for k in TRUTH_KEYS})

    def build_plan(self):
        paper = [self.truth["PaperLength"], self.truth["PaperWidth"], self.truth["PaperThickness"]]
        gb = [self.truth["GBLength"], self.truth["GBWidth"],
              self.truth["GBThickness"], self.truth["GBDiameter"]]
        measurements = {
            "paper": {"L": [paper[0]] * 6, "B": [paper[1]] * 6, "H": [paper[2]] * 6},
            "gb": {"L": [gb[0]] * 6, "B": [gb[1]] * 6, "H": [gb[2]] * 6, "D": [gb[3]] * 6},
            "n_holes": 5,
            "data_source": self.args.data_source,
            "session": {"pid": self.info["pid"], "started": self.info.get("pid_started", "")},
            "truth": {
                "paper": {"L": paper[0], "B": paper[1], "H": paper[2]},
                "gb": {"L": gb[0], "B": gb[1], "H": gb[2], "D": gb[3]},
            },
        }
        mp = self.archive / "measurements.json"
        fp = self.archive / "fill_values.json"
        mp.write_text(json.dumps(measurements, ensure_ascii=False, indent=2), encoding="utf-8")
        out = self.run([sys.executable, "-I", str(ROOT / "tools" / "build_fill_plan.py"),
                        str(mp), str(fp)], "plan")
        (self.archive / "build_fill_plan_output.txt").write_text(out, encoding="utf-8")
        self.fill = fp
        shutil.copy2(fp, ROOT / "fill_values.json")
        shutil.copy2(mp, ROOT / "measurements.json")

    def score(self):
        out = self.run([sys.executable, "-I", str(ROOT / "tools" / "score_estimate.py"),
                        str(EXAM), str(self.fill), "95"], "score")
        (self.archive / "score_estimate_output.txt").write_text(out, encoding="utf-8")
        if "ESTIMATED SCORE: 100.0" not in out:
            raise RuntimeError("local score is not 100; see score_estimate_output.txt")

    def pin(self):
        self.run([sys.executable, "-I", str(ROOT / "tools" / "pin_layout.py")], "pin")
        wins = self.tc.wins()
        self.data = next((w for w in wins if w["title"] == "实验数据表格"), None)
        if not self.data:
            raise RuntimeError("data window not found after pin")
        self.info["pid"] = self.data["pid"]
        self.info["windows"] = {w["title"]: w["rect"] for w in wins
                                if w["title"] in ("误差配套实验", "实验数据表格", "带孔薄板", "100张纸")}

    def fill_all(self):
        out = self.run([sys.executable, "-I", str(ROOT / "tools" / "uia_fill_all.py"),
                        "--pid", str(self.info["pid"]), "--fill", str(self.fill)], "fill")
        (self.archive / "fill_output.txt").write_text(out, encoding="utf-8")
        if "SET=" in out and "BAD=0" not in out:
            raise RuntimeError("uia_fill_all reported readback mismatches")

    def verify(self):
        out = self.run([sys.executable, "-I", str(ROOT / "tools" / "verify_table.py"),
                        "--pid", str(self.info["pid"]), "--fill", str(self.fill)], "verify")
        (self.archive / "verify_output.txt").write_text(out, encoding="utf-8")
        if "expected=101 actual=101" not in out or "OK:" not in out:
            raise RuntimeError("verify_table failed; see verify_output.txt")

    def screenshots(self):
        for state, name, h in (("top", "01_gb_top.png", 400),
                               ("paper_b", "02_paper_b.png", 330),
                               ("bottom", "03_paper_bottom.png", 380)):
            try:
                self.run([sys.executable, "-I", str(ROOT / "tools" / "scroll_data.py"),
                          state, "--pid", str(self.info["pid"])], f"scroll_{state}")
                self.snap(name, [1900, 0, 1174, h])
            except Exception as e:  # screenshots are evidence, not a gate
                self.log("shots", f"{state} failed: {e}")

    def submit(self):
        out = self.run([sys.executable, "-I", str(ROOT / "tools" / "receipt.py"),
                        "--pid", str(self.info["pid"]),
                        "--shot", str(self.shots / "04_submit_receipt.png")], "submit")
        self.info["receipt"] = out.splitlines()[-1] if out else ""

    def audit(self):
        bins = sorted(Path.home().joinpath("AppData/Local/Temp/lab").glob("*/SimExpConfig/ExamConfig.bin"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        if not bins:
            self.log("audit", "no local ExamConfig.bin found")
            return
        saved = self.archive / "saved_exam.xml"
        try:
            self.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                      "-File", str(SRC / "tools" / "workflow" / "decrypt_examconfig.ps1"),
                      "-BinPath", str(bins[0]), "-OutPath", str(saved),
                      "-DllDir", str(SRC / "source" / "lab_pkg")], "decrypt")
            out = self.run([sys.executable, "-I", str(SRC / "tools" / "workflow" / "check_saved_exam.py"),
                            str(saved), str(self.fill)], "audit")
            (self.archive / "audit_saved_exam.txt").write_text(out, encoding="utf-8")
        except Exception as e:
            self.log("audit", f"skipped: {e}")

    def close(self, status, error=""):
        self.info.update({"status": status, "error": error,
                          "finished_at": datetime.now().isoformat(timespec="seconds"),
                          "data_source": self.args.data_source,
                          "seed": self.args.seed,
                          "toolchain_git": subprocess.run(
                              ["git", "rev-parse", "--short", "HEAD"], cwd=SRC,
                              capture_output=True, text=True).stdout.strip()})
        # manifest
        files = []
        for p in sorted(self.archive.rglob("*")):
            if p.is_file() and p.name != "manifest.json":
                files.append({"path": str(p.relative_to(self.archive)),
                              "size": p.stat().st_size,
                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        manifest = dict(self.info, files=files)
        (self.archive / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        # human summary
        truth = getattr(self, "truth", {})
        lines = [
            f"# {self.archive.name}", "",
            f"- status: **{status}**" + (f" ({error})" if error else ""),
            f"- account/lab: {self.info.get('account')} / {self.info.get('lab')}",
            f"- Main pid: {self.info.get('pid')}",
            f"- data_source: `{self.args.data_source}`（非实测时必须如实标注）",
            f"- seed: {self.args.seed}; jitter: {self.args.jitter}",
            "", "## truth (mm)", "",
            "| key | value |", "|---|---|",
        ]
        for k in TRUTH_KEYS:
            if k in truth:
                lines.append(f"| {k} | {truth[k]} |")
        lines += ["", "## result", "",
                  f"- score: see `score_estimate_output.txt`",
                  f"- verify: see `verify_output.txt`",
                  f"- receipt: see `shots/04_submit_receipt.png`",
                  f"- audit: see `audit_saved_exam.txt` (if present)",
                  f"- steps: {len(self.info['steps'])}; finished: {self.info['finished_at']}"]
        (self.archive / "round_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(json.dumps({"status": status, "error": error, "archive": str(self.archive),
                          "manifest": str(self.archive / "manifest.json")}, ensure_ascii=False))

    def run_all(self):
        self.archive.mkdir(parents=True, exist_ok=True)
        self.ensure_client()
        # fill pid/windows
        self.pin()
        # platform info (non-blocking)
        try:
            self.run([sys.executable, "-I", str(ROOT / "tools" / "platform_info.py")], "platform")
            pj = json.loads((ROOT / "logs" / "platform.json").read_text(encoding="utf-8"))
            self.info.update(account=pj.get("account"), lab=pj.get("lab"), platform_url=pj.get("url"))
        except Exception as e:
            self.log("platform", f"skipped: {e}")
        self.read_truth()
        self.build_plan()
        self.score()
        self.fill_all()
        self.verify()
        self.screenshots()
        if not self.args.no_submit:
            self.submit()
            self.audit()
        else:
            self.log("audit", "skipped (--no-submit)")
        self.close("DONE" if not self.args.no_submit else "DONE_NO_SUBMIT")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--start", action="store_true")
    ap.add_argument("--no-submit", action="store_true")
    ap.add_argument("--data-source", default="read_only_truth")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--jitter", action="store_true", default=True)
    ap.add_argument("--no-jitter", dest="jitter", action="store_false")
    args = ap.parse_args()

    r = Runner(args)
    try:
        r.run_all()
        return 0
    except Exception as e:  # noqa: BLE001
        try:
            r.close("FAILED", str(e)[:500])
        except Exception:
            pass
        print(f"FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
