# VLab Automation Framework

轻量、可复用、合规的 USTCORi WebLab 虚拟仿真实验自动化框架。

**定位**：固定操作流程由程序执行；UIA 只读状态做反馈；图形刻度/异常由 agent 兜底。
**不是**：协议重放、改分、注入、内存写入工具。

> 零上下文入口：`../../START_HERE.md`；自检：`python -I ../../tools/verify_archive.py`（应 47/47 PASS）。

---

## 1. GitHub 调研结论（先避免重复造轮子）

> 详细拆解见 [docs/same-platform-tools.md](docs/same-platform-tools.md)：每个工具支持哪些实验、怎么实现、我们借鉴/拒绝什么。

| 项目 | 结论 | 是否采用 |
|---|---|---|
| `NaBr406/weblab-toolkit` | 同平台；抓包重放、把数据表填成标准答案、一键刷分 | **不采用**（违反合规）。仅参考其公开的协议分析（提交接口/判分模型/客户端防护） |
| `whmmhw/ustcoriCrack`、`PyrojewelMissU/Ustcori_Crack` | 改分/破解工具 | **不采用** |
| `MuelNova/SimExp_Cracker` | 上传/解密脚本 | **不采用**上传/改分；其解密思路与我们的只读审计一致 |
| `MaaXYZ/MaaFramework` | 图像识别自动化框架；Pipeline / Recognition / Action / Controller 分层 | **借鉴架构**，不直接依赖（C++/多语言绑定较重） |
| `MaaXYZ/MaaPracticeBoilerplate` | 项目模板：`interface.json` + `resource/pipeline/*.json` + `agent/` 自定义动作/识别 | **借鉴目录与接口** |
| `shanselman/FlaUI-MCP` | 把 Windows UIA 暴露成 `windows_snapshot` + `windows_click ref=...` | **借鉴 snapshot+ref 模式**；可选控制器 |
| `pywinauto` / `FlaUI` | Windows UIA 库 | 参考；本框架继续用已验证的 `input.exe/ui.exe` 处理 DPI/真实输入/图形刻度 |

**为什么不直接用 MAA Framework？**
- MAA 的 Win32 controller 以 `PostMessage`/截图为主；这个老 WPF 客户端需要 DPI 感知的真实 `SendInput`、窗口置顶、图形刻度读取。
- 我们的 `input.exe/ui.exe` + UIA 探针已经在上一轮实测跑通；框架层只需借鉴 MAA 的 **Pipeline/Recognition/Action** 语义，不需要引入整个引擎。
- 同平台的刷分工具虽然“能满分”，但属于协议重放/改分，直接违反本次“合规、无破坏性能力”的要求，明确排除。

---

## 2. 架构

```
interface.json
  ├─ controller: input.exe / input2.exe / ui.exe / read_vals.ps1 / uia_dump.ps1
  ├─ experiments/wucha_peitao/experiment.json   # 测量宏、填表映射、选择/精度
  ├─ experiments/wucha_peitao/anchors.json      # 校准后的窗口相对坐标
  └─ assets/resource/pipeline/wucha_peitao.json # 固定任务流水线

core/
  controller.py   # 窗口发现/固定、真实鼠标键盘、UIA 只读、剪贴板
  recognition.py  # ValueText/ValueText2/MessageText、稳定性、证据截图、agent fallback
  runner.py       # Pipeline 引擎：动作分发、变量解析、重试、断点恢复
  compliance.py   # 动作/脚本白名单、审计日志

tools/
  build_fill_plan.py      # 实测值 -> 精确填表字符串
  gen_field_map.py        # ExamConfig.xml -> FIELD_MAP.md
  check_saved_exam.py     # 解密后的考卷 vs 期望值，逐字段审计
  decrypt_examconfig.ps1  # 只读解密本地 ExamConfig.bin
  calibrate.py            # 截图 + 生成 anchors.json 模板
```

### 设计原则

1. **固定流程优先**：测量/填表/提交都写成 JSON 任务；agent 不参与常规步骤。
2. **UIA 只读反馈**：`ValueText2` 读千分尺、`MessageText` 判断“物体放不进去”；不把 UIA 当唯一事实源（会残留旧值）。
3. **图形刻度兜底**：直尺放大镜、卡尺游标是图像刻度，流程走到这里自动 `agent_fallback`，由 agent 读图后把值写回 `measurements.json`。
4. **可恢复**：每个测量量记录到 `measurements.json`；失败/兜底后从已完成处继续，不重测。
5. **提交前闸门**：`PreSubmitGate` 强制停一次，agent 检查 `verify_data.png` 后才允许 `--resume` 提交。
6. **合规白名单**：只允许点击/拖拽/输入/截图/UIA 读/白名单脚本；没有任意 shell、注入、内存写入、协议重放。

---

## 3. 固定流程

