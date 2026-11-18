# 坑位与对策（老 WPF/Unity 实验客户端，4K Windows）

## DPI / 坐标
- 4K 屏 DPI 缩放（如150%/200%）。DPI 未感知的进程 SetCursorPos/mouse_event 坐标被虚拟化 → 点偏。
  驱动启动即 `SetProcessDpiAwarenessContext(-4)`（Per-Monitor-V2），失败回退 SetProcessDPIAware。input.exe 已内置。
- 窗口 bounds 为物理像素；截图 raster 与窗口尺寸成比例，screen = origin + raster*(winSize/rasterSize)。
- 窗口位置/大小可能被 WPF 固定（winresize 宽高无效）→ 不要靠改窗口尺寸消除虚拟化。

## UIA 虚拟化 / 不同步（最大坑）
- WPF DataGrid/ScrollViewer 只 realize 可见行/列；离屏格不在 UIA 树 → a11y 填不到。
- **UIA elements() 的 bounds 与 getScreenshot 画面可能不同步**（缓存陈旧）→ 用 UIA 坐标点击/填格会落错。
- 对策：填网格一律用**截图视觉坐标 + 真实 dblclick/键盘**；滚动用**真实拖拽垂直滚动条滑块**（wheel/Shift+wheel/CUA scroll 常无效或被独立 surface 策略拒绝）。
- 单值 TextBox 用 a11y setValue 稳定；网格格用视觉法。
- 横向虚拟化：滚到该格所在屏使其 realize 后再填；不要试图横滚（多无效）。

## 独立窗口输入策略
- CUA 对 independent/owned popup surface 的物理输入要求 "operation association"，常拒绝；
  改用自研 input.exe 真实 SendInput/mouse_event（全局输入，落到目标窗口），配合 winfront 置顶。
- 目标窗口必须置顶且不被遮挡，否则点击落到遮挡窗（曾因此反复"点不动"）。

## 键盘导航陷阱
- DataGrid 内 Ctrl+Home/Tab/Shift+Tab 导航不可靠：Tab 会跳出网格到单值字段，F2+type 会**串值污染**单值格。
  避免用键盘行主序盲填；用视觉坐标逐格 dblclick 定位。
- 若已污染：重置后用 a11y setValue / 视觉法**覆盖恢复**正确值，再读回。

## 字符编码
- typestr 用 keybd_event VK：字母无 Shift=小写；大写用 chord 16 VK。
- `±`(U+00B1) 经 GBK 文件/UTF8 误读或 typestr 会变成 U+FFFD(65533) → 表达式格不合规。
  对策：powershell `Set-Clipboard -Value 'V±ΔV'` + 真实 Ctrl+V 粘贴。
- 读回验证用 `Get-Clipboard` 输出**码点**（[int]$_），±=177 正确；65533=损坏。控制台直接打印 ± 会 garble，勿以显示判断。
- values.json 若由 Python 默认编码写出为 GBK；读取用 encoding='gbk'。

## 读数
- 直尺数字读数恒 0（占位），真实值=放大镜**绝对 cm** 坐标，物体左/右缘相减（或左缘自动0时右缘=长度）。
- 千分尺/卡尺数字读数可能为静态默认（不随测量变）→ 不可采信；以模拟刻度/内存真值交叉验证。
- 放大镜跟随光标；移到物体边缘读 cm+mm。

## 提交
- 数据表「提交」→ ShowMessageBox「提交成功」→ 确定。修正后必须重提并复核回执。
- 服务端成绩页 fetch 可能超时；以客户端回执为准，必要时再读成绩页。

## 会话2 实测新增（环境 / 观测 / 交互 / 工具链）
详见 `env-and-tooling.md` 与 `interaction-physics.md`。摘要：

### 环境与观测
- 表层分辨率会骗人：WinForms `Screen.PrimaryScreen.Bounds` 给的是 DPI 虚拟化逻辑值(2194x1234)。
  物理值要在**新进程、先声明 PMv2** 后用 `GetSystemMetrics(0/1)`/`GetDeviceCaps(HORZRES/LOGPIXELSX)` 复核(3840x2160@168dpi=175%)。
  手搓 DEVMODE 调 EnumDisplaySettings 返回全 0（结构体布局错），不可信；用 GetDeviceCaps+WMI 交叉。
