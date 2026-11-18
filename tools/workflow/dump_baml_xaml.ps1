# Dump a WPF BAML resource to XAML (read-only, runs in a separate process).
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
$resName = $asm.GetName().Name + '.g.resources'
$s = $asm.GetManifestResourceStream($resName)
if (-not $s) { throw "g.resources not found: $resName" }
$rr = New-Object System.Resources.ResourceReader($s)
$bamlStream = $null
foreach ($entry in $rr.GetEnumerator()) {
  if ($entry.Key -ieq $BamlName) { $bamlStream = $entry.Value; break }
}
if (-not $bamlStream) { throw "baml not found: $BamlName" }

$pfAsm = [System.Windows.Markup.XamlWriter].Assembly
$tReader = $pfAsm.GetType('System.Windows.Baml2006.Baml2006Reader')
if (-not $tReader) { throw 'Baml2006Reader type not found' }
$flags = [System.Reflection.BindingFlags]'Instance,Public,NonPublic'
$ctor = $tReader.GetConstructor($flags, $null, [Type[]]@([System.IO.Stream]), $null)
if (-not $ctor) {
  $ctor = $tReader.GetConstructors($flags) | Select-Object -First 1
}
$reader = $ctor.Invoke(@($bamlStream))
$schema = New-Object System.Xaml.XamlSchemaContext
$writer = New-Object System.Xaml.XamlObjectWriter($schema)
while ($reader.Read()) { $writer.WriteNode($reader) }
$root = $writer.Result
$text = [System.Windows.Markup.XamlWriter]::Save($root)
[System.IO.File]::WriteAllText($OutPath, $text, [System.Text.Encoding]::UTF8)
Write-Output ("WROTE " + $OutPath + " chars=" + $text.Length)
