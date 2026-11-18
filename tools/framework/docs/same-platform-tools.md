# 同平台（USTCORi / 科大奥锐 WebLab）自动化工具调研

> 调研时间：2026-11-18。目的：避免重复造轮子，同时明确哪些能借鉴、哪些因合规原因不能用。
> 结论先行：同平台工具几乎都是**协议重放/改分/伪造客户端/预置答案**，不能直接采用；可借鉴的是它们的**平台协议事实**和**本地判分逻辑**。

---

## 1. 工具清单

| 项目 | 类型 | 支持实验 | 实现方式 | 合规结论 |
|---|---|---|---|---|
| `NaBr406/weblab-toolkit` | 抓包重放/一键满分 | 任意有 `StdResult` 的实验；实测示波器 163、电桥 166、声速 162、动态磁滞回线 | 本地 HTTP 代理抓 `POST /ServiceAPI/UpdateRecord` → 解密 `Content` → 把 `RealResult` 填成 `StdResult` → 原样重放 | **不采用**（伪造提交） |
| `whmmhw/ustcoriCrack` / `PyrojewelMissU/Ustcori_Crack` | 伪造实验大厅/客户端 + 本地判分 | 通用 USTCORi 实验（不针对单个实验） | C# 引用 `USTCORi.WebLabClient` 与 `SimExp.Instruments.Component.dll`；`FakeApp/FakeHall/FakeHall2` 复刻大厅 WCF 调用与 `USTCORI_*` 消息；`PaperReviewer` 按 `JudgeRule` 本地评分；`CMMDataCrypto` 复刻客户端 DES/AES | **不采用**（伪造客户端/改分） |
| `MuelNova/SimExp_Cracker` | Python 加解密/上传 | 通用 USTCORi | `gzip + AES-ECB + 质数插噪 + base64` 加解密；`gen_key` 复刻 `Sec.GenerateKey`；`upload` 直接 POST `UpdateRecord`；`get_content` 拉取实验 XML | **不采用**上传/改分；加解密事实用于只读审计 |
| `missfdu/PhysicalExperiment` | 预置高分数据文件 | 18 个实验：万用表 225、光强调制法测光速 100、分光计 65、动态磁滞回线、单缝衍射 99、声速 97、太阳能电池 100、干涉法测微小量 58、拉曼光谱、杨氏模量 60、热电偶、碰撞、示波器 88、红外波 100、落球法测粘度 100、迈克尔孙干涉仪 180、长度与固体密度 100、霍尔效应 99 | 直接提供各实验的高分 XML；`xml_Real2Std.cs` 把空白数据转成答案数据；base64 + 抓包重放 | **不采用**（预置答案） |
| `SUSTC/PhysicsExprSimulationTest` | 信息提取/测试系统 | 通用 USTCORi 考试记录/答卷/试卷模板 | 登录、查成绩、取答卷、取试卷模板；走平台 WCF/HTTP API | 只读提取；但“查他人答卷”有隐私问题；不作为自动化方案 |
| `lightsing/Another-Lab` / `PESTest-NG.js` | Electron/Node 协议客户端 | 通用登录/考试信息 | `PESTAgent`/`PESTxml` 调 `USTCORi.ExamSystem.BLL.*` 接口 | 协议研究；不是实验自动化 |
| `ztearroo/cheat-obrsim` | 不同平台（ilab-x、郑州大学金刚石合成） | 仅该校该实验 | 重放进度/报告数据，随机延时 | 与 USTCORi 无关 |
| `c2451134117-cyber/physics-lab-preexam`、`Lincyyyyyy/physics-lab-preexam` | 预习考试一键答题 | 预习系统，不是仿真实验 | 油猴脚本/书签 | 与仿真实验无关 |

---

## 2. 它们分别怎么实现

### 2.1 `weblab-toolkit`：抓包 → 解密 → 填标准答案 → 重放

流程（来自其 README/脚本）：

1. `1-开始抓包.bat` 把系统代理指到 `127.0.0.1:8888`，`HttpSpy.exe` 记录客户端提交。
2. 正常进实验，点「结束实验」，客户端 `POST /ServiceAPI/UpdateRecord`，body 含：
   `UserID / LabID / LabName / RecordID / FileName / Content / Key`。
3. `LabDecrypt.exe` 解密 `Content`，得到 `ExamPaper` XML。
4. `Invoke-LabPerfect.ps1` 把每个 `Para` 的 `RealResult` 改成 `StdResult`；两边都空就塞 `1`；可选 `-Fill` 指定实际值、`-NoSynthesize` 不补造。
5. 用抓到的 `RecordID`/`Key` 原样重放；服务端返回 `1` 即成功。
6. 可选 `-Delay`/`-RandomTime` 控制重放时刻，模仿真实用时。

