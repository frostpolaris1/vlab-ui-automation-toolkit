param([int]$Pid_)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $Pid_)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
$sb = New-Object System.Text.StringBuilder
foreach ($w in $wins) {
  $all = $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
  foreach ($e in $all) {
    $aid = $e.Current.AutomationId
    if ($aid -match '^(ValueText|ValueText2|MessageText)$') {
      [void]$sb.AppendLine($aid + ' = [' + $e.Current.Name + ']')
    }
  }
}
[System.IO.File]::WriteAllText('<local-research>\vals.txt', $sb.ToString(), [System.Text.Encoding]::UTF8)
Write-Output $sb.ToString()
