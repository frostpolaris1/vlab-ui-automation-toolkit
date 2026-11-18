# VLab Automation Framework（固定流程 + UIA + agent 兜底）

位置：项目 `vlab_framework/`（本机 `%USERPROFILE%\Documents\Qoder\2026-11-17\c40897b8\vlab_ywcj_2026-11-17\vlab_framework`）。

## 调研结论（GitHub）

| 项目 | 结论 | 采用 |
|---|---|---|
| `NaBr406/weblab-toolkit` | 同平台；抓包重放/填标准答案/一键刷分 | **不采用**（违规）；仅参考公开协议分析 |
| `whmmhw/ustcoriCrack`、`PyrojewelMissU/Ustcori_Crack` | 改分/破解 | **不采用** |
| `MuelNova/SimExp_Cracker` | 上传/解密 | **不采用**上传/改分；解密思路与只读审计一致 |
| `MaaXYZ/MaaFramework` | Pipeline / Recognition / Action / Controller | **借鉴架构**，不直接依赖 |
| `MaaXYZ/MaaPracticeBoilerplate` | `interface.json` + `resource/pipeline` + `agent/` | **借鉴目录/接口** |
| `shanselman/FlaUI-MCP` | UIA `snapshot` + `click ref` | **借鉴模式**；可选控制器 |
| `pywinauto` / `FlaUI` | Windows UIA 库 | 参考；底层仍用 `input.exe/ui.exe` 处理 DPI/真实输入/图形刻度 |

## 结构

```
interface.json
assets/resource/pipeline/<exp>.json   # 固定任务流水线
experiments/<exp>/experiment.json     # 测量宏、填表映射、选择/精度
experiments/<exp>/anchors.json        # 校准后的窗口相对坐标
core/controller.py                    # input.exe/ui.exe/UIA/剪贴板
core/recognition.py                   # ValueText2/MessageText/稳定/证据/兜底
core/runner.py                        # Pipeline 引擎（重试/断点恢复）
core/compliance.py                    # 动作/脚本白名单 + 审计
tools/calibrate.py                    # 截图 + anchors 模板
tools/uia_anchor_suggest.py           # UIA 控件名/相对坐标建议
tools/build_fill_plan.py              # 实测值 -> 填表字符串 + standards 近似
tools/gen_field_map.py                # XML -> FIELD_MAP.md
tools/score_estimate.py               # 提交前本地判分（JudgeRule；低于阈值转 agent）
tools/check_saved_exam.py             # 提交后逐字段审计
tools/decrypt_examconfig.ps1          # 只读解密本地考卷
```

## 运行

```bash
cd vlab_framework
python tools/calibrate.py                 # 截图 + 生成 anchors.json
# 填 anchors.json，calibrated=true
python -m core.runner --dry-run --anchors experiments/wucha_peitao/anchors.test.json
python -m core.runner
python -m core.runner --resume            # 兜底后继续
python -m core.runner --start MeasureGBL  # 从某任务继续
# 流程含 Review：score_estimate.py 低于 95 分自动转 agent
```

## 兜底契约

`logs/needs_agent.json` 包含 `task/reason/screenshot/state/context`；`context.macro` 有 `store/iteration`。
- 图形刻度（直尺/卡尺）：agent 读截图，把值追加到 `measurements.json`，`--start <当前Measure任务>` 继续。
- 锚点/UI 异常：改 `anchors.json` 或手动操作，`--resume`。
- 提交闸门：检查 `logs/shots/verify_data.png`，`--resume` 提交。

## 同平台工具调研

详见项目 `vlab_framework/docs/same-platform-tools.md`。要点：
- `weblab-toolkit`（抓包重放/一键满分）、`ustcoriCrack`（伪造大厅/本地判分）、`SimExp_Cracker`（加解密上传）、`PhysicalExperiment`（预置答案库）——**均不采用**。
- 可借鉴：协议事实（用于只读审计）、`PaperReviewer` 的 JudgeRule 逻辑（→ `score_estimate.py`/`check_saved_exam.py`）、MAA/FlaUI-MCP 的架构。

## 合规

- 白名单动作/脚本；无任意 shell、注入、内存写入、协议重放、改分。
- 只读解密仅用于审计；提交只点官方按钮；`PreSubmitGate` 提交前确认。
- 同平台刷分工具明确不采用。
