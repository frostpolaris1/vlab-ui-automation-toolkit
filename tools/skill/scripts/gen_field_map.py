# -*- coding: utf-8 -*-
"""Generate FIELD_MAP.md from ExamConfig_3.xml + optional fill_values.json."""
import json
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def text(node, tag, default=""):
    x = node.find(tag) if node is not None else None
    return (x.text or "").strip() if x is not None else default


def value_for(name, vals):
    if not vals:
        return ""
    if name.startswith("Choose") and name[6:].isdigit():
        i = int(name[6:]) - 1
        return vals.get("choose", [""] * 7)[i] if i < 7 else ""
    if name == "GBDataPara":
        d = vals["gb"]["data"]
        return "6 列 × 4 行：L/B/H/D；例 L=" + d["L"][0] + ", B=" + d["B"][0] + ", H=" + d["H"][0] + ", D=" + d["D"][0]
    if name == "PaperDataPara":
        d = vals["paper"]["data"]
        return "6 列 × 3 行：L/B/H；例 L=" + d["L"][0] + ", B=" + d["B"][0] + ", H=" + d["H"][0]
    if name == "InsUncertainPara":
        return "3 行 × 4 列（0 分）；例 钢直尺行=" + ", ".join(vals["table1"]["ruler"])
    if name == "InsUncertainPara2":
        return "3 行 × 3 列（0 分）；例 钢直尺行=" + ", ".join(vals["table3"]["ruler"])
    m = {
        "GBLengthAvg": ("gb", "avg", "L"), "GBWidthAvg": ("gb", "avg", "B"),
        "GBThicknessAvg": ("gb", "avg", "H"), "GBDiameterAvg": ("gb", "avg", "D"),
        "GBLengthBZC": ("gb", "S", "L"), "GBWidthBZC": ("gb", "S", "B"),
        "GBThicknessBZC": ("gb", "S", "H"), "GBDiameterBZC": ("gb", "S", "D"),
        "GBLengthUncertainA": ("gb", "dA", "L"), "GBWidthUncertainA": ("gb", "dA", "B"),
        "GBThicknessUncertainA": ("gb", "dA", "H"), "GBDiameterUncertainA": ("gb", "dA", "D"),
        "GBLengthUncertainB": ("gb", "dB", "L"), "GBWidthUncertainB": ("gb", "dB", "B"),
        "GBThicknessUncertainB": ("gb", "dB", "H"), "GBDiameterUncertainB": ("gb", "dB", "D"),
        "GBLengthUncertain": ("gb", "d", "L"), "GBWidthUncertain": ("gb", "d", "B"),
        "GBThicknessUncertain": ("gb", "d", "H"), "GBDiameterUncertain": ("gb", "d", "D"),
        "PaperLengthAvg": ("paper", "avg", "L"), "PaperWidthAvg": ("paper", "avg", "B"),
        "PaperThicknessAvg": ("paper", "avg", "H"),
        "GBV": ("gb", "V", None), "GBVRelativeUncertain": ("gb", "rel", None),
        "GBVUncertain": ("gb", "dV", None), "GBVExpression": ("gb", "expr", None),
        "PaperV": ("paper", "V", None), "PaperVRelativeUncertain": ("paper", "rel", None),
        "PaperVUncertain": ("paper", "dV", None), "PaperVExpression": ("paper", "expr", None),
    }
    if name in m:
        sec, grp, key = m[name]
        return vals[sec][grp][key] if key else vals[sec][grp]
    return ""


def main():
    xml_path = sys.argv[1]
    vals = None
    if len(sys.argv) > 2:
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            vals = json.load(f)
    root = ET.parse(xml_path).getroot()
    lines = ["# 误差配套实验：数据表字段地图", "",
             "> 由 `ExamConfig_3.xml` 的 Para 顺序生成；界面顺序 = XML 顺序。",
             "> 6× 表是“行=量、列=次数1..6”；INDEX 行是次数，不用填。", ""]
    for ti, tt in enumerate(root.findall("Content/Question/CheckPoint/TestTarget"), 1):
        lines.append(f"## {'薄板' if ti == 1 else '100张纸'}（TestTarget #{ti}）")
        lines.append("")
        lines.append("| # | 字段名 | 界面标签 | 类型 | 分值 | 填法/示例 |")
        lines.append("|---|---|---|---|---|---|")
        for gi, g in enumerate(tt.findall("Group"), 1):
            for pi, p in enumerate(g.findall("Para"), 1):
                name = text(p, "Name")
                script = text(p, "Script").replace("\n", " ").replace("|", "/")
                vartype = text(p, "VarType")
                score = text(p, "TotalScore", "0")
                visible = p.get("StudentVisible", "True")
                if vartype.upper() == "TLIST":
                    cnt = p.find("VarType").get("Count") if p.find("VarType") is not None else "?"
                    subs = [text(s, "Name") for s in p.findall("Para")]
                    typ = f"TList({cnt}列; {','.join(subs)})"
                else:
                    typ = vartype
                note = value_for(name, vals)
                if visible.lower() == "false":
                    note = "（隐藏，不显示；由 6× 小数位自动判定）"
                lines.append(f"| {pi} | `{name}` | {script} | {typ} | {score} | {note} |")
        lines.append("")
    out = "\n".join(lines) + "\n"
    with open("FIELD_MAP.md", "w", encoding="utf-8") as f:
        f.write(out)
    print("WROTE FIELD_MAP.md", len(out), "chars")


if __name__ == "__main__":
    main()
