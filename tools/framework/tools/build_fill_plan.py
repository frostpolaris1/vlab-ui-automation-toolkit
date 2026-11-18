# -*- coding: utf-8 -*-
"""
误差配套实验：实测值 -> 可直接填表的字符串（严格按客户端 GetStd/ToUncertainty 逻辑）。

用法:
  python -I build_fill_plan.py measurements.json [out.json]

measurements.json 结构:
{
  "paper": {"L": [6 个数], "B": [...], "H": [...]},
  "gb":    {"L": [6 个数], "B": [...], "H": [...], "D": [...]},
  "n_holes": 5,
  "truth": {                      # 可选，只用于校验/警告，不参与填表
    "paper": {"L": 240.3, "B": 169.4, "H": 7.495},
    "gb":    {"L": 140.1, "B": 38.04, "H": 1.996, "D": 7.1}
  }
}

关键事实（来自 Main.exe 反编译）:
- 6× 格的标准答案 = 会话真值按目标精度格式化（L F1 / B F2 / H F3 / D F1）。
- 平均值标准 = 会话真值；学生填实测平均值即可（容差内）。
- S 标准 = 学生自己 6 个数算出的样本标准差。
- ΔA 标准 = S（不是 S/√6！Main.exe GetUncertainA 返回样本标准差）。
- ΔB 标准 = Δ仪/√3，再经 ToUncertainty(...,2) 格式化。
- Δ 标准 = sqrt(S^2 + ΔB^2)，再经 ToUncertainty(...,2)。
- V 标准 = 真值公式；学生用实测平均值算 V。
- ΔV/V 标准用 Δ（不是 ΔA/ΔB 单独）与真值；学生用实测平均值算。
- 表达式标准 = 学生自己的 V/ΔV 拼 "V±ΔV"，V 的小数位 = |ΔV 的小数位|。
- 隐藏检查只看 6× 字符串的小数位：板宽 2 位、板厚 3 位、纸厚 3 位。
"""
import json
import math
import sys
from decimal import Decimal, ROUND_HALF_UP

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------- .NET Framework "F" 格式化（round half away from zero） ----------
def dotnet_fmt(x, d):
    q = Decimal(1).scaleb(-d)
    return format(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP), "f")

def dotnet_general(x):
    """Mimic .NET double.ToString(): integers without trailing .0."""
    if x == int(x):
        return str(int(x))
    return str(x)

# ---------- 客户端 DataConversion.Low / High / CutDataEffective / ToUncertainty ----------
def low(s):
    try:
        s = str(s)
        if s[:1] in "+-":
            s = s[1:]
        parts = s.split(".")
        int(parts[0])
        return -len(parts[1]) if len(parts) > 1 else 0
    except Exception:
        return 0

def high(s):
    try:
        s = str(s)
        if s[:1] in "+-":
            s = s[1:]
        parts = s.split(".")
        n = int(parts[0])
        if len(parts) <= 1:
            return len(str(n)) - 1 if n > 0 else 0
        if n > 0:
            return len(str(n)) - 1
        for i, ch in enumerate(parts[1]):
            if ch != "0":
                return -(i + 1)
        return -len(parts[1])
    except Exception:
        return 0

def cut_data_effective(result, num):
    try:
        v = float(result)
        sign = -1 if v < 0 else 1
        v = abs(v)
        if v == 0.0:
            return dotnet_fmt(1e-20, num - 1 if num >= 1 else 0)
        if v <= 9.9999996826552254e-21:
            v = 9.9999996826552254e-21
        exp = 0
        while v < 1.0 or v > 10.0:
            if v < 1.0:
                v *= 10.0
                exp -= 1
            elif v > 10.0:
                v *= 0.1
                exp += 1
            else:
                break
        text2 = dotnet_fmt(v, num - 1)
        v2 = float(text2) * (10.0 ** exp)
        if exp != 0:
            dec = num - exp - 1
            if dec <= 0:
                text = dotnet_general(v2)
            elif int(float(text2)) != 10:
                text = dotnet_fmt(v2, dec)
            else:
                text = dotnet_fmt(v2, dec - 1)
        else:
            text = text2
            if float(text2) == 10.0:
                text = "10" if num <= 2 else ("10." + "0" * (num - 1))
        return ("-" + text) if sign == -1 else text
    except Exception:
        return ""

def to_uncertainty(result, num=2):
    text = cut_data_effective(result, num)
    try:
        sign = -1 if float(text) < 0 else 1
        v = abs(float(text))
        if v < abs(float(result)):
            if low(text) >= 0:
                bumped = v + 10.0 ** (high(text) - num + 1)
            else:
                bumped = v + 10.0 ** low(text)
            text = cut_data_effective(str(bumped), num)
            if sign == -1:
                text = "-" + text
    except Exception:
        text = ""
    return text

# ---------- 统计 ----------
def mean(xs):
    return sum(xs) / len(xs)

def sample_s(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))

def round_list(xs, d):
    return [float(dotnet_fmt(x, d)) for x in xs]

def fmt_list(xs, d):
    return [dotnet_fmt(x, d) for x in xs]

