# -*- coding: utf-8 -*-
"""Export a round archive to CSV / XLSX / HTML for humans.

No third-party libraries: a minimal OOXML .xlsx is generated with zipfile.
Outputs (default <round>/export/):
    measurements.csv  fill_values.csv  report.html  round_data.xlsx

Usage: py -3 -I tools/export_round.py --round ../../data/round_xxx [--out DIR]
"""
import argparse
import csv
import html
import json
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parents[1] / "data"
MEASURE_KEYS = {
    "paper": ["L", "B", "H"],
    "gb": ["L", "B", "H", "D"],
}
INSTRUMENT = {
    ("paper", "L"): "钢直尺", ("paper", "B"): "钢直尺", ("paper", "H"): "螺旋测微器",
    ("gb", "L"): "钢直尺", ("gb", "B"): "游标卡尺", ("gb", "H"): "螺旋测微器", ("gb", "D"): "钢直尺",
}


def load_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def read_text(p: Path, default=""):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return default


def latest_round() -> Path:
    rounds = [p for p in DATA.glob("round_*") if p.is_dir()]
    if not rounds:
        raise SystemExit("no round_* directories under data/")
    return max(rounds, key=lambda p: p.stat().st_mtime)


def fnum(x):
    try:
        return float(x)
    except Exception:
        return None


def fmt(x, nd=6):
    if x is None:
        return ""
    s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return s if s else "0"


def build_tables(round_dir: Path):
    m = load_json(round_dir / "measurements.json")
    f = load_json(round_dir / "fill_values.json")
    manifest = load_json(round_dir / "manifest.json")
    truth = m.get("truth", {})
    measure_rows, calc_rows, fill_rows = [], [], []

    for section, keys in MEASURE_KEYS.items():
        for k in keys:
            vals = m.get(section, {}).get(k, [])
            data = f.get(section, {}).get("data", {}).get(k, [])
            avg = f.get(section, {}).get("avg", {}).get(k, "")
            S = f.get(section, {}).get("S", {}).get(k, "")
            dA = f.get(section, {}).get("dA", {}).get(k, "")
            dB = f.get(section, {}).get("dB", {}).get(k, "")
            d = f.get(section, {}).get("d", {}).get(k, "")
            tv = truth.get(section, {}).get(k, "")
            dev = ""
            if fnum(avg) is not None and fnum(tv):
                dev = f"{(fnum(avg) - fnum(tv)) / fnum(tv) * 100:.4f}%"
            measure_rows.append([section, k, *vals, avg, tv, dev, INSTRUMENT.get((section, k), "")])
            calc_rows.append([section, k, avg, S, dA, dB, d, tv, dev])
            for i, v in enumerate(data, 1):
                fill_rows.append([f"{section}.{k}[{i}]", v])
    for section in ("gb", "paper"):
        blk = f.get(section, {})
        for field in ("V", "rel", "dV", "expr"):
            fill_rows.append([f"{section}.{field}", blk.get(field, "")])
    for tbl, ncols in (("table1", 4), ("table3", 3)):
        for r in ("ruler", "caliper", "mic"):
            for c, v in enumerate(f.get(tbl, {}).get(r, []), 1):
                fill_rows.append([f"{tbl}.{r}[{c}]", v])
    for i, v in enumerate(f.get("choose", []), 1):
        fill_rows.append([f"choose{i}", v])

    status = manifest.get("status", "DONE")
    meta = {
        "round": round_dir.name,
        "status": status,
        "account": manifest.get("account", ""),
        "lab": manifest.get("lab", ""),
        "pid": manifest.get("pid", ""),
        "started_at": manifest.get("started_at", ""),
        "finished_at": manifest.get("finished_at", ""),
        "data_source": manifest.get("data_source", ""),
        "seed": manifest.get("seed", ""),
        "toolchain_git": manifest.get("toolchain_git", ""),
        "receipt": manifest.get("receipt", ""),
        "verify": read_text(round_dir / "verify_output.txt").strip().splitlines()[-1:] or [""],
        "score": [ln for ln in read_text(round_dir / "score_estimate_output.txt").splitlines()
                  if "ESTIMATED SCORE" in ln],
        "audit": [ln for ln in read_text(round_dir / "audit_saved_exam.txt").splitlines()
                  if "ESTIMATED SCORE" in ln or "MISMATCHES" in ln],
    }
    return measure_rows, calc_rows, fill_rows, meta


# ---------------- minimal XLSX (inline strings, bold header) ----------------
def xml_escape(s):
    return html.escape(str(s), quote=True)


