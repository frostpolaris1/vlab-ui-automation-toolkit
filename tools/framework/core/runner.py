# -*- coding: utf-8 -*-
"""
MAA-inspired pipeline runner for the VLab framework.

Pipeline JSON:
{
  "entry": "Start",
  "tasks": {
    "Start": {"action": "find_windows", "params": {...}, "next": "Pin"},
    ...
  }
}

Task fields:
- action: one of compliance.ALLOWED_ACTIONS
- params: dict (supports {{dotted.path}} resolution)
- next: next task name or null
- retry: int (default 0)
- on_fail: "agent" | task name | null
- timeout: seconds (soft; actions have their own timeouts)

Design goals:
- Deterministic fixed flow; agent only intervenes on explicit fallback.
- Every action is logged; screenshots/state are evidence.
- No arbitrary shell; only whitelisted helper scripts.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from . import compliance, recognition
from .controller import Toolchain

ROOT = Path(__file__).resolve().parents[1]


class Runner:
    def __init__(self, interface_path: str, experiment_id: Optional[str] = None, dry_run: bool = False):
        self.interface_path = Path(interface_path).resolve()
        self.root = self.interface_path.parent
        self.interface = json.loads(self.interface_path.read_text(encoding="utf-8"))
        self.dry_run = dry_run
        self.tc = Toolchain(self.interface["controller"]["tool_dir"])
        self.audit = compliance.AuditLog(str(self.root / "logs" / "run.jsonl"))

        exps = self.interface["experiments"]
        if experiment_id:
            exps = [e for e in exps if e["id"] == experiment_id]
            if not exps:
                raise SystemExit(f"experiment not found: {experiment_id}")
        self.exp_meta = exps[0]
        self.pipeline = json.loads((self.root / self.exp_meta["pipeline"]).read_text(encoding="utf-8"))
        self.experiment = json.loads((self.root / self.exp_meta["experiment"]).read_text(encoding="utf-8"))
        self.anchors_path = self.root / self.exp_meta["anchors"]
        self.anchors = json.loads(self.anchors_path.read_text(encoding="utf-8")) if self.anchors_path.exists() else {}

        self.ctx: dict[str, Any] = {
            "hwnds": {},
            "pids": {},
            "anchors": self.anchors,
            "experiment": self.experiment,
            "vars": {},
            "macro": {},
        }
        self.measurements: dict[str, list[float]] = {}
        self.current_task: Optional[str] = None
        self._load_measurements()

    # ---------- context ----------
    def _load_measurements(self) -> None:
        p = self.root / "measurements.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            for section in ("paper", "gb"):
                for k, vals in data.get(section, {}).items():
                    self.measurements[f"{section}.{k}"] = list(vals)

    def _save_measurements(self) -> None:
        out = {"paper": {}, "gb": {}, "n_holes": self.experiment.get("n_holes", 5)}
        for key, vals in self.measurements.items():
            section, name = key.split(".", 1)
            out.setdefault(section, {})[name] = vals
        (self.root / "measurements.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def lookup(self, path: str) -> Any:
        # macro-local variables: {{object}}, {{option}}, {{instrument}}, ...
        if "." not in path and path in self.ctx.get("macro", {}):
            return self.ctx["macro"][path]
        try:
            return self._dig(self.ctx, path)
        except KeyError:
            # anchors live under ctx["anchors"] but are addressed as paper.* / gb.* / data.*
            return self._dig(self.ctx.get("anchors", {}), path)

    @staticmethod
    def _dig(obj: Any, path: str) -> Any:
        cur: Any = obj
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
                cur = cur[int(part)]
            else:
                raise KeyError(f"cannot resolve: {path}")
        return cur

    def resolve(self, value: Any) -> Any:
        if isinstance(value, str):
            def repl(m):
                return str(self.lookup(m.group(1)))
            return re.sub(r"\{\{([^}]+)\}\}", repl, value)
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        return value

    # ---------- anchors / coordinates ----------
    def _window_key(self, params: dict) -> str:
        return params.get("window", "view")

    def _window_origin(self, key: str) -> tuple[int, int]:
        hwnd = self.ctx["hwnds"].get(key)
        if not hwnd:
            raise RuntimeError(f"window not found: {key}")
        return self.tc.origin(hwnd)

    def resolve_xy(self, target: Any, window_key: str = "view") -> tuple[int, int]:
        if isinstance(target, (list, tuple)) and len(target) == 2:
            rel = (int(target[0]), int(target[1]))
            ox, oy = self._window_origin(window_key)
            return ox + rel[0], oy + rel[1]
        if isinstance(target, str):
            anchor = self.lookup(target)
            if isinstance(anchor, (list, tuple)) and len(anchor) == 2:
                ox, oy = self._window_origin(window_key)
                return ox + int(anchor[0]), oy + int(anchor[1])
            if isinstance(anchor, dict):
                if "screen" in anchor:
                    return int(anchor["screen"][0]), int(anchor["screen"][1])
                if "rel" in anchor:
                    wk = anchor.get("window", window_key)
                    ox, oy = self._window_origin(wk)
                    return ox + int(anchor["rel"][0]), oy + int(anchor["rel"][1])
                if "x" in anchor and "y" in anchor:
                    ox, oy = self._window_origin(window_key)
                    return ox + int(anchor["x"]), oy + int(anchor["y"])
            raise ValueError(f"bad anchor: {target} -> {anchor}")
        raise ValueError(f"bad target: {target}")

    # ---------- action dispatch ----------
    def do(self, action: str, params: dict) -> bool:
        compliance.check_action(action, params)
        params = self.resolve(params)
        self.audit.write({"task": self.current_task, "action": action, "params": params, "dry_run": self.dry_run})
        dry_skip = {
            "find_windows", "pin_windows", "click", "dblclick", "rightclick", "drag", "hold",
            "wheel", "type", "key", "chord", "clipboard_set", "clipboard_get", "uia_read",
            "wait_stable", "wait_message", "screenshot", "record", "fill", "verify", "submit",
            "decrypt", "run_script", "agent_fallback", "assert", "sleep",
        }
        if self.dry_run and action in dry_skip:
            print(f"[dry] {action} {params}")
            return True
        fn = getattr(self, f"act_{action}", None)
        if fn is None:
            raise NotImplementedError(f"action not implemented: {action}")
        try:
            return bool(fn(params))
        except Exception as e:
            return self._fallback(action, f"{type(e).__name__}: {e}")

    # ---------- actions ----------
    def act_find_windows(self, p: dict) -> bool:
        titles = p["titles"]
        for key, title in titles.items():
            w = self.tc.find(title)
            if not w:
                return self._fallback("find_windows", f"window not found: {title}")
            self.ctx["hwnds"][key] = w["hwnd"]
            self.ctx["pids"][key] = w["pid"]
            print(f"window {key}: hwnd={w['hwnd']} pid={w['pid']} title={w['title']}")
        return True

    def act_pin_windows(self, p: dict) -> bool:
        for key, pos in p.get("layout", {}).items():
            hwnd = self.ctx["hwnds"].get(key)
            if not hwnd:
                return self._fallback("pin_windows", f"missing hwnd: {key}")
            self.tc.move(hwnd, int(pos[0]), int(pos[1]))
        # view may not exist yet (opened by the first measure setup)
        self.tc.front(self.ctx["hwnds"].get("view") or self.ctx["hwnds"]["main"])
        return True

    def act_check_anchors(self, p: dict) -> bool:
        if not self.anchors.get("calibrated"):
            return self._fallback("check_anchors", "anchors.json not calibrated; take a screenshot and fill anchors")
        return True

    def act_click(self, p: dict) -> bool:
        x, y = self.resolve_xy(p["target"], self._window_key(p))
        self.tc.click(x, y)
        return True

    def act_dblclick(self, p: dict) -> bool:
        x, y = self.resolve_xy(p["target"], self._window_key(p))
        self.tc.dblclick(x, y)
        return True

    def act_rightclick(self, p: dict) -> bool:
        x, y = self.resolve_xy(p["target"], self._window_key(p))
        self.tc.rightclick(x, y)
        return True

    def act_drag(self, p: dict) -> bool:
        wk = self._window_key(p)
        x1, y1 = self.resolve_xy(p["from"], wk)
        x2, y2 = self.resolve_xy(p["to"], wk)
        self.tc.drag(x1, y1, x2, y2, int(p.get("ms", 700)))
        return True

    def act_hold(self, p: dict) -> bool:
        wk = self._window_key(p)
        x, y = self.resolve_xy(p["target"], wk)
        right = bool(p.get("right", False))
        for _ in range(int(p.get("repeat", 1))):
            self.tc.hold(x, y, int(p.get("ms", 800)), right)
            time.sleep(float(p.get("gap", 0.08)))
        return True

    def act_wheel(self, p: dict) -> bool:
        wk = self._window_key(p)
        x, y = self.resolve_xy(p["target"], wk)
        self.tc.wheel(x, y, int(p["notches"]))
        return True

    def act_type(self, p: dict) -> bool:
        self.tc.type_text(str(p["text"]))
        return True

    def act_key(self, p: dict) -> bool:
        self.tc.key(int(p["vk"]))
        return True

    def act_chord(self, p: dict) -> bool:
        self.tc.chord(int(p["mod"]), int(p["vk"]))
        return True

    def act_clipboard_set(self, p: dict) -> bool:
        self.tc.clipboard_set(str(p["text"]))
        return True

    def act_clipboard_get(self, p: dict) -> bool:
        cps = self.tc.clipboard_codepoints()
        self.ctx["vars"]["clipboard_codepoints"] = cps
        print("clipboard codepoints:", cps)
        return True

    def act_uia_read(self, p: dict) -> bool:
        pid = self.ctx["pids"][p.get("window", "view")]
        state = recognition.read_state(self.tc, pid)
        self.ctx["vars"]["state"] = state
        print("uia:", state)
        return True

    def act_wait_stable(self, p: dict) -> bool:
        pid = self.ctx["pids"][p.get("window", "view")]
        res = recognition.wait_stable(
            self.tc, pid, p.get("key", "ValueText2"),
            timeout=float(p.get("timeout", 12)), interval=float(p.get("interval", 0.25)),
            stable_polls=int(p.get("stable_polls", 4)),
        )
        self.ctx["vars"]["stable"] = res
        print("stable:", res)
        return bool(res["ok"])

    def act_wait_message(self, p: dict) -> bool:
        pid = self.ctx["pids"][p.get("window", "view")]
        res = recognition.wait_message(self.tc, pid, p["substr"], float(p.get("timeout", 6)))
        self.ctx["vars"]["message"] = res
        print("message:", res)
        return bool(res["ok"])

    def act_screenshot(self, p: dict) -> bool:
        wk = p.get("window", "view")
        hwnd = self.ctx["hwnds"][wk]
        path = str(self.root / p.get("path", f"logs/shots/{wk}_{int(time.time())}.png"))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.tc.shot_window(hwnd, path)
        self.ctx["vars"]["last_screenshot"] = path
        print("shot:", path)
        return True

    def act_sleep(self, p: dict) -> bool:
        time.sleep(float(p.get("seconds", 0.5)))
        return True

    def act_log(self, p: dict) -> bool:
        print(p.get("message", ""))
        return True

    def act_set_var(self, p: dict) -> bool:
        self.ctx["vars"][p["name"]] = p.get("value")
        return True

    def act_assert(self, p: dict) -> bool:
        actual = self.lookup(p["path"])
        if "contains" in p:
            ok = str(p["contains"]) in str(actual)
        elif "equals" in p:
            ok = str(actual) == str(p["equals"])
        elif "nonempty" in p:
            ok = bool(str(actual).strip())
        else:
            ok = bool(actual)
        if not ok:
            return self._fallback("assert", f"assert failed: {p['path']} = {actual!r}")
        return True

    # ---------- measure ----------
    def act_measure(self, p: dict) -> bool:
        instrument = p["instrument"]
        macro_def = self.experiment["macros"][instrument]
        if isinstance(macro_def, list):
            setup, repeat = [], macro_def
        else:
            setup, repeat = macro_def.get("setup", []), macro_def.get("repeat", [])
        store = p["store"]
        times = int(p.get("times", 6))
        self.measurements.setdefault(store, [])
        existing = len(self.measurements[store])
        if existing >= times:
            print(f"{store}: already has {existing} readings, skip")
            return True
        self.ctx["macro"] = {
            "object": p["object"], "option": p["option"], "instrument": instrument,
            "store": store, "iteration": existing, "decimals": p.get("decimals"),
            "view_title": self.experiment.get("objects", {}).get(p["object"], {}).get("view_title", ""),
        }
        if existing == 0:
            for step in setup:
                step = dict(step)
                action = step.pop("action")
                if not self.do(action, step):
                    return False
        for i in range(existing + 1, times + 1):
            self.ctx["macro"]["iteration"] = i
            for step in repeat:
                step = dict(step)
                action = step.pop("action")
                ok = self.do(action, step)
                if not ok:
                    return False
            self._save_measurements()
            print(f"measured {store} #{i}: {self.measurements[store][-1] if self.measurements[store] else '?'}")
        return True

    def act_record(self, p: dict) -> bool:
        """Special action used inside a measure macro."""
        pid = self.ctx["pids"].get(p.get("window", "view"))
        state = recognition.read_state(self.tc, pid)
        key = p.get("key", "ValueText2")
        raw = state.get(key, "")
        num = recognition.extract_number(raw)
        if num is None:
            return self._fallback("record", f"cannot parse {key}={raw!r}", state)
        if "min" in p and num < float(p["min"]):
            return self._fallback("record", f"{key}={num} below min {p['min']}", state)
        if "max" in p and num > float(p["max"]):
            return self._fallback("record", f"{key}={num} above max {p['max']}", state)
        store = self.ctx["macro"]["store"]
        self.measurements.setdefault(store, []).append(num)
        self.ctx["vars"]["last_reading"] = {"raw": raw, "value": num, "state": state}
        print(f"record {store}: {num} (raw={raw!r})")
        return True

    # ---------- fill / verify ----------
    def act_fill(self, p: dict) -> bool:
        values = json.loads((self.root / p["values"]).read_text(encoding="utf-8"))
        fill = self.experiment["fill"]
        data_hwnd = self.ctx["hwnds"]["data"]
        self.tc.front(data_hwnd)
        # scroll to top (best effort)
        ox, oy = self.tc.origin(data_hwnd)
        self.tc.wheel(ox + 600, oy + 300, -20)
        time.sleep(0.5)
        for grid in fill.get("grids", []):
            anchor = self.lookup(grid["anchor"])
            origin = anchor["origin"]
            cw, ch = anchor["cell_w"], anchor["cell_h"]
            data = self._dig(values, grid["values"])
            for r, row_key in enumerate(grid["rows"]):
                for c in range(int(grid["cols"])):
                    val = data[row_key][c]
                    x = ox + origin[0] + c * cw
                    y = oy + origin[1] + r * ch
                    self.tc.dblclick(x, y)
                    self.tc.ctrl_a()
                    self.tc.type_text(str(val))
                    self.tc.enter()
                    time.sleep(0.05)
            self.act_screenshot({"window": "data", "path": f"logs/shots/fill_{grid['anchor'].replace('.', '_')}.png"})
        for single in fill.get("singles", []):
            anchor = self.lookup(single["anchor"])
            val = str(self._dig(values, single["value"]))
            x = ox + anchor["rel"][0]
            y = oy + anchor["rel"][1]
            self.tc.dblclick(x, y)
            self.tc.ctrl_a()
            if "±" in val:
                self.tc.clipboard_set(val)
                self.tc.ctrl_v()
            else:
                self.tc.type_text(val)
            self.tc.enter()
            time.sleep(0.05)
        return True

    def act_verify(self, p: dict) -> bool:
        # Gate: take screenshots of the data window at current scroll; the agent
        # visually confirms. UIA single-value check is a best-effort extra.
        self.act_screenshot({"window": "data", "path": "logs/shots/verify_data.png"})
        print("verify: screenshot saved; agent must visually confirm before submit")
        return True

    # ---------- submit / audit ----------
    def act_submit(self, p: dict) -> bool:
        x, y = self.resolve_xy(p["anchor"], "data")
        self.tc.click(x, y)
        time.sleep(1.0)
        # find the message box (same pid as main, title usually "提示")
        main_pid = self.ctx["pids"]["main"]
        box = None
        for w in self.tc.wins():
            if w["pid"] == main_pid and ("提示" in w["title"] or "提交" in w["title"]):
                box = w
                break
        if not box:
            return self._fallback("submit", "submit message box not found")
        self.tc.front(box["hwnd"])
        dump = str(self.root / "logs" / "submit_box.txt")
        self.tc.uia_dump(main_pid, dump)
        text = Path(dump).read_text(encoding="utf-8", errors="replace")
        if "提交成功" in text:
            self.tc.enter()  # default OK
            return True
        return self._fallback("submit", f"submit failed: {text[-500:]}")

    def act_decrypt(self, p: dict) -> bool:
        import glob
        bins = glob.glob(str(Path.home() / "AppData" / "Local" / "Temp" / "lab" / "*" / "SimExpConfig" / "ExamConfig.bin"))
        if not bins:
            return self._fallback("decrypt", "no live ExamConfig.bin found")
        latest = max(bins, key=lambda x: Path(x).stat().st_mtime)
        out = str(self.root / "saved_exam.xml")
        script = self.root / "tools" / "decrypt_examconfig.ps1"
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
               "-BinPath", latest, "-OutPath", out]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        print(r.stdout.strip())
        if r.returncode != 0:
            return self._fallback("decrypt", r.stderr.strip())
        self.ctx["vars"]["saved_exam"] = out
        return True

    def act_run_script(self, p: dict) -> bool:
        name = p["script"]
        compliance.check_script(name)
        script = self.root / "tools" / name
        if not script.exists():
            script = self.root / name
        if not script.exists():
            return self._fallback("run_script", f"script not found: {name}")
        args = [str(a) for a in p.get("args", [])]
        if name.endswith(".py"):
            cmd = [sys.executable, "-I", str(script)] + args
        else:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)] + args
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(self.root))
        print(r.stdout.strip())
        if r.returncode != 0:
            return self._fallback("run_script", r.stderr.strip())
        return True

    # ---------- fallback ----------
    def _fallback(self, task: str, reason: str, state: Optional[dict] = None) -> bool:
        shot = None
        try:
            wk = "view" if task in ("record", "wait_stable") else "data"
            hwnd = self.ctx["hwnds"].get(wk)
            if hwnd:
                shot = str(self.root / "logs" / "shots" / f"fallback_{int(time.time())}.png")
                Path(shot).parent.mkdir(parents=True, exist_ok=True)
                self.tc.shot_window(hwnd, shot)
        except Exception:
            pass
        p = recognition.needs_agent(
            str(self.root / "logs"), task, reason, shot, state,
            {"next": self._next_of(self.current_task or task), "vars": self.ctx["vars"], "macro": self.ctx.get("macro", {})},
        )
        print(f"AGENT FALLBACK: {reason}\n  -> {p}")
        return False

    def _next_of(self, task: str) -> Optional[str]:
        return self.pipeline["tasks"].get(task, {}).get("next")

    def act_agent_fallback(self, p: dict) -> bool:
        return self._fallback(self.current_task or "agent", p.get("reason", "agent requested"))

    # ---------- main loop ----------
    def run(self, start: Optional[str] = None) -> int:
        task = start or self.pipeline.get("entry")
        while task:
            self.current_task = task
            spec = self.pipeline["tasks"].get(task)
            if not spec:
                print(f"unknown task: {task}")
                return 2
            print(f"\n== {task} ==")
            retry = int(spec.get("retry", 0))
            ok = False
            for attempt in range(retry + 1):
                ok = self.do(spec["action"], spec.get("params", {}))
                if ok:
                    break
                print(f"retry {attempt + 1}/{retry} for {task}")
                time.sleep(1.0)
            if not ok:
                on_fail = spec.get("on_fail")
                if on_fail == "agent":
                    return 3
                if on_fail:
                    task = on_fail
                    continue
                return 4
            task = spec.get("next")
        print("\nDONE")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interface", default=str(ROOT / "interface.json"))
    ap.add_argument("--experiment", default=None)
    ap.add_argument("--start", default=None)
    ap.add_argument("--anchors", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    runner = Runner(args.interface, args.experiment, dry_run=args.dry_run)
    if args.anchors:
        runner.anchors_path = Path(args.anchors).resolve()
        runner.anchors = json.loads(runner.anchors_path.read_text(encoding="utf-8"))
        runner.ctx["anchors"] = runner.anchors
    start = args.start
    if args.resume:
        p = runner.root / "logs" / "needs_agent.json"
        if p.exists():
            info = json.loads(p.read_text(encoding="utf-8"))
            start = info.get("context", {}).get("next")
            print(f"resume from: {start}")
    return runner.run(start)


if __name__ == "__main__":
    sys.exit(main())