关键事实（我们用于只读审计，不用于重放）：
- `Content` 是加密 XML；`Key` 只签 `UserID,LabID,FileName`，**不覆盖 Content**；服务端不校验时效（其 README 自述）。
- 服务端返回码：`1` 成功，`-3` RecordID 不匹配，`-4` Key/FileName/UserID 不匹配。
- 判分是逐 `Para` 比较 `RealResult` 与 `StdResult`，规则多为相对偏差。

### 2.2 `ustcoriCrack` / `Ustcori_Crack`：伪造大厅 + 本地判分

- C# 控制台程序，引用官方 `USTCORi.WebLabClient` 与 `USTCORi.SimExp.Instruments.Component.dll`。
- `FakeApp` 解析实验链接；`FakeHall`/`FakeHall2` 复刻大厅的 `UserCountControl`、下载 `.lab`、`SetLabStart/End`、`USTCORI_*` 消息。
- `PaperReviewer` 读取试卷 XML，按 `JudgeRule` 逐 `Para` 本地算分；能打印答案区间。
- `CMMDataCrypto` 是客户端 DES/AES 的反编译副本。
- 它不“做实验”，而是伪造会话/直接构造满分卷。

### 2.3 `SimExp_Cracker`：纯 Python 加解密/上传

- `Experiment.decrypt`：base64 → 去质数插噪 → AES-ECB 解密（key 为 16 字节）→ gzip 解压。
- `Experiment.encrypt`：反向操作。
- `gen_key`：复刻 `Sec.GenerateKey`（MD5 + 时间 + 字符置换）。
- `upload`：直接 POST `UpdateRecord`。
- `get_content`：从平台拉取实验 XML。
- 它证明“客户端加密/签名”不是秘密；但也说明服务端信任客户端提交。

### 2.4 `PhysicalExperiment`：预置答案库

- 18 个实验的高分 XML 数据文件；`xml_Real2Std.cs` 把空白数据转成答案数据。
- 本质是“答案库 + 抓包重放”，不涉及实验操作。

### 2.5 `SUSTC` / `PESTest-NG.js`：协议/信息提取

- `SUSTC` 是 WinForms 测试系统：登录、查成绩、取答卷、取试卷模板。
- `PESTest-NG.js` 是 Node.js 的 `PESTAgent`/`PESTxml`，调用 `USTCORi.ExamSystem.BLL.*`。
- 它们是协议客户端，不是实验自动化；`SUSTC` 的“查他人答卷”还有隐私问题。

---

## 3. 我们借鉴了什么

| 借鉴点 | 来源 | 在我们的哪里 |
|---|---|---|
| 提交接口/返回码/判分模型 | `weblab-toolkit` 协议分析 | `REVERSE_ANALYSIS.md`、`check_saved_exam.py` |
| `ExamConfig.bin` 加密格式 | `weblab-toolkit`、`SimExp_Cracker` | `decrypt_examconfig.ps1`（用客户端 DLL 只读解密） |
| `JudgeRule` 本地评分逻辑 | `ustcoriCrack/PaperReviewer` | `score_estimate.py`、`check_saved_exam.py` |
| Pipeline/Recognition/Action 分层 | `MaaXYZ/MaaFramework` | `vlab_framework/core/*`、pipeline JSON |
| `interface.json` + `resource/pipeline` + `agent/` 目录 | `MaaPracticeBoilerplate` | `vlab_framework/interface.json`、`assets/resource/pipeline` |
| UIA `snapshot` + `ref` 模式 | `shanselman/FlaUI-MCP` | `uia_anchor_suggest.py`、`read_vals.ps1` |
| 真实输入/DPI 处理 | 我们自己的 `input.exe/ui.exe` | `core/controller.py` |

## 4. 我们明确不采用什么

- 抓包重放 `UpdateRecord`（`weblab-toolkit`）。
- 伪造大厅/客户端/考试会话（`ustcoriCrack`）。
- 直接上传/改分（`SimExp_Cracker`）。
- 预置答案库（`PhysicalExperiment`）。
- 查他人答卷/成绩（`SUSTC`）。
- 任何“填 `StdResult` 再提交”“补造 `1`”“绕过计时/录屏”的做法。

原因：这些能力都超出“合规自动化”的边界；本项目的红线是**真实测量、真实 UI、官方提交、只读审计**。

---

## 5. 对我们的启示

1. **平台客户端侧防护很弱**：签名不覆盖 Content、服务端信任客户端标准答案、`Main.exe` 启动后自毁磁盘副本。这些事实说明“协议层作弊”很容易，但也正是我们不能走的路。
2. **真正难的是实验操作**：图形刻度、仪器状态、窗口布局；这也是我们框架把 agent 兜底放在“读数/异常”上的原因。
3. **本地判分可复用**：`PaperReviewer` 的 `JudgeRule` 逻辑可以直接用于提交前自检；我们已实现 `score_estimate.py`。
4. **架构比代码更值得借鉴**：MAA 的 Pipeline/Recognition/Action 分层让新实验只需换 JSON，不用改引擎。
