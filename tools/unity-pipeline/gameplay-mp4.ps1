<#
.SYNOPSIS
  Write <run>\gameplay.mp4 (the dataset's Gameplay/ file) again, or for a run whose first try failed.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File gameplay-mp4.ps1 harbor-run -Commit ff5f1ee
  powershell -ExecutionPolicy Bypass -File gameplay-mp4.ps1 <game> -RunId <run id> -Force

  Valid = validation.json status ok or warn and no INVALID file. -Commit takes one or more build-commit prefixes
  (metadata.json build.commit). Video is stream-copied from video.mkv, system_audio.mka is encoded to AAC and aligned
  with the bundle's own clock offsets (see Export-GameplayMp4 in common.ps1). Adds `gameplay_mp4` to metadata.json and
  the file to manifest.json. CPU only, below-normal priority.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [string[]]$Commit,
    [string[]]$RunId,
    [switch]$Force
)
. (Join-Path $PSScriptRoot 'common.ps1')
Set-BelowNormalPriority
# "a,b" from powershell -File arrives as one string
$Commit = @($Commit | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$RunId = @($RunId | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$root = Join-Path $RecordingsRoot $Game
$done = 0; $failed = 0; $skipped = 0
foreach ($d in @(Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '_*' -and (-not $RunId -or $_.Name -in $RunId) } | Sort-Object Name)) {
    $v = Read-JsonFile (Join-Path $d.FullName 'validation.json')
    $m = Read-JsonFile (Join-Path $d.FullName 'metadata.json')
    if (-not $v -or -not $m -or $v.status -notin @('ok', 'warn') -or (Test-Path (Join-Path $d.FullName 'INVALID'))) { continue }
    if ($Commit -and -not @($Commit | Where-Object { "$(Get-Prop (Get-Prop $m 'build') 'commit')".StartsWith($_) }).Count) { continue }
    if (-not $Force -and (Test-Path (Join-Path $d.FullName 'gameplay.mp4'))) { $skipped++; continue }
    $sa = Get-Prop $m 'system_audio'
    $audioStart = if ($sa -and (Get-Prop $sa 'aligned') -eq $true) { Get-Prop $sa 'start_offset_ns' } else { $null }
    $r = Export-GameplayMp4 $d.FullName (Get-Prop $m 'video_start_offset_ns') $audioStart
    if ($r.error) { Write-Step "$($d.Name): WARNING gameplay.mp4 not written: $($r.error)"; $failed++; continue }
    $m | Add-Member -Force NoteProperty gameplay_mp4 $r
    Write-JsonFile (Join-Path $d.FullName 'metadata.json') $m
    Update-BundleManifest $d.FullName @('metadata.json', 'gameplay.mp4')
    Write-Step ("{0}: gameplay.mp4 {1:N1} s, {2:N1} MB, audio offset {3} s" -f $d.Name, $r.duration_s, ($r.bytes / 1MB), $r.audio_offset_s)
    $done++
}
Write-Step "$Game : $done written, $failed failed, $skipped already had one"
if ($failed) { exit 1 }