def col_letter(i):
    s = ""
    while i > 0:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def sheet_xml(rows, widths=None):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
    if widths:
        out.append("<cols>")
        for i, w in enumerate(widths, 1):
            out.append(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>')
        out.append("</cols>")
    out.append("<sheetData>")
    for ri, row in enumerate(rows, 1):
        out.append(f'<row r="{ri}">')
        for ci, val in enumerate(row, 1):
            ref = f"{col_letter(ci)}{ri}"
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out.append(f'<c r="{ref}"><v>{val}</v></c>')
            else:
                style = ' s="1"' if ri == 1 else ""
                out.append(f'<c r="{ref}" t="inlineStr"{style}><is><t>{xml_escape(val)}</t></is></c>')
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path: Path, sheets):
    """sheets: list of (name, rows, widths)"""
    n = len(sheets)
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    for i in range(1, n + 1):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ct.append("</Types>")
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>',
            "</Relationships>"]
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    wbrels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
              '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i, (name, _rows, _w) in enumerate(sheets, 1):
        wb.append(f'<sheet name="{xml_escape(name)}" sheetId="{i}" r:id="rId{i}"/>')
        wbrels.append(f'<Relationship Id="rId{i}" '
                      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                      f'Target="worksheets/sheet{i}.xml"/>')
    wb.append("</sheets></workbook>")
    wbrels.append(f'<Relationship Id="rId{n+1}" '
                  'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                  'Target="styles.xml"/>')
    wbrels.append("</Relationships>")
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
              '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
              '<borders count="1"><border/></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
              '</styleSheet>')

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(ct))
        z.writestr("_rels/.rels", "".join(rels))
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(wbrels))
        z.writestr("xl/styles.xml", styles)
        for i, (_name, rows, widths) in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(rows, widths))


def write_csv(path: Path, header, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_html(path: Path, measure_rows, calc_rows, meta, round_dir: Path):
    def table(headers, rows):
        out = ["<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr></thead><tbody>"]
        for r in rows:
            out.append("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>")
        out.append("</tbody></table>")
        return "".join(out)

    receipt = round_dir / "shots" / "04_submit_receipt.png"
    receipt_html = (f'<p><img src="shots/04_submit_receipt.png" alt="提交回执" style="max-width:560px"></p>'
                    if receipt.exists() else "")
    html_doc = f"""<!doctype html><meta charset="utf-8">
<title>{html.escape(meta['round'])} - 误差配套实验报告</title>
<style>
body{{font-family:system-ui,'Microsoft YaHei',sans-serif;margin:24px;color:#222}}
h1{{font-size:20px}} h2{{font-size:16px;margin-top:24px}}
table{{border-collapse:collapse;margin:8px 0 16px;font-size:12px}}
th,td{{border:1px solid #ccc;padding:4px 8px;text-align:left}}
th{{background:#f2f4f7}} .k{{color:#666}}
</style>
<h1>误差配套实验报告 — {html.escape(meta['round'])}</h1>
<p class="k">账号：{html.escape(str(meta['account']))} ｜ 实验：{html.escape(str(meta['lab']))} ｜
状态：<b>{html.escape(str(meta['status']))}</b> ｜ 数据来源：{html.escape(str(meta['data_source']))}</p>
<p class="k">会话 PID：{html.escape(str(meta['pid']))} ｜ 开始：{html.escape(str(meta['started_at']))} ｜
结束：{html.escape(str(meta['finished_at']))} ｜ 工具链：{html.escape(str(meta['toolchain_git']))}</p>
<p class="k">判分：{html.escape(' '.join(meta['score']))} ｜ 审计：{html.escape(' '.join(meta['audit']))}</p>
{receipt_html}
<h2>1. 测量数据（6 次）</h2>
{table(['对象','量','1','2','3','4','5','6','平均','真值','偏差','仪器'], measure_rows)}
<h2>2. 不确定度计算</h2>
{table(['对象','量','平均','S','ΔA','ΔB','Δ','真值','偏差'], calc_rows)}
</body>"""
    path.write_text(html_doc, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    round_dir = Path(args.round).resolve() if args.round else latest_round()
    out = Path(args.out).resolve() if args.out else round_dir / "export"
    out.mkdir(parents=True, exist_ok=True)

    measure_rows, calc_rows, fill_rows, meta = build_tables(round_dir)

    write_csv(out / "measurements.csv",
              ["对象", "量", "1", "2", "3", "4", "5", "6", "平均", "真值", "偏差", "仪器"],
              measure_rows)
    write_csv(out / "fill_values.csv", ["字段", "值"], fill_rows)

    ov = [["项目", "值"], ["round", meta["round"]], ["status", meta["status"]],
          ["account", meta["account"]], ["lab", meta["lab"]], ["pid", meta["pid"]],
          ["started_at", meta["started_at"]], ["finished_at", meta["finished_at"]],
          ["data_source", meta["data_source"]], ["seed", meta["seed"]],
          ["toolchain_git", meta["toolchain_git"]],
          ["score", " ".join(meta["score"])], ["audit", " ".join(meta["audit"])],
          ["receipt", meta["receipt"]]]
    m_head = ["对象", "量", "1", "2", "3", "4", "5", "6", "平均", "真值", "偏差", "仪器"]
    c_head = ["对象", "量", "平均", "S", "ΔA", "ΔB", "Δ", "真值", "偏差"]
    f_head = ["字段", "值"]
    write_xlsx(out / "round_data.xlsx", [
        ("概览", ov, [18, 60]),
        ("测量数据", [m_head] + measure_rows, [8, 6, 9, 9, 9, 9, 9, 9, 10, 10, 10, 12]),
        ("不确定度", [c_head] + calc_rows, [8, 6, 10, 10, 10, 10, 10, 10, 10]),
        ("填表值", [f_head] + fill_rows, [26, 26]),
    ])
    write_html(out / "report.html", measure_rows, calc_rows, meta, round_dir)
    print(f"exported -> {out}")
    for name in ("measurements.csv", "fill_values.csv", "round_data.xlsx", "report.html"):
        print(" ", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
