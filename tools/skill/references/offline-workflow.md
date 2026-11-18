# 离线工作流：实测值 → 精确填表 → 提交后审计

适用：客户端未运行/服务器维护，只有解包数据和历史资料时，先把“填什么”算准。
依据：`Main.exe` 反编译（`GetStd`/`GetReal`/`ToUncertainty`）+ `ExamConfig.xml`。

## 1. 四个关键修正（与教材/旧 skill 不同）

1. **ΔA = S，不是 S/√6**。`GetUncertainA` 返回样本标准差；`GetStd` 把 S 直接当 ΔA 标准。
2. **ΔB = Δ仪/√3，Δ = √(S²+ΔB²)**；客户端用 `ToUncertainty(...,2)` 做 2 位有效数字、向上取整。
3. **表达式是格式检查**：客户端用学生自己的 V/ΔV 拼 `V±ΔV`，V 小数位 = |ΔV 小数位|。
4. **隐藏考察点只看小数位**：板宽 2 位、板厚 3 位、纸厚 3 位；真实测量并保留尾零即可。

## 2. 离线管线

```bash
# 1) 填 measurements.json（6 次读数，mm）
python -I scripts/build_fill_plan.py measurements.json fill_values.json

# 2) 生成字段地图（界面顺序 = XML 顺序）
python -I scripts/gen_field_map.py <ExamConfig.xml> fill_values.json
# -> FIELD_MAP.md

# 2.5) 提交前本地判分（低于阈值返回 1，框架转 agent）
python -I scripts/score_estimate.py <ExamConfig.xml> fill_values.json 95

# 3) 提交后：解密本地 ExamConfig.bin
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/decrypt_examconfig.ps1 `
  -BinPath "$env:TEMP\lab\<n>\SimExpConfig\ExamConfig.bin" -OutPath saved_exam.xml

# 4) 对比 expected/actual/std + 估算分数
python -I scripts/check_saved_exam.py saved_exam.xml fill_values.json
```

## 3. 输入格式

```json
{
  "paper": {"L": [6], "B": [6], "H": [6]},
  "gb":    {"L": [6], "B": [6], "H": [6], "D": [6]},
  "n_holes": 5,
  "truth": {"paper": {"L": 240.3, "B": 169.4, "H": 7.495},
            "gb": {"L": 140.1, "B": 38.04, "H": 1.996, "D": 7.1}}
}
```

- `truth` 可选，只用于偏差警告，不参与填表。
- 脚本按目标精度四舍五入：板 L 1、B 2、H 3、D 1；纸 L/B 1、H 3。

## 4. 填表要点

- 6× 表：行=量（L/B/H/D），列=次数 1..6；INDEX 行是次数，不用填。
- 统计字段顺序见 `FIELD_MAP.md`；薄板 (7)-(30)，纸 (6)-(12)。
- 保留尾零：`38.04`、`1.996`、`7.495`；不要输入成 `38.0`。
- 6 次同值时：客户端 S 可能是浮点残留（如 1.996×6 → 2.4e-16），脚本给出 `0.00000000000000025` 这类字符串；ΔA 填脚本值，不要手填 0。
- 表达式：V 的小数位 = |ΔV 的小数位|；`±` 用剪贴板，读回码点 177。

## 5. 审计

- `check_saved_exam.py` 会按 `JudgeRule` 估算分数（仅供参考，最终以平台为准）。
- 有 MISMATCH 时按字段修正后重新提交（平台会问是否替换）。
- 本地 bin 是提交时写的；**提交前**的核对仍以截图/目视为主。

## 6. 红线

- 不注入、不写内存、不改 bin、不伪造 StdResult/签名、不伪造数据。
- 解密只用于读回校验；不用于改写/重签。
