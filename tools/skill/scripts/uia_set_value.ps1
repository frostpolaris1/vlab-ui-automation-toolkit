param(
    [Parameter(Mandatory=$true)][int]$Pid_,
    [Parameter(Mandatory=$true)][string]$Old,
    [Parameter(Mandatory=$true)][string]$New
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $Pid_)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
$editCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Edit)

$changed = 0
foreach ($w in $wins) {
    $edits = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editCond)
    foreach ($e in $edits) {
        try {
            $vp = $e.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
            if ($vp.Current.Value -eq $Old) {
                $vp.SetValue($New)
                Write-Output ("SET [" + $Old + "] -> [" + $New + "]")
                $changed++
            }
        } catch {}
    }
}
Write-Output ("CHANGED=" + $changed)
