# workflow — 误差配套实验离线工具链

服务器维护期不能启动客户端时，用这里的脚本把“实测值 → 精确填表字符串 → 提交后审计”跑通。

## 三步

```bash
# 1) 把 6 次读数填进 measurements.json（复制 measurements.example.json）
python -I build_fill_plan.py measurements.json fill_values.json

# 2) 生成界面字段地图
python -I gen_field_map.py ../data/package/ExamConfig_3.xml fill_values.json
# -> FIELD_MAP.md

# 3) 提交后审计（可选）
powershell -NoProfile -ExecutionPolicy Bypass -File decrypt_examconfig.ps1 `
  -BinPath "$env:TEMP\lab\<n>\SimExpConfig\ExamConfig.bin" -OutPath saved_exam.xml
python -I check_saved_exam.py saved_exam.xml fill_values.json
```

## 关键修正（来自 Main.exe 反编译）

- 客户端标准 **ΔA = S**，不是 S/√6。
- 6 次同值时 S 可能是浮点残留（如 2e-16），ΔA 用脚本给出的字符串，不要手填 0。
- 表达式由客户端用**学生自己的 V/ΔV** 拼，V 小数位 = |ΔV 小数位|。
- 隐藏考察点只看 6× 小数位：板宽 2 位、板厚 3 位、纸厚 3 位。
- B 类表用名义尺寸，0 分。

## 文件

| 文件 | 用途 |
|---|---|
| `RUNBOOK.md` | 重启后的完整执行手册（测量/填表/读回/提交/审计） |
| `FIELD_MAP.md` | 界面顺序 + 字段名 + 分值 + 填法（由 XML 生成） |
| `build_fill_plan.py` | 实测值 → 填表字符串 |
| `gen_field_map.py` | 生成 FIELD_MAP.md |
| `decrypt_examconfig.ps1` | 只读解密本地 ExamConfig.bin |
| `check_saved_exam.py` | 解密 XML vs 期望值，逐字段审计 + 估算分数 |
| `measurements.example.json` | 输入模板 |
| `measurements.template.json` | 包内样例会话，用于离线 dry-run |
| `fill_values.example.json` | 示例输出 |
| `fill_values.template.json` | 样例会话输出 |

## 合规

真实测量、真实 UI、官方提交；只读解密仅用于校验。不注入、不写内存、不改 bin、不伪造数据/签名。