```
Start → Pin → CheckAnchors
  → MeasureGBL → MeasureGBB → MeasureGBH → MeasureGBD
  → MeasurePaperL → MeasurePaperB → MeasurePaperH
  → Compute → FieldMap → Review → Fill → Verify → PreSubmitGate
  → Submit → Decrypt → Audit
```

- 先测薄板（61 分）再测纸（39 分），时间不够时优先保分。
- 每个 `Measure*` 任务：
  - `setup`（仅第一次）：双击物体 → 找/钉大视图 → 选测量项 → 点仪器。
  - `repeat`（6 次）：点仪器 → 解锁 → 张开 → 放物体 → 闭合 → 等读数稳定 → 记录 → 移出物体。
- 千分尺：`ValueText2` 直接读；卡尺：`ValueText` 能读就读，读不到/为 0 时 agent 兜底；直尺：截图 + agent 读放大镜。
- `Compute` 调 `build_fill_plan.py`；`FieldMap` 调 `gen_field_map.py`；`Review` 调 `score_estimate.py` 做**提交前本地判分**（低于 95 分自动转 agent）；`Fill` 按 `anchors.json` 的网格/单值锚点填表。
- `PreSubmitGate` 停一次；agent 确认后 `--resume` 才提交。
- `Submit` 点官方“提交”按钮，读 MessageBox 文本；`Decrypt` 找最新本地 `ExamConfig.bin` 解密；`Audit` 逐字段对比。

---

## 4. 运行

```bash
cd vlab_framework

# 1) 校准（客户端已启动、实验已打开）
python tools/calibrate.py
# 用 logs/shots/calib_main.png / calib_data.png / calib_view.png 填 anchors.json
# 也可以先跑 UIA 锚点建议：
python tools/uia_anchor_suggest.py
# 把 "calibrated": false 改成 true

# 2) 离线干跑（不点击，只展开流程）
python -m core.runner --dry-run --anchors experiments/wucha_peitao/anchors.test.json

# 3) 正式跑
python -m core.runner

# 4) 兜底后恢复
python -m core.runner --resume

# 5) 从某个任务继续（例如直尺读数后继续同量）
python -m core.runner --start MeasureGBL
```

日志：

- `logs/run.jsonl`：每个动作的时间戳/参数/是否 dry-run。
- `logs/needs_agent.json`：兜底请求（任务、原因、截图、UIA 状态、macro 的 store/iteration、next）。
- `logs/shots/`：校准、测量、填表、验证截图。

---

## 5. Agent 兜底契约

`logs/needs_agent.json` 示例：

```json
{
  "task": "MeasureGBL",
  "reason": "读取放大镜绝对 cm；把读数追加到 measurements.json 后，用 --start <当前Measure任务> 继续",
  "screenshot": "logs/shots/ruler_gb.L_1.png",
  "state": {"ValueText": "0", "ValueText2": "", "MessageText": ""},
  "context": {
    "next": "MeasureGBB",
    "macro": {"object": "gb", "option": "length", "instrument": "ruler", "store": "gb.L", "iteration": 1}
  }
}
```

Agent 的处理：

1. **读刻度**：看截图，读出数值；若流程停在 `agent_fallback` 之前，先点一下「移出物体」复位；把值追加到 `measurements.json` 的 `gb.L` 数组；运行 `--start MeasureGBL` 继续剩余次数（已完成的会跳过）。
2. **UI/锚点异常**：看截图/状态，修正 `anchors.json` 或手动点击；运行 `--resume` 或 `--start <task>`。
3. **提交闸门**：检查 `logs/shots/verify_data.png` 与 `fill_values.json`；确认后 `--resume` 提交。
4. **提交失败**：看 `needs_agent.json` 的 reason / MessageBox 文本；修正后重提。

---

## 6. 合规边界

- **允许**：真实 UI 操作、真实仪器测量、UIA 只读、截图、白名单脚本、官方提交、本地考卷只读解密审计。
- **禁止**：进程注入、内存写入、修改 `ExamConfig.bin`、伪造 `StdResult`/签名、协议重放、改分、绕过计时/录屏、伪造数据。
- `compliance.py` 对动作和参数做白名单检查；`run_script` 只允许 4 个辅助脚本。
- `PreSubmitGate` 保证提交前有一次人工/agent 确认。
- 自动化是否被课程允许，以课程规定为准。

---

## 7. 新增一个实验

1. 复制 `experiments/wucha_peitao` 为 `experiments/<new>`。
2. 改 `experiment.json`：`objects`、`macros`、`fill.grids/singles`、`selection`、`decimals`。
3. 复制 `assets/resource/pipeline/wucha_peitao.json` 为 `<new>.json`，改任务参数/顺序。
4. 在 `interface.json` 的 `experiments` 里加一项。
5. 运行 `python tools/calibrate.py` 校准新实验的 anchors。
6. `core/` 不需要改；新实验复用同一套 controller/recognition/runner。

---

## 8. 已知限制

