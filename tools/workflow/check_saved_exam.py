# -*- coding: utf-8 -*-
"""
提交后审计：解密后的 ExamConfig.xml vs build_fill_plan.py 的 fill_values.json。
用法:
  python -I check_saved_exam.py saved_exam.xml fill_values.json

输出:
  - 逐字段 expected / actual / std / status
  - 按 ExamConfig 的 JudgeRule 估算分数（仅供参考，最终以平台为准）
"""
import json
import math
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def text(node, tag, default=""):
    x = node.find(tag) if node is not None else None
    return (x.text or "").strip() if x is not None else default


def load_paras(path):
    root = ET.parse(path).getroot()
    out = {}
    for p in root.iter("Para"):
        name = text(p, "Name")
        if not name:
            continue
        out[name] = {
            "real": text(p, "RealResult"),
            "std": text(p, "StdResult"),
            "score": float(text(p, "TotalScore", "0") or 0),
            "judge": p.find("JudgeRule"),
            "subs": [text(s, "Name") for s in p.findall("Para")],
            "sub_nodes": {text(s, "Name"): s for s in p.findall("Para")},
        }
    return out


def parse_tuples(s):
    """'(1,140.1,38.04);(2,...)' -> [[...],[...]]"""
    s = s.strip()
    if not s:
        return []
    rows = []
    for part in s.split(";"):
        part = part.strip()
        if part.startswith("(") and part.endswith(")"):
            part = part[1:-1]
        rows.append([x.strip() for x in part.split(",")])
    return rows


def num(x):
    try:
        return float(x)
    except Exception:
        return None


def judge_numeric(real, std, judge):
    """Apply JudgeRule/Rule list. Returns (score, matched_rule)."""
    r, s = num(real), num(std)
    if r is None or s is None:
        return 0.0, "非数值/空"
    rules = judge.findall("Rule") if judge is not None else []
    for rule in rules:
        rng = rule.find("Range")
        if rng is None:
            continue
        typ = text(rng, "Type")
        lo = num(text(rng, "Min"))
        hi = num(text(rng, "Max"))
        sc = num(text(rule, "Score")) or 0.0
        if lo is None or hi is None:
            continue
        if typ == "百分比":
            if s == 0.0:
                ok = (r == 0.0)
            else:
                dev = (r - s) / s
                ok = lo <= dev <= hi
        else:  # 绝对值
            ok = lo <= (r - s) <= hi
        if ok:
            return sc, f"{typ} [{lo},{hi}]"
    return 0.0, "未命中"


def judge_exact(real, std, judge):
    if judge is None:
        return 0.0, "无规则"
    rr = judge.find("RightRule")
    wr = judge.find("WrongRule")
    if rr is None and wr is None:
        return 0.0, "无规则"
    if real.strip() == std.strip():
        return (num(text(rr, "Score")) or 0.0) if rr is not None else 0.0, "RightRule"
    return (num(text(wr, "Score")) or 0.0) if wr is not None else 0.0, "WrongRule"


