param([int]$Pid_, [string]$Out, [int]$MaxNodes = 4000, [int]$MaxDepth = 40)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $Pid_)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
$sb = New-Object System.Text.StringBuilder
$count = 0
function Walk($el, $depth) {
  if ($script:count -ge $MaxNodes -or $depth -gt $MaxDepth) { return }
  $script:count++
  $name = $el.Current.Name
  $ct = $el.Current.ControlType.ProgrammaticName -replace 'ControlType.', ''
  $aid = $el.Current.AutomationId
  $r = $el.Current.BoundingRectangle
  $val = ''
  try {
    $vp = $el.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    if ($vp) { $val = ' VALUE=[' + $vp.Current.Value + ']' }
  } catch {}
  if (-not $val) {
    try {
      $tp = $el.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern)
      if ($tp) { $t = $tp.DocumentRange.GetText(200); $val = ' TEXT=[' + $t + ']' }
    } catch {}
  }
  $rect = ''
  if (-not $r.IsEmpty) { $rect = ' @' + [int]$r.X + ',' + [int]$r.Y + ',' + [int]$r.Width + 'x' + [int]$r.Height }
  [void]$sb.AppendLine(('  ' * $depth) + $ct + ' name=[' + $name + '] aid=[' + $aid + ']' + $val + $rect)
  $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
  $child = $walker.GetFirstChild($el)
  while ($child -ne $null -and $script:count -lt $MaxNodes) {
    Walk $child ($depth + 1)
    $child = $walker.GetNextSibling($child)
  }
}
foreach ($w in $wins) {
  [void]$sb.AppendLine('===== WINDOW name=[' + $w.Current.Name + '] hwnd=' + $w.Current.NativeWindowHandle + ' =====')
  Walk $w 0
}
[System.IO.File]::WriteAllText($Out, $sb.ToString(), [System.Text.Encoding]::UTF8)
Write-Output ("NODES=" + $count + " ms=" + $sw.ElapsedMilliseconds + " -> " + $Out)
