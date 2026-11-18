param(
    [Parameter(Mandatory=$true)][string]$BinPath,
    [Parameter(Mandatory=$true)][string]$OutPath,
    [string]$DllDir = "<local-research>\lab_pkg"
)

$ErrorActionPreference = "Stop"

$common = Join-Path $DllDir "3USTCORi.SimExp.Common.dll"
if (!(Test-Path $common)) { $common = Join-Path $DllDir "USTCORi.SimExp.Common.dll" }
$component = Join-Path $DllDir "3USTCORi.SimExp.Instruments.Component.dll"
if (!(Test-Path $component)) { $component = Join-Path $DllDir "USTCORi.SimExp.Instruments.Component.dll" }
if (!(Test-Path $common)) { throw "missing Common.dll under $DllDir" }
if (!(Test-Path $component)) { throw "missing Component.dll under $DllDir" }

[Reflection.Assembly]::LoadFrom($common) | Out-Null
$a = [Reflection.Assembly]::LoadFrom($component)
$t = $a.GetType("LitJson.JsonReader")
if ($t -eq $null) { throw "LitJson.JsonReader not found" }
$m = $t.GetMethod("Read", [type[]]@([byte[]], [string]))
if ($m -eq $null) { throw "Read(byte[],string) not found" }

$bytes = [IO.File]::ReadAllBytes($BinPath)
$plain = $m.Invoke($null, @($bytes, "<CLIENT_DECRYPT_KEY>"))
$text = [Text.Encoding]::UTF8.GetString($plain)
[IO.File]::WriteAllText($OutPath, $text, [Text.UTF8Encoding]::new($false))
Write-Output ("OK " + $OutPath + " chars=" + $text.Length)
