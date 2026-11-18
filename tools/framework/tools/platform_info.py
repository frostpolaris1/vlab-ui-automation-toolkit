# -*- coding: utf-8 -*-
"""Read platform page info through UI Automation (no screenshots, no OCR).

Extracts: URL, account name ("xxx，欢迎您"), lab name, and the "开始实验" button
rectangle. Writes logs/platform.json and prints a one-line summary.

Usage: py -3 -I tools/platform_info.py [--edge-title Edge]
"""
import argparse
import json
import re
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

ADDR_RE = re.compile(r"Edit name=\[地址和搜索栏\].*?VALUE=\[(?P<url>[^\]]*)\]")
ACCT_RE = re.compile(r"ListItem name=\[(?P<name>[^，\]]+)，欢迎您")
LAB_RE = re.compile(r"Document name=\[(?P<name>[^\]]+)\] aid=\[RootWebArea\]")
START_RE = re.compile(r"Hyperlink name=\[开始实验\].*?@(?P<x>-?\d+),(?P<y>-?\d+),(?P<w>\d+)x(?P<h>\d+)")


def parse(text: str) -> dict:
    out = {"url": None, "account": None, "page_title": None, "lab": None, "start_button": None}
    m = ADDR_RE.search(text)
    if m:
        out["url"] = m.group("url").strip()
    m = ACCT_RE.search(text)
    if m:
        out["account"] = m.group("name").strip()
    m = LAB_RE.search(text)
    if m:
        out["page_title"] = m.group("name").strip()
    # breadcrumb: "所在位置：仿真实验 /" followed by Text name=[误差配套]
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "所在位置" in line:
            for follow in lines[i + 1:i + 8]:
                mm = re.search(r"Text name=\[(?P<n>[^\]]+)\].*?TEXT=", follow)
                if mm:
                    name = mm.group("n").strip()
                    if name and name != "/":
                        out["lab"] = name
                        break
            break
    m = START_RE.search(text)
    if m:
        x, y, w, h = (int(m.group(k)) for k in ("x", "y", "w", "h"))
        out["start_button"] = {"rect": [x, y, w, h], "center": [x + w // 2, y + h // 2]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge-title", default="Edge")
    args = ap.parse_args()

    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    w = tc.find(args.edge_title)
    if not w:
        print("Edge window not found")
        return 1
    dump = ROOT / "logs" / "uia_edge_page.txt"
    dump.parent.mkdir(parents=True, exist_ok=True)
    tc.uia_dump(w["pid"], str(dump), max_nodes=8000)
    info = parse(dump.read_text(encoding="utf-8", errors="replace"))
    info.update({"edge_hwnd": w["hwnd"], "edge_pid": w["pid"], "edge_rect": w["rect"]})

    out = ROOT / "logs" / "platform.json"
    out.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f'account={info["account"]} lab={info["lab"]} page_title={info["page_title"]} url={info["url"]}')
    print(f'start_button={info["start_button"]} -> {out}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
