param(
  [Parameter(Mandatory=$true)][int]$Pid_,
  [Parameter(Mandatory=$true)][string]$JsonPath,
  [Parameter(Mandatory=$true)][string]$DataTitle
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# JSON: { "<edit-index>": "<value>", ... } (document order of Edit descendants)
$map = Get-Content $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json

$root = [System.Windows.Automation.AutomationElement]::RootElement
$pidCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $Pid_)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $pidCond)
$dataWin = $null
foreach ($w in $wins) {
  if ($w.Current.Name -eq $DataTitle) { $dataWin = $w; break }
}
if (-not $dataWin) { Write-Output 'ERROR: data window not found'; exit 1 }

$editCond = New-Object System.Windows.Automation.PropertyCondition(
  [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
  [System.Windows.Automation.ControlType]::Edit)
$edits = $dataWin.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editCond)

$set = 0; $bad = 0; $oof = 0
foreach ($prop in $map.PSObject.Properties) {
  $i = [int]$prop.Name
  if ($i -lt 0 -or $i -ge $edits.Count) { $oof++; continue }
  $want = [string]$prop.Value
  $vp = $edits[$i].GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
  $vp.SetValue($want)
  if ($vp.Current.Value -ne $want) { $bad++ }
  $set++
}
Write-Output ("EDITS=" + $edits.Count + " SET=" + $set + " BAD=" + $bad + " OUT_OF_RANGE=" + $oof)
if ($bad -gt 0 -or $oof -gt 0) { exit 4 }
exit 0