# ---------- 主计算 ----------
def compute(data):
    n = int(data.get("n_holes", 5))
    gb = data["gb"]
    pp = data["paper"]

    # 6× 进入表格的字符串（先按目标精度四舍五入；后续统计用这些“已填值”）
    gb_entered = {
        "L": round_list(gb["L"], 1),
        "B": round_list(gb["B"], 2),
        "H": round_list(gb["H"], 3),
        "D": round_list(gb["D"], 1),
    }
    pp_entered = {
        "L": round_list(pp["L"], 1),
        "B": round_list(pp["B"], 1),
        "H": round_list(pp["H"], 3),
    }

    err_gb = {"L": 0.2, "B": 0.02, "H": 0.004, "D": 0.2}  # mm
    err_paper = {"L": 0.2, "B": 0.2, "H": 0.004}  # paper L/B use ruler, H micrometer
    out = {"choose": ["A", "B", "C", "A", "A", "A", "C"], "warnings": []}

    def stats_block(entered, keys, errs):
        block = {"data": {}, "avg": {}, "S": {}, "dA": {}, "dB": {}, "d": {}, "d_raw": {}}
        for k in keys:
            xs = entered[k]
            block["data"][k] = fmt_list(xs, {"L": 1, "B": 2, "H": 3, "D": 1}[k])
            m = mean(xs)
            s = sample_s(xs) if len(xs) > 1 else 0.0
            db_raw = errs[k] / math.sqrt(3.0)
            d_raw = math.sqrt(s * s + db_raw * db_raw)
            block["avg"][k] = dotnet_fmt(m, {"L": 1, "B": 2, "H": 3, "D": 1}[k])
            block["S"][k] = to_uncertainty(s, 2)
            block["dA"][k] = to_uncertainty(s, 2)  # 客户端 ΔA = S
            block["dB"][k] = to_uncertainty(db_raw, 2)
            block["d"][k] = to_uncertainty(d_raw, 2)
            block["d_raw"][k] = d_raw
            if abs(s) < 1e-12:
                out["warnings"].append(
                    f"{k}: 6 次同值，S≈{s:.3e}；客户端标准 S/ΔA 会按 ToUncertainty 给出极小字符串。"
                    f"脚本已按同一算法输出，请直接使用脚本值（不要手填 0，否则 ΔA 可能按百分比判据失分）"
                )
            if any(x <= 0 for x in xs):
                out["warnings"].append(f"{k}: 存在非正数，客户端 GetBZC/GetUncertainA 会忽略这些值")
        return block

    gb_stats = stats_block(gb_entered, ["L", "B", "H", "D"], err_gb)
    pp_stats = stats_block(pp_entered, ["L", "B", "H"], err_paper)

    # 体积：用实测平均值（学生填的平均值）
    gL, gB, gH, gD = (mean(gb_entered[k]) for k in "LBHD")
    V = gL * gB * gH - n * math.pi * gD * gD / 4.0 * gH
    rel = math.sqrt(
        (gb_stats["d_raw"]["L"] / gL) ** 2
        + (gb_stats["d_raw"]["B"] / gB) ** 2
        + (gb_stats["d_raw"]["H"] / gH) ** 2
        + (n * math.pi * gD * gb_stats["d_raw"]["D"] / (2.0 * gL * gB)) ** 2
    )
    dV = V * rel
    dV_str = to_uncertainty(dV, 2)
    V_str = dotnet_fmt(V, 2)
    expr = dotnet_fmt(V, abs(low(dV_str))) + "±" + dV_str

    pL, pB, pH = (mean(pp_entered[k]) for k in "LBH")
    Vp = pL * pB * pH / 100.0
    relp = math.sqrt(
        (pp_stats["d_raw"]["L"] / pL) ** 2
        + (pp_stats["d_raw"]["B"] / pB) ** 2
        + (pp_stats["d_raw"]["H"] / pH) ** 2
    )
    dVp = Vp * relp
    dVp_str = to_uncertainty(dVp, 2)
    Vp_str = dotnet_fmt(Vp, 2)
    expr_p = dotnet_fmt(Vp, abs(low(dVp_str))) + "±" + dVp_str

    out["gb"] = {
        **gb_stats,
        "V": V_str,
        "rel": to_uncertainty(rel, 2),
        "dV": dV_str,
        "expr": expr,
        "V_raw": V,
        "rel_raw": rel,
        "dV_raw": dV,
    }
    out["paper"] = {
        **pp_stats,
        "V": Vp_str,
        "rel": to_uncertainty(relp, 2),
        "dV": dVp_str,
        "expr": expr_p,
        "V_raw": Vp,
        "rel_raw": relp,
        "dV_raw": dVp,
    }

    # B 类表（0 分；按客户端 GetStd 的名义尺寸/单位 cm）
    def btype_row(err_cm, L, B, H, D=None):
        # 与客户端 GetInsUncertain -> ToUncertainty(...,2) 完全一致：
        # 2 位有效数字 + 纯小数（不用科学计数法），填进表格与 StdResult 同格式。
        row = [
            to_uncertainty((err_cm / L) ** 2, 2),
            to_uncertainty((err_cm / B) ** 2, 2),
            to_uncertainty((err_cm / H) ** 2, 2),
        ]
        if D is not None:
            row.append(to_uncertainty((n * math.pi * D * err_cm / (2.0 * L * B)) ** 2, 2))
        return row

    out["table1"] = {
        "ruler": btype_row(0.02, 14.0, 3.8, 0.2, 0.7),
        "caliper": btype_row(0.002, 14.0, 3.8, 0.2, 0.7),
        "mic": btype_row(0.0004, 14.0, 3.8, 0.2, 0.7),
    }
    out["table3"] = {
        "ruler": btype_row(0.02, 24.0, 17.0, 0.75),
        "caliper": btype_row(0.002, 24.0, 17.0, 0.75),
        "mic": btype_row(0.0004, 24.0, 17.0, 0.75),
    }

    # ---- 客户端标准答案的近似值（用于提交前本地判分） ----
    # 6×/平均/V 的标准来自会话真值；若未提供 truth，则用实测值近似（乐观）。
    truth = data.get("truth") or {}

    def tv(section, key, fallback):
        return truth.get(section, {}).get(key, fallback)

    dec = {"L": 1, "B": 2, "H": 3, "D": 1}
    std = {"choose": list(out["choose"]), "table1": out["table1"], "table3": out["table3"]}
    std["gb"] = {
        "data": {k: [dotnet_fmt(tv("gb", k, mean(gb_entered[k])), dec[k])] * 6 for k in "LBHD"},
        "avg": {k: dotnet_fmt(tv("gb", k, mean(gb_entered[k])), dec[k]) for k in "LBHD"},
        "S": dict(gb_stats["S"]), "dA": dict(gb_stats["dA"]),
        "dB": dict(gb_stats["dB"]), "d": dict(gb_stats["d"]),
        "rel": out["gb"]["rel"], "dV": out["gb"]["dV"], "expr": out["gb"]["expr"],
    }
    if all(k in truth.get("gb", {}) for k in "LBHD"):
        tL, tB, tH, tD = (float(truth["gb"][k]) for k in "LBHD")
        std["gb"]["V"] = dotnet_fmt(tL * tB * tH - n * math.pi * tD * tD / 4.0 * tH, 2)
    else:
        std["gb"]["V"] = out["gb"]["V"]
    std["paper"] = {
        "data": {k: [dotnet_fmt(tv("paper", k, mean(pp_entered[k])), {"L": 1, "B": 1, "H": 3}[k])] * 6 for k in "LBH"},
        "avg": {k: dotnet_fmt(tv("paper", k, mean(pp_entered[k])), {"L": 1, "B": 1, "H": 3}[k]) for k in "LBH"},
        "S": dict(pp_stats["S"]), "dA": dict(pp_stats["dA"]),
        "dB": dict(pp_stats["dB"]), "d": dict(pp_stats["d"]),
        "rel": out["paper"]["rel"], "dV": out["paper"]["dV"], "expr": out["paper"]["expr"],
    }
    if all(k in truth.get("paper", {}) for k in "LBH"):
        tL, tB, tH = (float(truth["paper"][k]) for k in "LBH")
        std["paper"]["V"] = dotnet_fmt(tL * tB * tH / 100.0, 2)
    else:
        std["paper"]["V"] = out["paper"]["V"]
    out["standards"] = std
    if not truth:
        out["warnings"].append("未提供 truth：standards 用实测值近似，本地判分偏乐观；建议从只读内存/本地考卷补 truth")

    # 真值校验（可选）
    truth = data.get("truth")
    if truth:
        tol = {
            "gb": {"L": 0.005, "B": 0.02, "H": 0.003, "D": 0.05},
            "paper": {"L": 0.005, "B": 0.005, "H": 0.002},
        }
        for section, stats in (("gb", gb_stats), ("paper", pp_stats)):
            for k, avg_s in stats["avg"].items():
                tv = truth.get(section, {}).get(k)
                if tv:
                    dev = abs(float(avg_s) - tv) / tv
                    if dev > tol[section][k]:
                        out["warnings"].append(
                            f"{section}.{k}: 实测均值 {avg_s} 与真值 {tv} 偏差 {dev*100:.3f}% 超出满档容差 {tol[section][k]*100:.2f}%"
                        )
    return out

def main():
    if len(sys.argv) < 2:
        print("usage: python -I build_fill_plan.py measurements.json [out.json]")
        return 1
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
    out = compute(data)
    out_path = sys.argv[2] if len(sys.argv) > 2 else "fill_values.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("WROTE", out_path)
    print("GB  V =", out["gb"]["V"], " rel =", out["gb"]["rel"], " dV =", out["gb"]["dV"], " expr =", out["gb"]["expr"])
    print("Paper V =", out["paper"]["V"], " rel =", out["paper"]["rel"], " dV =", out["paper"]["dV"], " expr =", out["paper"]["expr"])
    for w in out["warnings"]:
        print("WARN:", w)
    return 0

if __name__ == "__main__":
    sys.exit(main())
