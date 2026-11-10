<#
.SYNOPSIS
  Queue a pipeline run for a game and return at once (the coordinator queues; game sessions never do). A hidden drainer
  process works through the queue one request at a time; results land in builds\_queue\done\ and
  .recording\<game>\pipeline.jsonl.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File %UGF_ROOT%\unity-game-factory\tools\unity-pipeline\enqueue.ps1 harbor-run -Scenarios 1 -Runs 1 -RequestedBy coordinator
  ... -Commit HEAD -MaxSeconds "1=300,2=600,3=900"   # per-scenario AutoPlay time limit (s); a plain number applies to
                                                     # every scenario; unlisted scenarios keep the default 600
  ... -Backend mono                                  # a release player without IL2CPP (no C++ tools on this machine)
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [int]$Runs = 1,
    [string[]]$Scenarios,   # "1,2" from powershell -File arrives as one string
    [string]$Commit = 'HEAD',
    [string]$RequestedBy = 'unknown',
    [string]$MaxSeconds,   # "900" or "1=300,3=900" (see pipeline.ps1 -MaxSeconds)
    [ValidateSet('', 'il2cpp', 'mono')][string]$Backend = '',
    [switch]$Force   # queue anyway although the requester is not the coordinator
)

. (Join-Path $PSScriptRoot 'common.ps1')
# The coordinator owns the queue (user's decision: one GPU recording at a time, in the order the coordinator sets).
if ($RequestedBy -ne 'coordinator' -and -not $Force) {
    Write-Host ''
    Write-Host '!!! NOT QUEUED: only the coordinator queues recordings (-RequestedBy coordinator).' -ForegroundColor Red
    Write-Host "!!! Ask the coordinating session to queue $Game (commit $Commit, scenarios $($Scenarios -join ','), runs $Runs)." -ForegroundColor Red
    Write-Host '!!! (-Force queues anyway; it is logged with your -RequestedBy.)' -ForegroundColor Red
    exit 2
}
$info = Get-GameInfo $Game
$maxMap = ConvertTo-MaxSecondsMap $MaxSeconds   # validates now, so a typo fails here and not in the drainer
$sha = (Invoke-Git $info.Dir @('rev-parse', '--verify', "$Commit^{commit}")).Trim()   # pin the commit now
$queue = Join-Path $BuildsRoot '_queue'
New-Item -ItemType Directory -Force $queue | Out-Null
$name = '{0}-{1}-{2}.json' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'), $Game, $sha.Substring(0, 8)
$req = [ordered]@{ game = $Game; commit = $sha; runs = $Runs; scenarios = @($Scenarios | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { [int]$_ }); requested_by = $RequestedBy; requested_at = (Get-IsoNow) }
if ($MaxSeconds) { $req.max_seconds = $maxMap }
if ($Backend) { $req.backend = $Backend }
Write-JsonFile (Join-Path $queue $name) $req

if (Test-Path (Join-Path $queue '_paused.txt')) {
    Write-Step "queued $name, but the queue is PAUSED ($((Get-Content (Join-Path $queue '_paused.txt') -TotalCount 1))); it starts when _paused.txt is removed and a drainer runs"
    exit 0
}
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    "`"$(Join-Path $PSScriptRoot 'pipeline.ps1')`"", '-DrainQueue')
Write-Step "queued $name (builds\_queue); results: .recording\$Game\pipeline.jsonl and builds\_queue\done\$name"
