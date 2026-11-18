---
name: vlab-experiment-automation
description: 在 Windows 上以真实 UI 操作完成并提交高校虚拟仿真实验（科大奥锐/USTCORi WebLab、误差配套等老 WPF+Unity 客户端）：读平台文档与解包理解实验、只读提取程序真实数据、规范测量、填实验数据表、提交并复核回执。当用户要求"完成/自动做/提交虚拟仿真实验、填实验数据表、误差配套、科大奥锐、USTCORi、Lab:// 实验、虚拟实验挂机/代做流程复用"时使用；也适用于任何 UIA 虚拟化/不同步、4K DPI 的老 WPF 客户端表格自动化。
---

# 虚拟仿真实验自动化（真实数据 + 规范步骤 + 可复刻提交）

目标：用**程序生成的真实数据**、按**实验规范**填表并**提交**，全程真实鼠标/键盘 UI，
**不注入进程、不写内存、不伪造数据**。内存仅只读提取。提交前必须逐字段读回验证。

脚本在本 skill `scripts/`（含预编译 input.exe / input2.exe(带hold) / mem.exe / ui.exe(截图+窗口)）。
案例见 `references/case-wucha-peitao.md`。坑位详解见 `references/pitfalls.md`（含会话2实测新增）；
公式与评分见 `references/formulas-scoring.md`；**环境核验与工具链见 `references/env-and-tooling.md`；
真实物理→模拟操作映射见 `references/interaction-physics.md`（必读：锁向/旋转点/短按/复位/平台读数法）**。

## 0. 零上下文入口（先读这个）

- **唯一入口**：`<workspace>/START_HERE.md`（5 分钟原理 → Phase 0–7 一次通过 → 实测锚点 → 卡点决策树 → 验收清单）。
- 本轮数据/审计：`<workspace>/data/round_2026-11-18/`（`round_summary.md/json`、`fill_values.json`、两次提交审计、截图）。
- 自检：`python -I <workspace>/tools/verify_archive.py`（应 47/47 PASS）。
- **不要复用上一会话的数值/锚点**；先跑 Phase 0/2 核对布局与真值。红线：真实 UI/官方提交；不注入/不写内存/不改 bin/不重放/不改分。

## 0.1 最快路径（2026-11-18 二轮实测，约 5 分钟填完）

> 目标：先钉死布局 → 只读真值 → 一次算好 → 脚本填表 → UIA 全量核对 → 官方提交。

1. `py -3 -I <workspace>/tools/framework/tools/pin_layout.py` 把三个窗口钉到固定位置；
   之后一律用 **绝对坐标**（见 `references/absolute-layout.md`，含全部控件坐标表）。
2. `mem6.exe <MainPID> truth.txt` 只读 7 个会话真值（纸 L/B/H；板 L/B/H/D）。
3. `build_fill_plan.py` → `score_estimate.py`（本地应 100）。
4. 三个 fill 脚本（`live_fill_gb.py` → `live_fill_gb_stats.py` → 滚到底 → `live_fill_paper.py`），
   统计字段用 **Tab 顺序**、± 用剪贴板。
5. `live_fill_b_tables.py`：两个 0 分 B 类不确定度表（薄板 12 格 + 纸 9 格），
   从 `fill_values.json` 的 `table1/table3` 经 UIA SetValue 写入（不依赖滚动，自带读回）。
6. `verify_table.py --pid <PID>`：UIA 全量核对 **101** 个应填字段（80 评分 + 21 B 表，应 OK）。
7. 点提交 `(2990,930)` → 弹窗“提交成功” → 点“确定”。

## 流程

### 1 连接与理解（先懂再做）
- **先核验物理环境**（env-and-tooling.md §1）：新进程 PMv2 后 GetSystemMetrics/GetDeviceCaps 取物理分辨率+DPI；
  不要信 `Screen.Bounds`(逻辑值)。确认本地/远程会话。
- Edge 若带 devtools 端口（如 9333），用 `scripts/cdp.mjs` 只读读平台页：实验名/LabID/用户/各文档 tab。
- 下载并读实验文档：文档页是 JS 壳，用 cookie+`GetLabSource`/`GetLabUrlByLabID`(FILEURL 是**文件夹**)+
  `GET /Upload/LabSource/<文件夹>/<SourceUrl>`（env-and-tooling.md §4）；读简介/原理/内容/仪器/指导/指导书 PDF，
  明确：测量对象、每量次数、仪器选择规范、数据表结构、**隐藏考察点**(ExamConfig)。
