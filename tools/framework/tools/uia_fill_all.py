# -*- coding: utf-8 -*-
"""Fill ALL data-table fields through UIA (scroll- and keyboard-independent).

Maps fill_values.json onto the client's Edit elements by UI structure:
- Choose1-7       : next sibling Edit after the matching "选择测量..." label
- GB/paper 6x grid: Edit descendants of the "测量次数" pane, column-major
- GB stats (7-30) : number of the "(n) ..." label -> fixed field order
- paper stats(6-12): same
- B-class tables   : Edit descendants of the "(1) 根据参数..." containers

Usage:
    py -3 -I tools/uia_fill_all.py [--pid PID] [--fill fill_values.json] [--dry-run]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.controller import Toolchain  # noqa: E402

LINE_RE = re.compile(
    r"^(?P<indent> *)(?P<type>[A-Za-z]+) name=\[(?P<name>.*?)\] aid=\[(?P<aid>.*?)\]"
    r"(?: VALUE=\[(?P<value>.*?)\])?(?: @(?P<x>-?\d+),(?P<y>-?\d+),(?P<w>\d+)x(?P<h>\d+))?$"
)

GB_STATS_ORDER = [
    "avg.L", "S.L", "dA.L", "dB.L", "d.L",
    "avg.B", "S.B", "dA.B", "dB.B", "d.B",
    "avg.H", "S.H", "dA.H", "dB.H", "d.H",
    "avg.D", "S.D", "dA.D", "dB.D", "d.D",
    "V", "rel", "dV", "expr",
]
PAPER_STATS_ORDER = ["avg.L", "avg.B", "avg.H", "V", "rel", "dV", "expr"]


class Node:
    __slots__ = ("idx", "depth", "type", "name", "value", "x", "y", "parent", "children")

    def __init__(self, idx, depth, typ, name, value, x, y, parent):
        self.idx = idx
        self.depth = depth
        self.type = typ
        self.name = name
        self.value = value
        self.x = x
        self.y = y
        self.parent = parent
        self.children = []


def parse_dump(text: str):
    nodes = []
    stack = []
    in_data = False
    for raw in text.splitlines():
        line = raw.lstrip("\ufeff")
        if line.startswith("===== WINDOW"):
            in_data = "实验数据表格" in line
            continue
        if not in_data:
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        depth = len(m.group("indent")) // 2
        while stack and stack[-1].depth >= depth:
            stack.pop()
        parent = stack[-1] if stack else None
        n = Node(
            len(nodes), depth, m.group("type"), m.group("name") or "",
            m.group("value"), int(m.group("x")) if m.group("x") else None,
            int(m.group("y")) if m.group("y") else None, parent,
        )
        if parent:
            parent.children.append(n)
        nodes.append(n)
        stack.append(n)
    return nodes


def subtree(node: Node):
    out = [node]
    for c in node.children:
        out.extend(subtree(c))
    return out


def next_sibling_edit(node: Node):
    if node.parent is None:
        return None
    sibs = node.parent.children
    try:
        i = sibs.index(node)
    except ValueError:
        return None
    for s in sibs[i + 1:]:
        if s.type == "Edit":
            return s
    return None


def get_path(fill: dict, dotted: str):
    cur = fill
    for part in dotted.split("."):
        cur = cur[part]
    return str(cur)


def build_mapping(nodes, fill):
    edits = [n for n in nodes if n.type == "Edit"]
    index_of = {id(n): i for i, n in enumerate(edits)}

    paper_header = next((n for n in nodes if n.type == "Text" and "2. 测量一张纸" in n.name), None)
    paper_at = paper_header.idx if paper_header else 10 ** 9

    mapping = {}

    def put(edit, value, why):
        if edit is None:
            print(f"WARN missing edit for {why}")
            return
        i = index_of.get(id(edit))
        if i is None:
            print(f"WARN edit not in list for {why}")
            return
        mapping[i] = value

    # --- choose fields ---
    choose_keys = {
        "带孔薄板长度": 0, "带孔薄板宽度": 1, "带孔薄板厚度": 2, "带孔薄板孔径": 3,
        "100张纸长度": 4, "100张纸宽度": 5, "100张纸厚度": 6,
    }
    for n in nodes:
        if n.type != "Text" or "选择测量" not in n.name:
            continue
        for key, ci in choose_keys.items():
            if key in n.name:
                put(next_sibling_edit(n), fill["choose"][ci], n.name[:24])
                break

    # --- 6x grids ---
    grids_seen = {"gb": False, "paper": False}
    for n in nodes:
        if n.type != "Pane":
            continue
        kids = subtree(n)
        names = [k.name for k in kids if k.type == "Text"]
        if "测量次数" not in names:
            continue
        gedits = [k for k in kids if k.type == "Edit"]
        # ancestor containers also contain "测量次数"; the real grid pane has 18/24 edits
        if len(gedits) not in (18, 24):
            continue
        is_paper = n.idx > paper_at
        rows = ["L", "B", "H"] if is_paper else ["L", "B", "H", "D"]
        block = fill["paper"] if is_paper else fill["gb"]
        if len(gedits) != len(rows) * 6:
            continue
        flat = []
        for c in range(6):
            for r in rows:
                flat.append(block["data"][r][c])
        for e, v in zip(gedits, flat):
            put(e, v, f"grid paper={is_paper}")
        grids_seen["paper" if is_paper else "gb"] = True
    for key, seen in grids_seen.items():
        if not seen:
            print(f"WARN {key} grid not mapped")

    # --- stats by label number ---
    for n in nodes:
        if n.type != "Text":
            continue
        m = re.match(r"^\((\d+)\)", n.name)
        if not m or "选择测量" in n.name or "根据参数" in n.name:
            continue
        num = int(m.group(1))
        is_paper = n.idx > paper_at
        if is_paper:
            if 6 <= num <= 12:
                put(next_sibling_edit(n), get_path(fill["paper"], PAPER_STATS_ORDER[num - 6]),
                    f"paper stat {num}")
        else:
            if 7 <= num <= 30:
                put(next_sibling_edit(n), get_path(fill["gb"], GB_STATS_ORDER[num - 7]),
                    f"gb stat {num}")

    # --- B-class tables ---
    b_headers = [n for n in nodes if n.type == "Text" and "根据参数计算下列B类不确定度" in n.name]
    for h in b_headers:
        if h.parent is None:
            continue
        bedits = [k for k in subtree(h.parent) if k.type == "Edit"]
        is_paper = h.idx > paper_at
        table = fill["table3"] if is_paper else fill["table1"]
        ncols = 3 if is_paper else 4
        if len(bedits) != 3 * ncols:
            print(f"WARN B table count {len(bedits)} != {3*ncols} (paper={is_paper})")
            continue
        flat = [table[r][c] for c in range(ncols) for r in ("ruler", "caliper", "mic")]
        for e, v in zip(bedits, flat):
            put(e, v, f"B table paper={is_paper}")

    return edits, mapping


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--fill", default=str(ROOT / "fill_values.json"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    iface = json.loads((ROOT / "interface.json").read_text(encoding="utf-8"))
    tc = Toolchain(iface["controller"]["tool_dir"])
    data = tc.find("实验数据表格")
    if not data:
        print("data window not found")
        return 1
    pid = args.pid or data["pid"]

    fill = json.loads(Path(args.fill).read_text(encoding="utf-8"))
    dump = ROOT / "logs" / "uia_fill_all.txt"
    tc.uia_dump(pid, str(dump))
    nodes = parse_dump(dump.read_text(encoding="utf-8", errors="replace"))
    edits, mapping = build_mapping(nodes, fill)

    covered = len(mapping)
    missing = [i for i in range(len(edits)) if i not in mapping]
    print(f"edits={len(edits)} mapped={covered} unmapped={len(missing)}")
    if missing:
        for i in missing[:10]:
            e = edits[i]
            print(f"  unmapped[{i}] @({e.x},{e.y}) value={e.value!r}")
    if covered != len(edits):
        print("WARN: not every Edit is mapped (expected 101 on a full data table)")

    if args.dry_run:
        for i in sorted(mapping)[:8]:
            print(f"  dry {i} -> {mapping[i]}")
        print("DRY RUN OK")
        return 0

    payload = {str(i): v for i, v in mapping.items()}
    out_json = ROOT / "logs" / "fill_all_values.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    tc.front(data["hwnd"])
    script = ROOT / "tools" / "uia_set_by_index.ps1"
    res = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
         "-Pid_", str(pid), "-JsonPath", str(out_json), "-DataTitle", "实验数据表格"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print((res.stdout or "").strip())
    if res.returncode != 0:
        print("STDERR:", (res.stderr or "").strip()[:500])
        return res.returncode
    print(f"FILLED {covered} fields via UIA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
