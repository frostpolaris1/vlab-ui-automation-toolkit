param(
  [Parameter(Mandatory=$true)][int]$Pid_,
  [Parameter(Mandatory=$true)][string]$JsonPath,
  [Parameter(Mandatory=$true)][string]$DataTitle,
  [Parameter(Mandatory=$true)][string]$HeaderLike
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# JSON: { "gb": [12 strings], "paper": [9 strings] }
$cfg = Get-Content $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
$sets = @($cfg.gb, $cfg.paper)

$root = [System.Windows.Automation.AutomationElement]::RootElement
$pidCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $Pid_)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $pidCond)
$dataWin = $null
foreach ($w in $wins) {
  if ($w.Current.Name -eq $DataTitle) { $dataWin = $w; break }
}
if (-not $dataWin) { Write-Output 'ERROR: data window not found'; exit 1 }

$trueCond = [System.Windows.Automation.Condition]::TrueCondition
$editCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
  [System.Windows.Automation.ControlType]::Edit)

$all = $dataWin.FindAll([System.Windows.Automation.TreeScope]::Descendants, $trueCond)
$headers = @()
foreach ($e in $all) {
  if ($e.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text -and
      $e.Current.Name -like ('*' + $HeaderLike + '*')) {
    $headers += $e
  }
}
if ($headers.Count -ne 2) { Write-Output ("ERROR: expected 2 B-class tables, found " + $headers.Count); exit 2 }

# GB table is above the paper table in the document
$headers = $headers | Sort-Object { $_.Current.BoundingRectangle.Y }
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker

for ($i = 0; $i -lt 2; $i++) {
  $label = if ($i -eq 0) { 'gb' } else { 'paper' }
  $parent = $walker.GetParent($headers[$i])
  $edits = $parent.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editCond)
  $vals = @($sets[$i])
  if ($edits.Count -ne $vals.Count) {
    Write-Output ("ERROR: " + $label + " cells=" + $edits.Count + " values=" + $vals.Count)
    exit 3
  }
  $bad = 0
  for ($j = 0; $j -lt $edits.Count; $j++) {
    $vp = $edits[$j].GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $want = [string]$vals[$j]
    $vp.SetValue($want)
    if ($vp.Current.Value -ne $want) { $bad++ }
  }
  if ($bad -gt 0) {
    Write-Output ("ERROR: " + $label + " readback mismatches=" + $bad)
    exit 4
  }
  Write-Output ("OK " + $label + " cells=" + $edits.Count + " readback=all")
}
exit 0