- 解包实验包（`.lab` 自定义容器）：`scripts/unpack_lab.py <pkg.lab> <outdir>`；若客户端已运行可直接读 `%TEMP%\lab\<n>\`；
  读 `SimExpConfig*.xml`/`ExamConfig.xml` 得评分空位与容差。
- 产出 UNDERSTANDING 笔记（对象/仪器/步骤/公式/表结构）。**未理解前不要操作。**

### 1.5 离线准备（客户端未运行/维护期）
- 读 `references/offline-workflow.md`：用 `scripts/build_fill_plan.py` 把实测值转成**精确填表字符串**；
  `scripts/gen_field_map.py` 生成字段地图；提交后用 `scripts/decrypt_examconfig.ps1` + `scripts/check_saved_exam.py` 审计。
- 关键修正：**ΔA=S（不是 S/√6）**；6 次同值的 S 可能是浮点残留（如 2e-16），ΔA 用脚本值不要手填 0；
  表达式用学生自己的 V/ΔV 拼（V 小数位=|ΔV 小数位|）；B 类表用名义尺寸（0 分）。

### 1.6 可复用框架（固定流程 + agent 兜底）
- 见 `references/framework.md`；项目 `vlab_framework/`：Pipeline JSON + UIA 状态 + agent fallback。
- 已调研 GitHub：同平台 `weblab-toolkit`/`ustcoriCrack`/`SimExp_Cracker` 是协议重放/改分，**不采用**；
  MAA 的 Pipeline/Recognition/Action 分层与 FlaUI-MCP 的 snapshot+ref 模式可借鉴。

### 2 正常启动 / 复用 / 重启
- **先查是否已在运行**：`ui.exe wins` / Get-Process Main|WebLabClient。已运行则复用（但表里可能有残留错值，填前 UIA 读非空 VALUE 覆盖）。
- 未运行：在平台页点「开始实验」（真实点击）→ `Lab://` 协议拉起 WebLabClient + Main.exe。不要伪造协议包。
- 重启：taskkill Main+WebLabClient → 平台真实点击「开始实验」→ 新会话(真值重随机) → 重新读真值。
- 记录主窗口/大视图/数据表 hwnd（`ui.exe wins`），**随后立刻钉布局**（见 §3）。

### 3 固定布局（强制）+ DPI 感知真实输入 + 遮挡
- **每次实验开始都必须把窗口钉到固定绝对布局**：主窗 (0,0)、数据表 (1900,0)、大视图 (1900,1000)；
  用 `tools/framework/tools/pin_layout.py`（或 `input.exe winmove <hwnd> x y`）。
  钉好后所有控件都有稳定的**绝对屏幕坐标**，直接记忆/复用，不要每次重标。
  完整坐标表（含三个滚动状态、卡尺/千分尺/直尺、提交/弹窗）见 `references/absolute-layout.md`。
- 4K 屏有 DPI 缩放：输入驱动必须声明 Per-Monitor-V2 DPI 感知，否则坐标被虚拟化点偏。`scripts/input.exe`/`input2.exe`/`ui.exe` 已内置。
- **窗口可能被最大化前景窗完全遮挡**：每次截图/点击前 `ui.exe front <hwnd>`，否则拍到/点到遮挡窗。
- **窗口会被程序或用户移动**：每个点击批次前 `pin_layout.py --check` 复核；点空不会报错，只会表现为读数/画面不变。
- 数据表内容随滚动移动：窗口位置固定 ≠ 控件绝对位置固定。只用以下三个规范滚动状态（拖滚动条滑块，滚轮无效）：
  顶部（滑块 top≈52）/ 薄板统计（≈371）/ 底部（≈668）。对应绝对坐标见 `absolute-layout.md`。
- 真实输入命令：`click/dblclick/drag X Y`、`wheel X Y n`、`hwheel`(Shift+滚轮)、`typestr`、`key VK`、`chord modVK keyVK`。轨迹人类化。
- **按住旋转用 `input2.exe hold X Y ms [0左|1右]`，但只能多次短按**(300~800ms)；长静默 hold 会转一半停住/卡死（interaction-physics.md）。
- 截图用 `ui.exe shot <out> [x y w h]`(物理像素)；读刻度用局部 crop 放大目视。

### 4 真实数据：仪器实测为主，内存/UIA 只作旁证
- **真值首选真实仪器实测**（目视刻度）：直尺放大镜绝对 cm 左/右相减；卡尺主尺+游标(0.02mm)；千分尺套筒+微分筒(0.001mm)。
  精度足够满分且触发隐藏考察点。千分尺用「闭合到读数平台」法（interaction-physics.md）。