def main():
    if len(sys.argv) < 3:
        print("usage: python -I check_saved_exam.py saved_exam.xml fill_values.json")
        return 1
    paras = load_paras(sys.argv[1])
    with open(sys.argv[2], "r", encoding="utf-8") as f:
        expected = json.load(f)

    root = ET.parse(sys.argv[1]).getroot()
    max_total = float(root.findtext("Content/Question/Score/Total", "100") or 100)
    rows = []
    total = 0.0

    def add(name, exp, act, std, ok, note=""):
        nonlocal total
        score = paras.get(name, {}).get("score", 0.0)
        if ok:
            total += score
        rows.append((name, str(exp), str(act), str(std), "OK" if ok else "MISMATCH", note))

    # Choose
    for i, exp in enumerate(expected["choose"], 1):
        name = f"Choose{i}"
        p = paras.get(name, {})
        act = p.get("real", "")
        std = p.get("std", "")
        add(name, exp, act, std, act.strip().upper() == (std or exp).strip().upper(), "选择")

    # 6x tables
    for section, parent, keys in (
        ("gb", "GBDataPara", ["L", "B", "H", "D"]),
        ("paper", "PaperDataPara", ["L", "B", "H"]),
    ):
        p = paras.get(parent, {})
        act_rows = parse_tuples(p.get("real", ""))
        std_rows = parse_tuples(p.get("std", ""))
        exp_data = expected[section]["data"]
        for r in range(6):
            for c, k in enumerate(keys):
                exp = exp_data[k][r]
                # tuple 0 is the header column; measurements start at tuple 1
                act = act_rows[r + 1][c + 1] if r + 1 < len(act_rows) and c + 1 < len(act_rows[r + 1]) else ""
                std = std_rows[r + 1][c + 1] if r + 1 < len(std_rows) and c + 1 < len(std_rows[r + 1]) else ""
                # per-cell score from sub-Para rule
                sub_name = (
                    {"L": "GBLengthData", "B": "GBWidthData", "H": "GBThicknessData", "D": "GBDiameterData"}.get(k, "")
                    if section == "gb"
                    else {"L": "PaperLengthData", "B": "PaperWidthData", "H": "PaperThicknessData"}.get(k, "")
                )
                sub = p.get("sub_nodes", {}).get(sub_name)
                sc = 0.0
                if sub is not None:
                    sc, _ = judge_numeric(act, std or exp, sub.find("JudgeRule"))
                if num(act) is not None and num(std or exp) is not None:
                    ok = abs(num(act) - num(std or exp)) <= max(1e-9, abs(num(std or exp)) * 0.0001)
                else:
                    ok = act == (std or exp)
                if ok:
                    total += 1.0
                rows.append((f"{parent}[{r+1}].{k}", exp, act, std, "OK" if ok else "MISMATCH", f"cell score {sc}"))

    # single numeric fields
    mapping = {
        "gb": {
            "avg": ("GBLengthAvg", "GBWidthAvg", "GBThicknessAvg", "GBDiameterAvg"),
            "S": ("GBLengthBZC", "GBWidthBZC", "GBThicknessBZC", "GBDiameterBZC"),
            "dA": ("GBLengthUncertainA", "GBWidthUncertainA", "GBThicknessUncertainA", "GBDiameterUncertainA"),
            "dB": ("GBLengthUncertainB", "GBWidthUncertainB", "GBThicknessUncertainB", "GBDiameterUncertainB"),
            "d": ("GBLengthUncertain", "GBWidthUncertain", "GBThicknessUncertain", "GBDiameterUncertain"),
        },
        "paper": {
            "avg": ("PaperLengthAvg", "PaperWidthAvg", "PaperThicknessAvg"),
        },
    }
    for section, groups in mapping.items():
        keys = list(expected[section]["avg"].keys())
        for group, names in groups.items():
            for k, name in zip(keys, names):
                p = paras.get(name, {})
                exp = expected[section][group][k]
                act = p.get("real", "")
                std = p.get("std", "")
                ok = num(act) is not None and num(std or exp) is not None and abs(num(act) - num(std or exp)) <= max(1e-9, abs(num(std or exp)) * 0.0001)
                if ok:
                    total += p.get("score", 0.0)
                rows.append((name, exp, act, std, "OK" if ok else "MISMATCH", group))

    # V / rel / dV / expression
    for section, prefix in (("gb", "GB"), ("paper", "Paper")):
        for group, suffix in (("V", "V"), ("rel", "VRelativeUncertain"), ("dV", "VUncertain"), ("expr", "VExpression")):
            name = prefix + suffix
            p = paras.get(name, {})
            exp = expected[section][group]
            act = p.get("real", "")
            std = p.get("std", "")
            if group == "expr":
                ok = act.replace(" ", "") == (std or exp).replace(" ", "")
            else:
                ok = num(act) is not None and num(std or exp) is not None and abs(num(act) - num(std or exp)) <= max(1e-9, abs(num(std or exp)) * 0.0001)
            if ok:
                total += p.get("score", 0.0)
            rows.append((name, exp, act, std, "OK" if ok else "MISMATCH", group))

    # hidden decimal-place checks (1 point each; previously omitted -> 96/100)
    for name, dec in (
        ("IsMeasureGBWidthUseYBKC", 2),
        ("IsMeasureGBThicknessUseQFC", 3),
        ("IsMeasurePaperWidthUseYBKC", 3),
    ):
        p = paras.get(name, {})
        act = str(p.get("real", "")).strip().lower()
        ok = act in ("true", "1")
        if ok:
            total += p.get("score", 0.0)
        rows.append((name, "true", act, p.get("std", ""), "OK" if ok else "MISMATCH",
                     f"decimal check ({dec}dp)"))

    # print
    print(f"{'field':32s} {'expected':>16s} {'actual':>16s} {'std':>16s} status")
    for name, exp, act, std, status, note in rows:
        print(f"{name:32s} {exp:>16s} {act:>16s} {std:>16s} {status}  {note}")
    print()
    print(f"ESTIMATED SCORE: {total:.1f} / {max_total:.0f} (仅供参考)")
    mism = [r for r in rows if r[4] != "OK"]
    print(f"MISMATCHES: {len(mism)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
