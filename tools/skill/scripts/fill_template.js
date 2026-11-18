const WS = "D:\\code\\.zcode\\workspace\\1794886573800-be334229-60ef-42d8-a59b-e4d19f0f8499";
const I = WS + "\\tools\\input\\input.exe";
const V = JSON.parse(fs.readFileSync(WS + "\\analysis\\values.json", "utf8"));
let filled = new Set(); try { filled = new Set(JSON.parse(fs.readFileSync(WS + "\\analysis\\filled_keys.json", "utf8"))); } catch {}
let pass = 0; try { pass = parseInt(fs.readFileSync(WS + "\\analysis\\fill_pass.txt", "utf8")); } catch {}
const dt = await agent.computerUse.getApp({ pid: 19616, window_id: 12652312 });
execSync(`"${I}" winfront 12652312`);
const OX = 1841, OY = 0;
const num = x => typeof x === "number" ? String(Math.round(x * 1000) / 1000) : String(x);
const save = () => fs.writeFileSync(WS + "\\analysis\\filled_keys.json", JSON.stringify([...filled], null, 1));
const els = await dt.elements();
const texts = els.filter(e => e.role === "Text").map(t => ({ t: t.title || "", x: t.bounds[0] - OX, y: t.bounds[1] - OY }));
const edits = els.filter(e => e.role === "Edit");
let did = 0;
for (const e of edits) {
  const ex = e.bounds[0] - OX, ey = e.bounds[1] - OY;
  const lab = texts.find(t => Math.abs(t.y - ey) <= 6 && t.x < 300 && /^\(\d+\)/.test(t.t));
  let val = null, key = null;
  if (lab) {
    const L = lab.t; key = L; const gb = /带孔薄板/.test(L), pp = /100张纸|1张纸/.test(L);
    if (/选择测量/.test(L)) { const m = L.match(/^\((\d+)\)/); val = V.choose[gb ? (+m[1] - 2) : (+m[1] - 2 + 4)]; }
    else if (gb) {
      if (/长度L的平均值/.test(L)) val = V.gb_stat.L.avg; else if (/长度的标准差/.test(L)) val = V.gb_stat.L.S; else if (/长度的A类/.test(L)) val = V.gb_stat.L.dA; else if (/长度的B类/.test(L)) val = V.gb_stat.L.dB; else if (/长度的不确定度/.test(L)) val = V.gb_stat.L.d;
      else if (/宽度B的平均值/.test(L)) val = V.gb_stat.B.avg; else if (/宽度的标准差/.test(L)) val = V.gb_stat.B.S; else if (/宽度的A类/.test(L)) val = V.gb_stat.B.dA; else if (/宽度的B类/.test(L)) val = V.gb_stat.B.dB; else if (/宽度的不确定度/.test(L)) val = V.gb_stat.B.d;
      else if (/厚度H的平均值/.test(L)) val = V.gb_stat.H.avg; else if (/厚度的标准差/.test(L)) val = V.gb_stat.H.S; else if (/厚度的A类/.test(L)) val = V.gb_stat.H.dA; else if (/厚度的B类/.test(L)) val = V.gb_stat.H.dB; else if (/厚度的不确定度/.test(L)) val = V.gb_stat.H.d;
      else if (/孔径D的平均值/.test(L)) val = V.gb_stat.D.avg; else if (/孔径的标准差/.test(L)) val = V.gb_stat.D.S; else if (/孔径的A类/.test(L)) val = V.gb_stat.D.dA; else if (/孔径的B类/.test(L)) val = V.gb_stat.D.dB; else if (/孔径的不确定度/.test(L)) val = V.gb_stat.D.d;
      else if (/体积V\(mm/.test(L)) val = V.gb_V.V; else if (/相对不确定度/.test(L)) val = V.gb_V.rel; else if (/不确定度ΔV/.test(L)) val = V.gb_V.dV; else if (/表达式/.test(L)) val = V.gb_V.expr;
    } else if (pp) {
      if (/长度L的平均值/.test(L)) val = V.pp_stat.L.avg; else if (/宽度B的平均值/.test(L)) val = V.pp_stat.B.avg; else if (/厚度H的平均值/.test(L)) val = V.pp_stat.H.avg; else if (/体积V\(mm/.test(L)) val = V.pp_V.V; else if (/相对不确定度/.test(L)) val = V.pp_V.rel; else if (/不确定度ΔV/.test(L)) val = V.pp_V.dV; else if (/表达式/.test(L)) val = V.pp_V.expr;
    }
  } else {
    const row = texts.find(t => Math.abs(t.y - ey) <= 6 && t.x < 200 && /^(L\(mm\)|B\(mm\)|H\(mm\)|D\(mm\)|钢直尺|游标卡尺|千分尺)/.test(t.t));
    if (row) {
      const hdrs = texts.filter(t => /^\d$/.test(t.t) || /Δ仪/.test(t.t));
      const hy = Math.max(...hdrs.map(t => t.y).filter(y => y < ey - 10));
      const col = hdrs.filter(t => Math.abs(t.y - hy) <= 6).sort((a, b) => Math.abs(a.x - ex) - Math.abs(b.x - ex))[0];
      if (col) {
        const rk = row.t.replace(/\(.*mm\)/, "").trim(); const isB = /Δ仪/.test(col.t); const cc = hdrs.filter(t => Math.abs(t.y - hy) <= 6).length; const tr = texts.filter(t => /^(L\(mm\)|B\(mm\)|H\(mm\)|D\(mm\))/.test(t.t) && t.y > hy && t.y < hy + 260); const sect = isB ? (cc >= 4 ? "gb" : "pp") : (tr.some(t => /D\(mm\)/.test(t.t)) ? "gb" : "pp");
        key = sect + rk + col.t;
        if (isB) { const inst = /钢直尺/.test(rk) ? "ruler" : /游标卡尺/.test(rk) ? "caliper" : "mic"; const ci = /L\)²/.test(col.t) ? 0 : /B\)²/.test(col.t) ? 1 : /H\)²/.test(col.t) ? 2 : 3; val = (sect === "gb" ? V.t1 : V.t3)[inst][ci]; }
        else { const ci = +col.t - 1; const tbl = sect === "gb" ? V.gb6 : V.pp6; val = tbl[rk] ? tbl[rk][ci] : null; }
      }
    }
  }
  if (val !== null && key && !filled.has(key)) { await dt.setValue(e.index, num(val)); filled.add(key); save(); did++; }
}
fs.writeFileSync(WS + "\\analysis\\fill_pass.txt", String(pass + 1));
save();
nodeRepl.write("PASS=" + pass + " did=" + did + " TOTAL=" + filled.size);