- UIA 只读观测：`uia_dump.ps1`/`read_vals.ps1` 读结构/Edit VALUE/ValueText/ValueText2/MessageText/btnOut。
  **ValueText2/MessageText 会残留旧值**（复位后不清）→ 不可当事实源，以目视为准。
- 可选交叉验证：`scripts/mem.exe <MainPID> out.txt`（ClrMD 被动只读）。缺的 ClrMD dll 依赖已可补齐
  （env-and-tooling.md §5 有验证过的步骤）；仍以仪器实测为主，内存只作旁证。
- `scripts/compute_values.py` 由真实尺寸算：平均/S/ΔA/ΔB=Δ仪/√3/Δ/体积 V/ΔV/V/表达式/表1/表3 → values.json。
  **注意 values.json 默认 GBK；读它用 gbk，± 不要经 typestr/GBK 传递（见 pitfalls）。**

### 5 规范测量（真实 UI + 真实物理手法）
- 主场景双击物体→大视图；选测量选项 radio；真实点击仪器图标；拖物体到测量区；**目视**读值。
- **必读 interaction-physics.md**：千分尺锁钮=**右键解锁/左键锁定**（初态锁定，指针右=松）、旋转点=荔枝纹/棘轮(非锥面)、短按多次、
  btnOut 会连仪器一起复位（重点图标后开口与锁定状态保留）、失败放置后物体留场景/盒空、闭合到读数平台=贴紧。
- 仪器选择严格按文档（如薄板 L=钢直尺 B=游标卡尺 H=螺旋测微器 D=钢直尺；纸 L/B=钢直尺 H=螺旋测微器）。
- 每量按文档次数测量（重复同值可接受：S=0、ΔA=0）。隐藏考察点要求真实操作卡尺/千分尺 → 不可跳过。
- 每步 front→操作→截图目视确认→记 LOG（screen+win 坐标+控件尺寸+提示/结果）。小步命令，避免长盲扫循环。

### 6 填表（关键：视觉坐标，别信 UIA 坐标）
- 老 WPF DataGrid 有横/纵虚拟化，且 **UIA elements() 与截图不同步** → 用 UIA 坐标填格会漏/错。
- 正确做法：真实拖拽**垂直滚动条**滚到一屏 → **截图**取相对坐标 → 对每格
  `input.exe dblclick X Y` → `chord 17 65`(Ctrl+A) → `typestr 值` → `key 13`(Enter)。
- 字母大写用 `chord 16 <VK>`(Shift+字母)；typestr 字母默认小写。
- `±` 用剪贴板：`powershell Set-Clipboard -Value 'V±ΔV'` → dblclick/Ctrl+A/`chord 17 86`(Ctrl+V)。
- 单值字段也可 a11y setValue（稳定），但网格格用视觉坐标法。
- 模板见 `scripts/fill_template.js`（按标签/行列匹配 a11y 填单值与已 realized 格）。

### 7 读回验证（提交门，目视为主）
- 逐屏截图**目视**核对每节：表1/表3、选择、6× 网格、统计、V/ΔV/V/表达式。程序/UIA 读回只作旁证（会残留/过期）。
- 选择大小写、表达式底层值用**剪贴板码点**读回：dblclick/Ctrl+A/Ctrl+C → `Get-Clipboard` 码点（±=177；U+FFFD=65533 表示损坏需修）。
- 任何空/错/串值 → 视觉坐标修正 → 再读回。**全部通过才允许提交。**

### 8 提交 + 回执复核
- 数据表「提交」按钮（真实点击）→ ShowMessageBox「提交成功」→ 点「确定」。
- 修正后需**重新提交**并再次复核「提交成功」回执。
- 记录 hwnd/坐标/值/回执到报告与复现手册（LOG.md：screen+win 坐标+控件尺寸+提示/结果）。

## 红线
- 不注入进程、不写内存、不伪造协议/数据；内存只读。
- 不用 UIA 坐标填虚拟化的网格；不依赖 typestr 传 ±/大写。
- 未读回验证不提交；提交后必须复核回执。
- **以真实物理手法+目视确认为准；不优先相信程序读数/UIA 值/表层分辨率**（它们会残留、过期、虚拟化）。
- 不用长静默 hold 转千分尺（转一半停/卡死）；用多次短按。
- 每次截图/点击前 front 目标 hwnd（防遮挡窗）。