- **锚点依赖布局**：窗口移动/DPI 变化后要重新校准；框架每次点击前都会 `front`，但坐标是窗口相对的。
- **图形刻度**：直尺放大镜、卡尺游标仍需 agent 视觉兜底；千分尺 `ValueText2` 最可靠。
- **DataGrid 虚拟化**：填表用视觉锚点；UIA 读回只作旁证。
- **时间限制**：先薄板后纸；`measurements.json` 支持断点续测。
- **服务端判分**：`check_saved_exam.py` 只是估算；最终以平台为准。
- **同平台刷分工具**：明确不采用；只参考其公开协议事实做只读审计。

---

## 9. 2026-11-18 实战记录（live）

- 平台恢复后真实启动，`Main.exe pid=5228`；框架打开薄板大视图、点直尺、拖物体。
- **直尺放大镜不跟随合成鼠标**（move/click 后仍显示“7”），改用 `mem6.exe` 只读 `SimInstrumentPara[]` 真值交叉校验：
  纸 240.9/170.9/7.499；板 140.0/38.04/1.997/6.8。
- 填表锚点（数据窗相对）：GB 6× 首格 `(270,690)`、格 `135×36`；纸 6× 首格 `(270,362)`、格 `145×36`；Choose5–7 UIA 矩形 `2690,117/172/227,168x30`；提交 `(1090,930)`。
- **单值字段用 UIA `ValuePattern.SetValue` 比坐标点击稳**：`tools/uia_set_value.ps1 -Pid_ <pid> -Old <old> -New <new>`；`uia_dump.ps1` 可给出实时 Edit 矩形。
- 第一次提交成功但审计 94 分：纸宽误用卡尺 `Δ仪=0.02`，应为直尺 `0.2`（`PaperVRelativeUncertain` 0.00058 vs 0.00089，`PaperVUncertain` 1.8 vs 2.8）。修正 `build_fill_plan.py` 为分段误差字典后，第二次提交成功。
- **本地 `ExamConfig.bin` 可能滞后**：第二次提交后本地解密仍是第一次旧值；以客户端“提交成功”回执为准，平台成绩页为准。
- 6× 网格仍用视觉坐标（UIA 虚拟化/坐标不同步）；纸节需要先滚动到对应位置再填。

## 10. 文件速查

| 文件 | 用途 |
|---|---|
| `interface.json` | 控制器路径、实验入口 |
| `assets/resource/pipeline/wucha_peitao.json` | 固定任务流水线 |
| `experiments/wucha_peitao/experiment.json` | 测量宏、填表映射、选择/精度 |
| `experiments/wucha_peitao/anchors.example.json` | 锚点模板（复制为 anchors.json） |
| `core/controller.py` | 窗口/输入/UIA/剪贴板 |
| `core/recognition.py` | 读数稳定/消息/证据/兜底 |
| `core/runner.py` | Pipeline 引擎 |
| `core/compliance.py` | 白名单/审计 |
| `tools/calibrate.py` | 校准截图 + anchors 模板 |
| `tools/doctor.py` | 一次环境报告：账号/实验名/进程/窗口/真值/表格状态（无截图） |
| `tools/platform_info.py` | 从 Edge 的 UIA 树读账号/实验名/URL/开始实验按钮（无截图） |
| `tools/run_all.py` | **无人值守端到端**：环境→钉布局→真值→算→填 101→verify→截图→提交/回执→审计→manifest |
| `tools/receipt.py` | 提交 + 读「提交成功」+ 1:1 回执裁剪 + 按 UIA 矩形点确定 |
| `tools/pin_layout.py` | **把主窗/数据表/两个大视图钉到固定绝对坐标**（之后直接用绝对坐标） |
| `tools/scroll_data.py` | 把数据表滚到规范状态（top/bottom/paper_b，front + 抓 Thumb + 校验） |
| `tools/uia_fill_all.py` | **一次写入全部 101 字段（含 B 表）**，按标签/网格结构映射，不依赖滚动/键盘，幂等 |
| `tools/uia_set_by_index.ps1` | 按 Edit 文档顺序 SetValue 的 PowerShell 助手 |
| `tools/verify_table.py` | 提交前 UIA 全量核对数据表（101 个应填字段 + 小数位检查） |
| `tools/live_fill_b_tables.py` | 填两个 0 分 B 类不确定度表（12+9 格，UIA SetValue + 读回） |
| `tools/uia_set_b_tables.ps1` | 按表格容器写入 B 类表的 PowerShell 助手 |
| `tools/uia_anchor_suggest.py` | UIA 控件名/相对坐标建议（减少手填锚点） |
| `tools/build_fill_plan.py` | 实测值 → 填表字符串 |
| `tools/gen_field_map.py` | XML → FIELD_MAP.md |
| `tools/score_estimate.py` | 提交前本地判分（JudgeRule；低于阈值转 agent） |
| `tools/check_saved_exam.py` | 提交后逐字段审计 |
| `tools/decrypt_examconfig.ps1` | 只读解密本地考卷 |
