param([int]$Hwnd, [string]$Points, [int]$Dwell = 800)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class Dpi{[DllImport("user32.dll")]public static extern bool SetProcessDpiAwarenessContext(IntPtr c);[DllImport("user32.dll")]public static extern bool SetCursorPos(int x,int y);[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);}'
[Dpi]::SetProcessDpiAwarenessContext([IntPtr](-4)) | Out-Null
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
[Dpi]::SetForegroundWindow([IntPtr]$Hwnd) | Out-Null
Start-Sleep -Milliseconds 600
$el = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Hwnd)
$root = [System.Windows.Automation.AutomationElement]::RootElement
$pidOf = $el.Current.ProcessId
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $pidOf)
foreach ($p in $Points.Split(';')) {
  $f = $p.Split(',')
  $x = [int]$f[0]; $y = [int]$f[1]; $label = $f[2]
  [Dpi]::SetCursorPos($x, $y) | Out-Null
  Start-Sleep -Milliseconds $Dwell
  $wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
  $tips = @()
  foreach ($w in $wins) {
    $all = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
    foreach ($e in $all) {
      $n = $e.Current.Name
      if ($n -match '旋转|按下|棘轮|锁|夹持|松开') { $tips += $n }
    }
  }
  $uniq = $tips | Select-Object -Unique
  Write-Output ("(" + $x + "," + $y + ") " + $label + " => " + ($(if ($uniq) { $uniq -join ' | ' } else { '<no tooltip>' })))
}
