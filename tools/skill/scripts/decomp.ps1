param([string]$Dll, [string]$Out, [string]$Type = '', [switch]$List, [switch]$Each)
$ErrorActionPreference = 'Stop'
$lib = '<local-research>\decomp\lib'
foreach ($n in @('System.Runtime.CompilerServices.Unsafe','System.Buffers','System.Numerics.Vectors','System.Memory','System.Threading.Tasks.Extensions','System.Collections.Immutable','System.Reflection.Metadata','ICSharpCode.Decompiler')) {
  [System.Reflection.Assembly]::LoadFrom((Join-Path $lib ($n + '.dll'))) | Out-Null
}
$settings = New-Object ICSharpCode.Decompiler.DecompilerSettings
$dec = New-Object ICSharpCode.Decompiler.CSharp.CSharpDecompiler($Dll, $settings)
$all = [ICSharpCode.Decompiler.TypeSystem.TypeSystemExtensions]::GetAllTypeDefinitions($dec.TypeSystem)
if ($List) {
  $names = @($all | ForEach-Object { $_.FullName })
  [System.IO.File]::WriteAllLines($Out, $names, [System.Text.Encoding]::UTF8)
  Write-Output ("TYPES=" + $names.Count)
} elseif ($Type) {
  $tn = New-Object ICSharpCode.Decompiler.TypeSystem.FullTypeName($Type)
  $code = $dec.DecompileTypeAsString($tn)
  [System.IO.File]::WriteAllText($Out, $code, [System.Text.Encoding]::UTF8)
  Write-Output ("WROTE type " + $Type + " chars=" + $code.Length)
} elseif ($Each) {
  $sb = New-Object System.Text.StringBuilder
  $ok = 0; $fail = 0
  foreach ($t in $all) {
    try {
      $code = $dec.DecompileTypeAsString($t.FullTypeName)
      [void]$sb.AppendLine('// ===== ' + $t.FullName + ' =====')
      [void]$sb.AppendLine($code)
      $ok++
    } catch { [void]$sb.AppendLine('// FAIL ' + $t.FullName + ' : ' + $_.Exception.Message); $fail++ }
  }
  [System.IO.File]::WriteAllText($Out, $sb.ToString(), [System.Text.Encoding]::UTF8)
  Write-Output ("EACH ok=" + $ok + " fail=" + $fail + " chars=" + $sb.Length)
} else {
  $code = $dec.DecompileWholeModuleAsString()
  [System.IO.File]::WriteAllText($Out, $code, [System.Text.Encoding]::UTF8)
  Write-Output ("WROTE module chars=" + $code.Length)
}
