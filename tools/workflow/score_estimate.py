# -*- coding: utf-8 -*-
"""
提交前本地判分（只评我们自己的 fill_values.json，不做任何上传/重放）。

用法:
  python -I score_estimate.py ExamConfig.xml fill_values.json [threshold]

fill_values.json 由 build_fill_plan.py 生成，内含 "standards"（客户端标准答案的近似值）。
若没有 standards，则用 fill 值当标准（会偏乐观）。

返回码: 0 = 估算分数 >= threshold；1 = 低于 threshold（框架会转 agent 兜底）。
"""
import json
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def text(node, tag, default=""):
    x = node.find(tag) if node is not None else None
    return (x.text or "").strip() if x is not None else default


def num(x):
    try:
        return float(x)
    except Exception:
        return None


def judge_numeric(real, std, judge):
    r, s = num(real), num(std)
    if r is None or s is None:
        return 0.0, "非数值/空"
    rules = judge.findall("Rule") if judge is not None else []
    for rule in rules:
        rng = rule.find("Range")
        if rng is None:
            continue
        typ = text(rng, "Type")
        lo, hi = num(text(rng, "Min")), num(text(rng, "Max"))
        sc = num(text(rule, "Score")) or 0.0
        if lo is None or hi is None:
            continue
        if typ == "百分比":
            ok = (r == 0.0) if s == 0.0 else (lo <= (r - s) / s <= hi)
        else:
            ok = lo <= (r - s) <= hi
        if ok:
            return sc, f"{typ}[{lo},{hi}]"
    return 0.0, "未命中"


def judge_exact(real, std, judge):
    if judge is None:
        return 0.0, "无规则"
    rr, wr = judge.find("RightRule"), judge.find("WrongRule")
    if rr is None and wr is None:
        return 0.0, "无规则"
    if str(real).replace(" ", "").strip() == str(std).replace(" ", "").strip():
        return (num(text(rr, "Score")) or 0.0) if rr is not None else 0.0, "RightRule"
    return (num(text(wr, "Score")) or 0.0) if wr is not None else 0.0, "WrongRule"


def get_path(obj, path):
    cur = obj
    for p in path.split("."):
        if isinstance(cur, dict):
            cur = cur[p]
        elif isinstance(cur, list):
            cur = cur[int(p)]
        else:
            raise KeyError(path)
    return cur


