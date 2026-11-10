<#
.SYNOPSIS
  Extract README stills from recorded runs again (or for a run whose extraction failed).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File stills.ps1 harbor-run                          # every valid run without stills
  powershell -ExecutionPolicy Bypass -File stills.ps1 <game> -RunId <run id> -Force

  Valid = validation.json status ok or warn and no INVALID file. Writes <run>\stills\NN.jpg and
  recordings\<game>\_stills\<run_id>_NN.jpg, adds `stills` to metadata.json and the files to manifest.json.
  CPU decode only (no GPU slot needed).
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [string[]]$RunId,
    [int]$Count = 8,
    [switch]$Force
)
. (Join-Path $PSScriptRoot 'common.ps1')
$RunId = @($RunId | ForEach-Object { $_ -split ',' } | Where-Object { $_ })   # "a,b" from powershell -File arrives as one string
$root = Join-Path $RecordingsRoot $Game
$dirs = @(Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '_*' -and (-not $RunId -or $_.Name -in $RunId) })
foreach ($d in $dirs) {
    $v = Read-JsonFile (Join-Path $d.FullName 'validation.json')
    if (-not $v -or $v.status -notin @('ok', 'warn') -or (Test-Path (Join-Path $d.FullName 'INVALID'))) { continue }
    if (-not $Force -and (Test-Path (Join-Path $d.FullName 'stills\01.jpg'))) { continue }
    # a new set replaces the old one whole (a smaller -Count leaves no stale files behind)
    if (Test-Path (Join-Path $d.FullName 'stills')) { Remove-Item -Recurse -Force (Join-Path $d.FullName 'stills') }
    $s = Export-RunStills $d.FullName $d.Name (Join-Path $root '_stills') $Count
    if ($s.error) { Write-Step "$($d.Name): WARNING stills not extracted: $($s.error)"; continue }
    $mPath = Join-Path $d.FullName 'metadata.json'
    $m = Read-JsonFile $mPath
    if ($m) { $m | Add-Member -Force NoteProperty stills $s; Write-JsonFile $mPath $m }
    # Refresh the manifest entries for metadata.json and the stills (other entries untouched).
    Update-BundleManifest $d.FullName (@('metadata.json') + @($s.files | ForEach-Object { $_.file })) 'stills/'
    Write-Step "$($d.Name): $($s.count) stills"
}
