# 环境核验与工具链（会话2 实测）

## 1 物理环境核验（不要信表层）
新 PowerShell 进程，**先**声明 PMv2 再取数：
```
Add-Type user32: SetProcessDpiAwarenessContext(-4), GetSystemMetrics, GetDeviceCaps(GetDC(0))
GetSystemMetrics(0/1)      -> 物理宽高 (实测 3840x2160)
GetDeviceCaps(hdc,88)      -> LOGPIXELSX (168 = 175%)
GetDeviceCaps(hdc,118/117) -> DESKTOPHORZRES/VERTRES (物理)
GetSystemMetrics(0x1000)   -> SM_REMOTESESSION (0=本地)
WMI Win32_VideoController  -> 交叉验证
```
- `Screen.PrimaryScreen.Bounds` 给逻辑值(2194x1234)，即使同进程调了 PMv2 也可能不变 → 不可作物理依据。
- 手搓 DEVMODE + EnumDisplaySettings 返回全 0（struct 布局/size 错）→ 弃用，用 GetDeviceCaps。
- 一切 input/截图坐标=物理像素。逻辑→物理 ×(dpi/96)=×1.75。

## 2 截图/窗口助手 ui.exe（scripts/ui.cs，csc 编译）
子命令：`shot <out.png|jpg> [x y w h]`(默认全屏, PMv2, 物理像素) / `wins`(hwnd pid rect title) / `rect <hwnd>` / `front <hwnd>` / `move <hwnd> x y` / `fg`。
- **每次 shot/点击前 front 目标 hwnd**，否则拍到遮挡窗。
- 编译：`csc -nologo -target:exe -out:<绝对路径>\ui.exe -r:System.Drawing.dll <绝对路径>\ui.cs`
  （MSYS 下必须 `-` 选项+绝对路径；`/nologo`、相对路径会被转成 Git 路径）。
- 大图落 D 盘(C 盘紧张)； viewing 用 PIL 缩到 ~1400 宽 jpg q88；读刻度用局部 crop 放大(LANCZOS ×6)。

## 3 编码
- .NET/PS 中文 → MSYS 控制台 GBK 乱码：写 UTF8 文件再 Read，勿凭控制台判断。
- MSYS python 读 JSON：`json.loads(sys.stdin.buffer.read().decode('utf-8'))`（stdin 文本按 GBK 解码会因 0x5C 尾字节炸）。
- values.json 默认 GBK（沿用旧坑）。

## 4 平台文档抓取（无需渲染）
```
cookie: CDP Network.getCookies({urls:[平台]}) -> ASP.NET_SessionId; COOKIES_KEY_USERNAME
POST /ReportStudent/SLabSource/GetLabSource        data LabID=133      -> [{SourceName,SourceUrl}]
POST /ReportStudent/SLabSource/GetLabUrlByLabID    data LabID,SourceName -> {FILEURL:"误差配套\"}  # 文件夹!
GET  /Upload/LabSource/<FILEURL文件夹>/<SourceUrl>  -> htm/pdf
```
- 直接 GET /Upload/LabSource/ =403；新开 tab 读文档跳 Login → 用 curl+cookie。
- CDP evaluate+awaitPromise fetch 易 25s 超时 → 批量用 curl。
- htm 多为 GB2312：decode gb18030 → 去 script/style/标签 → txt。PDF 用 Windows Python312 pymupdf 提文本+render 页图。

## 5 ClrMD / mem.exe 缺口
- mem.exe 依赖 Microsoft.Diagnostics.Runtime.dll **未随 skill 附带** → FileNotFoundException。
- 程序集 3.1.10.12801 ↔ nuget 包 3.1.512801；ClrMD3.1 仅 lib/net6.0+netstandard2.0（无 net462）。
- 本机 dotnet **只有 runtime 无 SDK** → 不能 dotnet build；netfx csc 仅 C#5。
- nuget 可达：api.nuget.org 302 → nuget.azure.cn（国内镜像）。
- **依赖可补齐（会话3实测，mem.exe 已跑通）**：
  1. 从 clrmd.nupkg 取 `lib/netstandard2.0/Microsoft.Diagnostics.Runtime.dll`（程序集 3.1.10.12801）；
  2. System.Memory 用 net461 版（4.0.1.1）；`mem.exe.config` 的 System.Memory `newVersion` 改成 `4.0.1.1`；
  3. 其余依赖用 `<local-research>\decomp\lib` 的 net461 版（Buffers 4.0.3.0 / Immutable 6.0.0.0 / Metadata 6.0.0.0 / Unsafe 6.0.0.0 / Numerics 4.1.4.0 / Tasks.Extensions 4.2.0.1）；
  4. 全部与 mem.exe 同目录 → `mem.exe <pid> out.txt` 正常只读附加。
- 要枚举非 `USTCORi.SimExp` 前缀的混淆类型：老 csc(C#5) 对 `ClrInstanceField.Read<T>` 的 unmanaged 约束报 CS0570 → 用反射 `MakeGenericMethod` 调用；编译加 `-r:netstandard.dll -r:System.Core.dll`（示例 `<local-research>\mem\mem4.cs`）。

## 6 Headless 反编译（理解逻辑用，只读）
scripts/decomp.ps1。依赖放 <local-research>\decomp\lib（或改脚本 lib 路径）：
ICSharpCode.Decompiler 8.2.0.7535 + System.Collections.Immutable 6.0.0 + System.Reflection.Metadata 6.0.0
+ System.Runtime.CompilerServices.Unsafe 6.0.0 + System.Memory 4.5.4 + System.Buffers 4.5.1
+ System.Numerics.Vectors 4.5.0 + System.Threading.Tasks.Extensions 4.5.4（各取 lib/net461 或 netstandard2.0）。
- **预加载**全部依赖 Assembly.LoadFrom；**禁止** AssemblyResolve→LoadFrom handler（StackOverflowException）。
- 枚举类型：`[ICSharpCode.Decompiler.TypeSystem.TypeSystemExtensions]::GetAllTypeDefinitions($dec.TypeSystem)`（扩展方法，不能实例调用）。
- `DecompileWholeModuleAsString()` 对这些 dll 抛 DecompilerException → 用 `-Each` 逐类型 try/catch。
- 枚举含引用框架类型 → 海量 "not found in module" FAIL 属正常，只看本模块命名空间类型。
- 仪器 dll 混淆+字符串加密 → 明文消息搜不到；放置判定逆向不划算，改经验探针。

## 7 UIA 只读 dump / 探针
- scripts/uia_dump.ps1：按 pid dump 全顶层窗子树（ControlViewWalker），输出 ControlType/Name/AutomationId/Value/Text/rect。
  用 `TreeWalker.GetFirstChild/GetNextSibling`（**无 FindNext**）。
- scripts/read_vals.ps1：单进程读 ValueText/ValueText2/MessageText，写 <local-research>\vals.txt(UTF8)。
- scripts/probe_hover.ps1：单进程 SetCursorPos 逐点悬停 + 扫**该 pid 全部顶层窗**(ToolTip 是独立 Popup) 匹配提示词。
  注意本模拟悬停不出提示（提示仅交互后瞬现）→ 探针结果全 no-tooltip 不代表不可操作。
- 每点起一个 PS 进程太慢 → 批量放单进程。