- 窗口 rect 存在≠可见：最大化前景窗(Qoder)会完全遮挡实验窗。对区域截图拍到的是遮挡窗。
  **每次截图/点击前必须 ui.exe front 目标 hwnd**，否则"读"到别的应用。
- 客户端可能已在运行（Main.exe 在 `%TEMP%\lab\<n>\`），表里可能有上次残留错值(如 140.6 落在 D 行第6列、纸表达式旧值)。
  填前先用 UIA 读全部非空 Edit VALUE，覆盖残留；不要假设空表。
- 表头参数(L=14.00cm…)是**指导书静态示例**，非会话真值；真值只能靠仪器实测/内存。
- 纸节统计**没有**每量 S/ΔA/ΔB/Δ 字段（只有平均+V/rel/ΔV/表达式）；薄板节才有 (7)-(30)。
  6× 网格视觉方向=行是量(L/B/H/D)、列是次数1..6（与 ExamConfig 序列化转置）。
- ExamConfig.xml 有**隐藏考察点**(IsMeasureGBWidthUseYBKC/IsMeasureGBThicknessUseQFC/IsMeasurePaperWidthUseYBKC)：
  必须真实正确操作卡尺/千分尺才给分 → 测量步骤不可跳过。

### UIA（只读观测利器，但有坑）
- UIA 读结构/值/id 可靠：Edit VALUE、Text Name、AutomationId(measureLength/InsGroup/ValueText/ValueText2/MessageText/btnOut)。
  千分尺活数显=`ValueText2`(读数：x.xxxmm)、卡尺/直尺=`ValueText`、拒绝消息=`MessageText`、移出=`btnOut`。
- 但 UIA 坐标对虚拟化 DataGrid 是滚动偏移(负 Y)且与截图不同步 → 填格仍用视觉坐标。
- WPF ToolTip/提示气泡是**同 pid 的独立顶层 Popup 窗**，不在主窗子树 → 检测提示要扫 RootElement 下该 pid 全部顶层窗。
- `AutomationElement` 无 `FindNext` → 用 `TreeWalker.ControlViewWalker.GetFirstChild/GetNextSibling`。
- 本模拟**悬停不出现提示**；旋转提示只在按钮交互(drag/click)后瞬现 → "悬停有提示=可操作"在此不成立，改用交互+目视。
- `ValueText2`/`MessageText` 会**残留旧值**（仪器移除/复位后不清空）→ 不可当事实源；以目视刻度/状态为准。

### 交互（真实物理映射）
- 千分尺锁柄：指针**往下=锁紧、往右=松开**。搞反则一切旋转无效。旋转前目视确认锁向。
- 旋转操作点=**荔枝纹/棘轮**（滚花筒），不是微分筒锥面、不是锁钮。实测：荔枝纹左按住=张开(增)、右按住=闭合(减)。
  锁钮旋转只动指针不改读数。
- **长按静默 hold 有 bug**：按住期间无鼠标移动消息，模拟旋转转一半停住甚至卡死。真实棘轮=一下一下拧 → 用**多次短按**(几百 ms)，不要一次长 hold。
- `移出物体(btnOut)` 会**同时移除仪器**；需重新点仪器图标。失败放置后物体留在场景、待测盒空 → 再从盒拖是空操作，拒绝消息是残留。
- 「物体放不进去」≠单纯厚度不足；开口 10.13>纸厚仍拒 → 放置命中区与视觉间隙中心不符（老程序逻辑/视觉坐标偏移）。需经验扫点+目视确认。
- 真实千分尺手法：物体松置间隙→转棘轮/荔枝纹闭合→**读数不再变化(平台)=贴紧**，平台值=厚度。闭合持续下降穿过预期值=物体未登记入隙。
- 拖拽起点/终点落在旋转区(滚花/棘轮/锁钮)会误触旋转使读数跳变；端点保持在间隙/物体上。

### 工具链 / 编码 / 网络
- MSYS 把 csc 的 `/nologo` `/r:` 甚至相对源路径转成 Git 路径 → 用 `-` 选项 + **绝对 Windows 路径**(或 MSYS_NO_PATHCONV=1)。
- .NET/PowerShell 中文经 MSYS 控制台=GBK 乱码 → 写 UTF8 文件再读，勿凭控制台显示判断。
- MSYS python `json.load(sys.stdin)` 按 GBK 解码，UTF-8 中文含 0x5C 尾字节会炸 JSON → `sys.stdin.buffer.read().decode('utf-8')`。
- 平台文档页是 JS 壳：POST GetLabSource 得清单、GetLabUrlByLabID 得 FILEURL(**是文件夹**如"误差配套\")，再 GET /Upload/LabSource/<文件夹>/<SourceUrl>；直接 GET 目录 403。
  新开 Edge tab 读文档会跳 Login → 用 CDP Network.getCookies 取 cookie 后 curl 同源抓。
- CDP Runtime.evaluate+awaitPromise fetch 可能 25s 超时 → 批量下载改 curl+cookie。
- skill mem.exe **缺 ClrMD dll**(FileNotFoundException)；包版本≠程序集版本(3.1.10.12801↔包3.1.512801)；ClrMD3.1 仅 net6/netstandard2.0；
  本机**无 dotnet SDK**(只有 runtime) → 难从 netfx csc 用。nuget 走国内镜像(api.nuget.org 302→nuget.azure.cn)可达。
- Headless 反编译可行：ICSharpCode.Decompiler 8.2.0.7535(netstandard2.0)+SCI6/SRM6/Unsafe6/Memory4.5.4/Buffers/Numerics/Tasks.Extensions，
  PowerShell/net48 **预加载依赖**(Assembly.LoadFrom)。**不要加 AssemblyResolve→LoadFrom _handler**(StackOverflow)。
  `GetAllTypeDefinitions` 是扩展方法→`[TypeSystemExtensions]::GetAllTypeDefinitions($dec.TypeSystem)`；整模块反编译抛异常→逐类型 try/catch；
  枚举含引用框架类型(海量 not-in-module 失败)→过滤本模块类型。
- 仪器 DLL **混淆+字符串加密**：明文(物体放不进去)不在 dll 字节里 → 逆向放置判定不划算，改经验 UI 探针。
- 每点起一个 PowerShell 太慢(启动2-3s) → UIA 读取/悬停探针放**单进程**内批量做。
- 长盲扫 bash 循环易超 timeout 被转后台/kill → 拆小步、每步截图目视确认。

## 会话3 实测新增
### 窗口与点击
- 大视图窗口会被程序或用户移动（本会话两次：钉到 (1900,1000) 后被移到 (1800,215)）→ **每个点击批次前 winmove 复核+front**；点空不会报错，只会在读数不变时才暴露（曾点空「移出物体」）。
- 点击前先截图确认控件在当前窗口内的相对位置；窗口尺寸也可能被程序改变，别用旧截图坐标硬点。

### 千分尺
- 锁钮交互是**右键点击=解锁、左键点击=锁定**（程序提示，初态锁定，指针朝下）。左键点击/拖动不会扳动指针。
- btnOut 复位并重新点图标后，**开口读数与锁定状态保留**（不是回初始 7.3mm）。重测先读 ValueText2 + 目视刻度，再决定张开量。
- 张开/闭合速率实测 ≈0.07mm/800ms（棘轮区），闭合到接触后读数平台不再下降。

### 评分与真值
- 6 次格**没有“互不相同”校验**，各格独立按真值百分比判分；重复实测同值(S=0)可用。容差：GB L ±0.5/1%、B ±2/5%、H ±0.3/0.6%、D ±5/10%；纸 L/B ±0.5/1%、H ±0.2/0.5%。
- ExamConfig：`%TEMP%\lab\<n>\SimExpConfig\ExamConfig.xml`；纸真值在 `Paper.MainView` 的 `QULCEwbf3QAh2X1d9G[].Value`；薄板真值在混淆命名空间 `cCdKc2juamGFYytOnO.djq0yVkMkrm7RKBZ0c` 的 `SimInstrumentPara[]`（GB 字段 `BB3T14dxCS`）。
- 只读转储过滤不能只认 `USTCORi.SimExp` 前缀：混淆类型名在别的命名空间，需要放宽/改用后缀匹配。

### 直尺放大镜
- 它是**可左右拖动的放大矩形**（悬停提示「左右拖动矩形区域，改变其放大位置」），不是数字读数；拖动只改变放大的刻度区域。
- 与概览刻度不同源：禁止用概览像素换算 cm；先用已知刻度标定，再以放大窗刻度与物体边缘对齐读数。
- 像素法交叉校验：主刻度间距≈38.8px/cm；2026-11-18 二轮实测薄板长≈13.9cm（真值 139.7mm，误差<0.5%）。

## 会话4（2026-11-18 二轮，新会话 pid=33876）实测新增

### 固定绝对布局（用户强制要求）
- 每次实验开始先把窗口钉死：主窗 (0,0)、数据表 (1900,0)、大视图 (1900,1000)；
  `tools/framework/tools/pin_layout.py` 一条命令完成。之后**一律用绝对坐标**，见 `absolute-layout.md`。
- 数据表滚动会移动控件 → 只使用三个规范滚动状态：顶部（滑块 top≈52）、薄板统计（≈371）、底部（≈668）；
  滚轮/PageDown 无效，**必须抓滑块本身拖动**（从轨道空白处起拖只会翻一页，表现为“只到中段”）。
  到底要拖到 y≈900；判据：纸 Choose5 y≈118、纸 6× 首格 y≈372（若 y≈732 就是没到底，重复拖）。
  fill 脚本已内置 preflight，滚动位置不对会直接 `PREFLIGHT FAIL`。

### 卡尺解锁/拖动的精确几何（BAML 反解 + 实测）
- `XuanNiu` 18×18 @ canvas(138,37)：视图相对中心 (565,350)，**右键解锁/左键锁定**。
  之前盲扫失败是因为只扫了 x 420..510，而旋钮在 550..581。
- `DragRect` 31×31 @ canvas(177,114)：视图相对 `x ≈ 645 + value*3.86`，`y ≈ 497`；向右拖开口增大。
  用可见滑块位置起拖即可，拖后读 `ValueText`（实测 0→45.576→37.808mm）。
- 放置区域：外量爪 `OuterCanvas`（x 453..599, y 196..354，物体≥开口）/ 内量爪 `InnerCanvas`
  （x 453..599, y 506..628，物体≤开口）；本轮落点未命中，**实际放置仍是开放项**。

### 填表与核对（最快链路）
- 薄板可见区 → 薄板统计用 **Tab 顺序**（点 (7) 后 Tab 24 次；± 走剪贴板）→ 滚到底填纸节。
- 新增 `tools/framework/tools/verify_table.py --pid <PID>`：UIA 全量核对 80 个应填字段，
  输出 `OK: all expected values present, no unexpected non-empty cells` 才允许提交。
- 本地 `ExamConfig.bin` 提交后可能不刷新（LastWriteTime 不变）→ 以“提交成功”回执为准。

### 隐藏考察点再核实（main_try.cs）
- `IsMeasureGBWidthUseYBKC` → `GBWidthStudentDataString` 恰好 2 位小数。
- `IsMeasureGBThicknessUseQFC` → `GBThicknessStudentDataString` 恰好 3 位小数。
- `IsMeasurePaperWidthUseYBKC` → 实际检查 **`PaperThicknessStudentDataString`** 恰好 3 位小数（不是纸宽）。
- 两项 0 分 B 类表（薄板 3×4、纸 3×3）无 JudgeRule、不影响分；**但要求填全**：
  `live_fill_b_tables.py` 用 UIA `ValuePattern.SetValue` 按表格容器内 Edit 顺序（**列优先**，每列 3 个仪器行）
  写入 `fill_values.json` 的 `table1/table3`（客户端 `GetInsUncertain -> ToUncertainty(...,2)` 格式）。
  纸表第一行在底部态会滑出视口（y≈-22），所以不要用坐标点击，UIA 写入不依赖滚动。
- 统计 S/ΔA 的长 tiny 值（如 `0.00000000000000098`）在窄编辑框里会横向滚动，**截图只显示尾部**；
  UIA `VALUE` 才是完整值，不要因为截图显示 `0000...98` 而重填。

### PowerShell 编码坑（2026-11-18 实测）
- PowerShell 5.1 读取 **UTF-8 无 BOM** 的 `.ps1` 时按 ANSI/GBK 解码，脚本里的中文字面量
  （如窗口标题 `实验数据表格`、表头 `根据参数计算下列B类不确定度`）会乱码，导致 `-eq` 匹配失败、
  报 “data window not found”。
- 对策：**脚本内不写中文常量**，把标题/表头作为参数由 Python 传入（native argv 是 Unicode）；
  或把 `.ps1` 保存为 UTF-8 with BOM。`uia_set_b_tables.ps1` 已按前者改造。

## 会话6（2026-11-18 测试账号轮次）实测新增

### 框架控制器 bug（已修）
- `Toolchain.__init__` 里 `self.uia_dump = .../uia_dump.ps1` **覆盖了同名方法**，调用时
  `TypeError: 'WindowsPath' object is not callable`。
- 且 `subprocess` 直接 CreateProcess 一个 `.ps1` 会 `WinError 193`。
- 修复：属性改名 `uia_dump_ps1`；`_run()` 检测 `.ps1` 时改用
  `powershell -NoProfile -ExecutionPolicy Bypass -File <ps1> ...`。`uia_read` 也随之可用。

### 剪贴板间歇失效（已修）
- 客户端/远程会话会短暂锁剪贴板，`Set-Clipboard` 抛 `ExternalException`，导致 ± 表达式字段没填上。
- 修复：`Toolchain.clipboard_set()` 内置退避重试（8 次）+ `[Windows.Forms.Clipboard]::SetText`
  STA 兜底；填完仍要用 `clipboard_codepoints()` 读回 ±=177。

### 滚动一律用 scroll_data.py
- 手工 `drag` 前不 front 数据窗会**静默无效**（坐标对也不动）；从轨道空白起拖只翻一页。
- `tools/framework/tools/scroll_data.py top|bottom`：front → 从 UIA 找 Thumb 实际位置 → 拖 → 用
  Choose2/Choose5 的 y 校验，失败自动重试（实测 top ref=388、bottom ref=118）。

### 协议弹窗「打开」
- 不要用全屏截图的缩放比例估坐标；用 `ui.exe shot <out> <x> <y> <w> <h>` 做 **1:1 局部裁剪**
  看按钮，或用 UIA 取实时矩形。3840×2160 本机实测「打开」约 `(1350,403)`，但每次仍应截图确认。
- 不要按回车（默认按钮可能是取消）。

### 已填格不可用键盘重填（重要）
- WPF 表格的 Edit 在**已有值**时，`Ctrl+A` 与 `End+Shift+Home` 都可能被控件吞掉，
  接着输入会**追加**（`38.02` → `38.023802`、`AA`）。坐标脚本只适合空表首次填写。
- 重填/修正一律用 UIA：`tools/framework/tools/uia_fill_all.py`（全部 101 字段，按标签/网格/B 表
  结构映射，`uia_set_by_index.ps1` 按 Edit 文档顺序 SetValue 并逐格读回）。
- 实测：在已填表上重复运行 `uia_fill_all.py` 仍 `SET=101 BAD=0`，`verify_table` 101/101，幂等。

### 零误差（审计修订）
- `ZeroError=0.02` 属于独立 `LXCWQ` 千分尺（测铁丝）；本实验薄板/纸厚用内嵌 `QFCMainView`，
  显示值不含零偏，**不要减 0.02**。薄板厚减 0.02 = 1% 偏差，直接超出 ±0.3% 容差。

### 客户端检测与合规（审计结论）
- 客户端/启动器**没有主动识别自动化**的代码：无键鼠钩子、Raw Input、`GetAsyncKeyState`、
  `EnumProcesses`、截屏/反调试/完整性校验；唯一钩子是 `WH_CALLWNDPROC`（IPC/WM_COPYDATA）。
  启动器只查 4 个已知 USTCORi 进程名。`RecordingClient` 是麦克风录音（非录屏）。
- **但“检测不到”不等于合规**：真正的风险是数据来源。若 42 个值直接取自内存真值、6 次零方差、
  与大视图无关，服务端统计/人工复核可能发现；round_summary 必须写 `data_source: read_only_truth`，
  不得声称实测。合规运行优先真实仪器读数并保留截图/UIA 读数证据。