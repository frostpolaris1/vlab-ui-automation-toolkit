# Dump a WPF BAML resource as a flat XAML node stream (read-only).
param(
  [Parameter(Mandatory=$true)][string]$DllPath,
  [Parameter(Mandatory=$true)][string]$BamlName,
  [Parameter(Mandatory=$true)][string]$OutPath
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$asm = [System.Reflection.Assembly]::LoadFrom($DllPath)
# preload sibling assemblies so BAML type resolution succeeds
$dir = Split-Path -Parent $DllPath
Get-ChildItem -Path $dir -Filter *.dll | ForEach-Object {
  try { [void][System.Reflection.Assembly]::LoadFrom($_.FullName) } catch {}
}
$resName = $asm.GetName().Name + '.g.resources'
$s = $asm.GetManifestResourceStream($resName)
$rr = New-Object System.Resources.ResourceReader($s)
$bamlStream = $null
foreach ($entry in $rr.GetEnumerator()) {
  if ($entry.Key -ieq $BamlName) { $bamlStream = $entry.Value; break }
}
if (-not $bamlStream) { throw "baml not found: $BamlName" }

$pfAsm = [System.Windows.Markup.XamlWriter].Assembly
$tReader = $pfAsm.GetType('System.Windows.Baml2006.Baml2006Reader')
$flags = [System.Reflection.BindingFlags]'Instance,Public,NonPublic'
$ctor = $tReader.GetConstructor($flags, $null, [Type[]]@([System.IO.Stream]), $null)
if (-not $ctor) { $ctor = $tReader.GetConstructors($flags) | Select-Object -First 1 }
$reader = $ctor.Invoke(@($bamlStream))

$sb = New-Object System.Text.StringBuilder
while ($reader.Read()) {
  $nt = $reader.NodeType
  $parts = @([string]$nt)
  try { if ($reader.Depth -ne $null) { $parts += ('d=' + $reader.Depth) } } catch {}
  try { if ($reader.Type) { $parts += ('type=' + $reader.Type.Name) } } catch {}
  try { if ($reader.Member) { $parts += ('member=' + $reader.Member.Name) } } catch {}
  try {
    $v = $reader.Value
    if ($v -ne $null) {
      $tn = $v.GetType().FullName
      $vs = [string]$v
      if ($vs.Length -gt 120) { $vs = $vs.Substring(0,120) + '...' }
      $extra = ''
      if ($tn -like 'System.Windows.Baml2006.*') {
        $bf = [System.Reflection.BindingFlags]'Instance,Public,NonPublic'
        foreach ($f in $v.GetType().GetFields($bf)) {
          try {
            $fv = $f.GetValue($v)
            if ($fv -ne $null -and ($fv -is [string] -or $fv -is [ValueType])) {
              $extra += ' [' + $f.Name + '=' + [string]$fv + ']'
            }
          } catch {}
        }
      }
      $parts += ('value=' + $vs + $extra)
    }
  } catch {}
  [void]$sb.AppendLine(($parts -join ' | '))
}
[System.IO.File]::WriteAllText($OutPath, $sb.ToString(), [System.Text.Encoding]::UTF8)
Write-Output ("WROTE " + $OutPath + " chars=" + $sb.Length)
