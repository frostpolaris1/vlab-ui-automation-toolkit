# -*- coding: utf-8 -*-
"""Submit the data table and capture the receipt dialog end-to-end.

- fronts the data window and clicks the submit button
- waits for ShowMessageBox, reads tbMessage via UIA
- saves a 1:1 crop of the dialog (mkdir -p safe)
- clicks the OK button from its real UIA rect
- exits 0 only if the message equals/contains the expected text

Usage:
    py -3 -I tools/receipt.py --pid 1234 --shot shots/submit_receipt_success.png
    py -3 -I tools/receipt.py --submit-point 2990,930 --expect 提交成功
"""
import argparse
import json
import re
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

MSG_RE = re.compile(r"Text name=\[(?P<msg>.*?)\] aid=\[tbMessage\].*?@(?P<x>-?\d+),(?P<y>-?\d+),(?P<w>\d+)x(?P<h>\d+)")
BTN_RE = re.compile(r"Button name=\[(?P<name>.*?)\] aid=\[btn01\].*?@(?P<x>-?\d+),(?P<y>-?\d+),(?P<w>\d+)x(?P<h>\d+)")
CAP_RE = re.compile(r"Text name=\[(?P<cap>.*?)\] aid=\[tbCaption\]")


def parse_dialog(text: str) -> dict:
    out = {"message": None, "caption": None, "button": None}
    m = MSG_RE.search(text)
    if m:
        out["message"] = m.group("msg")
    m = CAP_RE.search(text)
    if m:
        out["caption"] = m.group("cap")
    m = BTN_RE.search(text)
    if m:
        x, y, w, h = (int(m.group(k)) for k in ("x", "y", "w", "h"))
        out["button"] = {"name": m.group("name"), "rect": [x, y, w, h],
                         "center": [x + w // 2, y + h // 2]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--submit-point", default="2990,930")
    ap.add_argument("--expect", default="提交成功")
    ap.add_argument("--shot", default="")
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--no-click", action="store_true", help="capture only, do not submit")
    args = ap.parse_args()

    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    data = tc.find("实验数据表格")
    if not data:
        print("data window not found")
        return 1
    pid = args.pid or data["pid"]

    if not args.no_click:
        sx, sy = (int(v) for v in args.submit_point.split(","))
        tc.front(data["hwnd"])
        tc.click(sx, sy)

    # wait for the modal
    deadline = time.time() + args.timeout
    box = None
    while time.time() < deadline:
        box = tc.find("ShowMessageBox", pid=pid)
        if box:
            break
        time.sleep(0.3)
    if not box:
        print("ShowMessageBox not found (submit may have failed or the dialog closed)")
        return 2

    l, t, r, b = box["rect"]
    shot_path = Path(args.shot) if args.shot else ROOT / "logs" / "submit_receipt.png"
    shot_path.parent.mkdir(parents=True, exist_ok=True)
    tc.shot(str(shot_path), [l, t, max(1, r - l), max(1, b - t)])

    dump = ROOT / "logs" / "uia_submit_dialog.txt"
    tc.uia_dump(pid, str(dump))
    info = parse_dialog(dump.read_text(encoding="utf-8", errors="replace"))
    info.update({"dialog_rect": box["rect"], "screenshot": str(shot_path)})

    print(json.dumps(info, ensure_ascii=False))
    ok = bool(info["message"]) and args.expect in info["message"]

    if info["button"]:
        cx, cy = info["button"]["center"]
        tc.click(cx, cy)
    else:
        # fallback: click the dialog's lower middle
        tc.click(l + (r - l) // 2, t + int((b - t) * 0.8))

    tc.sleep(0.5)
    gone = tc.find("ShowMessageBox", pid=pid) is None
    print(f"message={info['message']!r} expect={args.expect!r} ok={ok} dialog_closed={gone}")
    return 0 if (ok and gone) else 3


if __name__ == "__main__":
    sys.exit(main())
