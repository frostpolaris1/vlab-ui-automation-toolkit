# VLab 一键实验启动器（UTF-8 控制台）
param(
  [switch]$DoctorOnly,
  [switch]$NoSubmit,
  [switch]$Force,
  [switch]$CheckGuard,
  [switch]$PromptTest
)
$ErrorActionPreference = 'Stop'
try {
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  $OutputEncoding = [Console]::OutputEncoding
} catch {}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '============================================================' -ForegroundColor Cyan
Write-Host '  VLab 误差配套 - 一键实验' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  Write-Host '[错误] 未找到 Python 启动器 py。请安装 Python 3 并勾选 Add to PATH。' -ForegroundColor Red
  Read-Host '按回车关闭'
  exit 1
}

if ($DoctorOnly) {
  & py -3 -I tools\framework\tools\doctor.py
  Write-Host ''
  Read-Host '按回车关闭'
  exit $LASTEXITCODE
}

$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$archive = "data\round_${ts}_oneclick"
Write-Host "归档目录: $archive"
Write-Host ''

$main = Get-Process Main -ErrorAction SilentlyContinue
& py -3 -I tools\framework\tools\doctor.py
Write-Host ''

if ($PromptTest) {
  $a = Read-Host 'test (y/N)'
  Write-Host ("ANS=[" + $a + "] type=" + $(if ($null -eq $a) { 'null' } else { $a.GetType().Name }))
  exit 0
}

$doc = $null
try {
  $doc = Get-Content 'tools\framework\logs\doctor.json' -Raw -Encoding UTF8 | ConvertFrom-Json
} catch { }

if ($doc) {
  if ($CheckGuard) {
    Write-Host ("DEBUG nonempty=" + $doc.table_nonempty_edits + " data_present=" + ($null -ne $doc.windows.data) + " force=" + $Force)
    exit 0
  }
  if ($main -and -not $doc.windows.data) {
    Write-Host '[提示] 客户端进程在运行，但数据表窗口不在。请先在主窗点“结束操作”或关闭客户端，再重新双击本程序。' -ForegroundColor Yellow
    Read-Host '按回车关闭'
    exit 2
  }
  if (-not $Force -and $doc.table_nonempty_edits -gt 0) {
    Write-Host ("[提示] 数据表已有 {0} 个非空字段（可能已提交或填过）。继续会重新填写并提交。" -f $doc.table_nonempty_edits) -ForegroundColor Yellow
    $ans = Read-Host '继续？(y/N)'
    if ([string]$ans -notmatch '^[Yy]') { exit 0 }
  }
}

if ($main) {
  Write-Host '[1/2] 检测到客户端已运行，复用当前会话...' -ForegroundColor Yellow
  $runArgs = @('-3','-I','tools\framework\tools\run_all.py','--archive',$archive)
  if ($NoSubmit) { $runArgs += '--no-submit' }
  & py @runArgs
} else {
  Write-Host '[1/2] 客户端未运行，自动启动实验...' -ForegroundColor Yellow
  $runArgs = @('-3','-I','tools\framework\tools\run_all.py','--start','--archive',$archive)
  if ($NoSubmit) { $runArgs += '--no-submit' }
  & py @runArgs
}
$code = $LASTEXITCODE

if ($code -ne 0) {
  Write-Host ''
  Write-Host '[失败] 未提交。请查看:' -ForegroundColor Red
  Write-Host "  $archive\manifest.json"
  Write-Host "  $archive\shots\"
  Read-Host '按回车关闭'
  exit $code
}

$export = Join-Path $archive 'export'
Write-Host ''
Write-Host '[2/2] 完成。导出文件:' -ForegroundColor Green
Write-Host "  $export\round_data.xlsx"
Write-Host "  $export\report.html"
Write-Host ''
$report = Join-Path (Get-Location).Path (Join-Path $export 'report.html')
$exportFull = Join-Path (Get-Location).Path $export
if (Test-Path $report) { Start-Process $report }
if (Test-Path $exportFull) { Start-Process explorer.exe $exportFull }
Read-Host '按回车关闭'
exit 0