def main():
    if len(sys.argv) < 3:
        print("usage: python -I score_estimate.py ExamConfig.xml fill_values.json [threshold]")
        return 2
    xml_path, fill_path = sys.argv[1], sys.argv[2]
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 95.0
    root = ET.parse(xml_path).getroot()
    fill = json.loads(open(fill_path, encoding="utf-8").read())
    std = fill.get("standards")
    if not std:
        print("WARNING: no standards in fill_values.json; using fill as standard (optimistic)")
        std = fill

    rows = []
    total = 0.0
    max_total = 0.0

    def add(name, real, standard, judge, max_score, note=""):
        nonlocal total, max_total
        max_total += max_score
        if judge is not None and judge.find("Rule") is not None:
            sc, why = judge_numeric(real, standard, judge)
        else:
            sc, why = judge_exact(real, standard, judge)
        total += sc
        rows.append((name, str(real), str(standard), sc, max_score, why, note))

    def dec_count(s):
        s = str(s).strip()
        return len(s.split(".", 1)[1]) if "." in s else 0

    def hidden_value(name):
        """Hidden checks are decimal-place checks on the submitted strings."""
        if name == "IsMeasureGBWidthUseYBKC":
            vals, d = fill["gb"]["data"]["B"], 2
        elif name == "IsMeasureGBThicknessUseQFC":
            vals, d = fill["gb"]["data"]["H"], 3
        elif name == "IsMeasurePaperWidthUseYBKC":
            vals, d = fill["paper"]["data"]["H"], 3
        else:
            return "true"
        return "true" if all(dec_count(v) == d for v in vals) else "false"

    for tt in root.findall("Content/Question/CheckPoint/TestTarget"):
        for para in tt.findall("Group/Para"):
            name = text(para, "Name")
            vartype = text(para, "VarType").upper()
            score = num(text(para, "TotalScore", "0")) or 0.0
            judge = para.find("JudgeRule")

            if vartype == "TLIST":
                if name == "InsUncertainPara" or name == "InsUncertainPara2":
                    continue  # 0 分
                subs = para.findall("Para")
                if name == "GBDataPara":
                    keys = ["L", "B", "H", "D"]
                    sub_names = ["GBLengthData", "GBWidthData", "GBThicknessData", "GBDiameterData"]
                    real_data, std_data = fill["gb"]["data"], std["gb"]["data"]
                elif name == "PaperDataPara":
                    keys = ["L", "B", "H"]
                    sub_names = ["PaperLengthData", "PaperWidthData", "PaperThicknessData"]
                    real_data, std_data = fill["paper"]["data"], std["paper"]["data"]
                else:
                    continue
                sub_map = {text(s, "Name"): s for s in subs}
                per = score / (len(keys) * 6) if keys else 0.0
                for k, sn in zip(keys, sub_names):
                    sj = sub_map.get(sn)
                    sj_judge = sj.find("JudgeRule") if sj is not None else None
                    for i in range(6):
                        add(f"{name}[{k}{i+1}]", real_data[k][i], std_data[k][i], sj_judge, per)
                continue

            # single fields
            if name.startswith("Choose") and name[6:].isdigit():
                i = int(name[6:]) - 1
                add(name, fill["choose"][i], std["choose"][i], judge, score)
            elif name.startswith("IsMeasure"):
                add(name, hidden_value(name), "true", judge, score)
            elif name in ("GBVExpression", "PaperVExpression"):
                sec = "gb" if name.startswith("GB") else "paper"
                add(name, fill[sec]["expr"], std[sec]["expr"], judge, score)
            elif name == "GBV":
                add(name, fill["gb"]["V"], std["gb"]["V"], judge, score)
            elif name == "GBVRelativeUncertain":
                add(name, fill["gb"]["rel"], std["gb"]["rel"], judge, score)
            elif name == "GBVUncertain":
                add(name, fill["gb"]["dV"], std["gb"]["dV"], judge, score)
            elif name == "PaperV":
                add(name, fill["paper"]["V"], std["paper"]["V"], judge, score)
            elif name == "PaperVRelativeUncertain":
                add(name, fill["paper"]["rel"], std["paper"]["rel"], judge, score)
            elif name == "PaperVUncertain":
                add(name, fill["paper"]["dV"], std["paper"]["dV"], judge, score)
            elif name.startswith("GB") or name.startswith("Paper"):
                sec = "gb" if name.startswith("GB") else "paper"
                prefix = "GB" if sec == "gb" else "Paper"
                rest = name[len(prefix):]
                mapping = {
                    "LengthAvg": ("avg", "L"), "WidthAvg": ("avg", "B"),
                    "ThicknessAvg": ("avg", "H"), "DiameterAvg": ("avg", "D"),
                    "LengthBZC": ("S", "L"), "WidthBZC": ("S", "B"),
                    "ThicknessBZC": ("S", "H"), "DiameterBZC": ("S", "D"),
                    "LengthUncertainA": ("dA", "L"), "WidthUncertainA": ("dA", "B"),
                    "ThicknessUncertainA": ("dA", "H"), "DiameterUncertainA": ("dA", "D"),
                    "LengthUncertainB": ("dB", "L"), "WidthUncertainB": ("dB", "B"),
                    "ThicknessUncertainB": ("dB", "H"), "DiameterUncertainB": ("dB", "D"),
                    "LengthUncertain": ("d", "L"), "WidthUncertain": ("d", "B"),
                    "ThicknessUncertain": ("d", "H"), "DiameterUncertain": ("d", "D"),
                }
                if rest in mapping:
                    grp, k = mapping[rest]
                    add(name, fill[sec][grp][k], std[sec][grp][k], judge, score)

    print(f"{'field':34s} {'fill':>18s} {'std':>18s} {'score':>6s} {'max':>5s}  rule")
    for name, real, standard, sc, mx, why, note in rows:
        print(f"{name:34s} {real:>18s} {standard:>18s} {sc:>6.2f} {mx:>5.2f}  {why}")
    print()
    print(f"ESTIMATED SCORE: {total:.1f} / {max_total:.0f}  (threshold {threshold:.0f})")
    low = [(r[0], r[3], r[4]) for r in rows if r[3] < r[4] - 1e-9]
    if low:
        print("LOW SCORE FIELDS:")
        for n, sc, mx in low[:30]:
            print(f"  {n}: {sc:.2f}/{mx:.2f}")
    return 0 if total >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
