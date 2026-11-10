<#
.SYNOPSIS
  Queue runner: release build -> record N runs per scenario -> validate. See docs/unity-pipeline.md.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File pipeline.ps1 harbor-run -Runs 1             # scenarios from the milestone tag
  powershell -ExecutionPolicy Bypass -File pipeline.ps1 harbor-run -Scenarios 1,2 -Commit HEAD
  powershell -ExecutionPolicy Bypass -File pipeline.ps1 -DrainQueue                    # requests written by enqueue.ps1

  Scenarios default to 1..n where milestone/autoplay-<n> ("scenarios 1..n are ready") is the newest such tag reachable
  from the commit; the commit defaults to the game's current branch tip (HEAD). Without -Force, scenarios that already
  have -Runs good runs (status ok/warn) of that commit are skipped. One summary row per invocation and game in
  .recording\<game>\pipeline.jsonl.
#>
param(
    [Parameter(Position = 0)][string]$Game,
    [int]$Runs = 1,
    [string[]]$Scenarios,   # "1,2" from powershell -File arrives as one string; split below
    [string]$Commit = 'HEAD',
    [string]$MaxSeconds = '600',   # AutoPlay time limit per run (s): "900" for every scenario, or "1=300,3=900" (others 600)
    [ValidateSet('', 'il2cpp', 'mono')][string]$Backend = '',   # '': the release default (IL2CPP); mono where IL2CPP's C++ tools are missing
    [switch]$Force,
    [switch]$DrainQueue
)

. (Join-Path $PSScriptRoot 'common.ps1')
$QueueDir = Join-Path $BuildsRoot '_queue'
if ($DrainQueue) {
    # Unattended: keep a transcript (the hidden drainer has no console anyone reads).
    $logs = Join-Path $BuildsRoot '_logs'
    New-Item -ItemType Directory -Force $logs | Out-Null
    Start-Transcript -Path (Join-Path $logs ('queue-{0}.log' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))) | Out-Null
}

function Get-MilestoneScenarios([string]$Dir, [string]$Rev) {
    $tag = Invoke-Git $Dir @('describe', '--tags', '--abbrev=0', '--match', 'milestone/autoplay-*', $Rev) -AllowFail
    if ($LASTEXITCODE -ne 0 -or -not $tag) { return $null }
    $tag = "$tag".Trim()
    if ($tag -match 'milestone/autoplay-(\d+)$') { return [pscustomobject]@{ Tag = $tag; Scenarios = @(1..[int]$matches[1]) } }
    return $null
}

function Get-GoodRunCount([string]$GameSlug, [string]$Sha, [int]$Scenario) {
    $path = Join-Path (Join-Path $LogRoot $GameSlug) 'runs.jsonl'
    if (-not (Test-Path $path)) { return 0 }
    # runs.jsonl also holds event rows (mark-invalid.ps1: event "invalidated", no build_commit); invalidated runs don't count.
    $rows = @(foreach ($line in [System.IO.File]::ReadLines($path)) { try { $line | ConvertFrom-Json } catch { } })
    $invalid = @($rows | Where-Object { (Get-Prop $_ 'event') -eq 'invalidated' } | ForEach-Object { $_.run_id })
    $n = 0
    foreach ($r in $rows) {
        if ($null -eq (Get-Prop $r 'build_commit') -or $null -eq (Get-Prop $r 'status')) { continue }
        if ((Get-Prop $r 'run_id') -in $invalid) { continue }
        if ($r.build_commit -eq $Sha -and (Get-Prop $r 'scenario') -eq $Scenario -and $r.status -in @('ok', 'warn')) { $n++ }
    }
    return $n
}

function Test-SessionLocked {
    # Desktop Duplication cannot see a locked (secure) desktop; LogonUI runs while the session is locked.
    return [bool](Get-Process LogonUI -ErrorAction SilentlyContinue)
}

function Invoke-GamePipeline([string]$GameSlug, [int]$RunCount, [int[]]$ScenarioList, [string]$Rev, [string]$Trigger, $MaxMap = (ConvertTo-MaxSecondsMap $MaxSeconds), [string]$BuildBackend = $Backend) {
    $info = Get-GameInfo $GameSlug
    $t0 = Get-Date
    $summary = [ordered]@{
        schema = 'unity-pipeline/v1'; game = $GameSlug; trigger = $Trigger; requested = $Rev
        start = $t0.ToString('o'); status = 'ok'; note = ''; build = $null; scenarios = @(); runs = @()
    }
    try {
        $sha = (Invoke-Git $info.Dir @('rev-parse', '--verify', "$Rev^{commit}")).Trim()
        $summary.commit = $sha
        if (-not $ScenarioList -or $ScenarioList.Count -eq 0) {
            $m = Get-MilestoneScenarios $info.Dir $sha
            if (-not $m) { $summary.status = 'skipped'; $summary.note = 'no milestone/autoplay-* tag reachable'; return $summary }
            $ScenarioList = $m.Scenarios; $summary.milestone = $m.Tag
        }
        $summary.scenarios = $ScenarioList
        $summary.max_seconds = [ordered]@{}; foreach ($l in $ScenarioList) { $summary.max_seconds["$l"] = Get-MaxSeconds $MaxMap $l }
        $todo = @(foreach ($l in $ScenarioList) {
            $have = if ($Force) { 0 } else { Get-GoodRunCount $GameSlug $sha $l }
            if ($have -lt $RunCount) { [pscustomobject]@{ Scenario = $l; Runs = $RunCount - $have } }
        })
        if ($todo.Count -eq 0) { $summary.status = 'skipped'; $summary.note = "every scenario already has $RunCount good runs of $($sha.Substring(0, 8))"; return $summary }

        Write-Step "== $GameSlug $($sha.Substring(0, 8)): release build"
        $build = if ($BuildBackend) { & (Join-Path $PSScriptRoot 'build.ps1') $GameSlug -Commit $sha -Backend $BuildBackend | Select-Object -Last 1 }
                 else { & (Join-Path $PSScriptRoot 'build.ps1') $GameSlug -Commit $sha | Select-Object -Last 1 }
        $summary.build = [ordered]@{ status = (Get-Prop $build 'status'); short_sha = (Get-Prop $build 'short_sha'); output = (Get-Prop $build 'output_path'); backend = (Get-Prop $build 'backend'); autoplay_version = (Get-Prop $build 'autoplay_version') }
        # Leak-scan hits (user name in paths, forbidden names) in the job summary, so they show without builds.jsonl.
        # Warn-only here; the packager is the gate. $build is the fresh row (ordered dictionary) or a reused
        # build_info.json (PSCustomObject).
        # (assigned in two steps: an if-expression turns an empty list into null, and [] means a clean scan)
        $ls = Get-Prop $build 'leak_scan'
        $hits = $null
        if ($null -ne $ls) { $hits = @(Get-Prop $ls 'hits' | Where-Object { $_ } | ForEach-Object { [ordered]@{ file = (Get-Prop $_ 'file'); pattern = (Get-Prop $_ 'pattern'); count = (Get-Prop $_ 'count'); example = (Get-Prop $_ 'example') } }) }
        $summary.build.leak_scan_hits = $hits
        if ((Get-Prop $build 'status') -ne 'ok') { $summary.status = 'failed'; $summary.note = "build failed: $(Get-Prop $build 'error_excerpt')"; return $summary }

        foreach ($t in $todo) {
            if (Test-SessionLocked) { $summary.status = 'failed'; $summary.note = 'session locked: capture impossible'; break }
            Write-Step "== $GameSlug scenario $($t.Scenario): $($t.Runs) runs"
            $rows = & (Join-Path $PSScriptRoot 'record.ps1') $GameSlug -Build $build.output_path -Scenario $t.Scenario -Runs $t.Runs -MaxSeconds (Get-MaxSeconds $MaxMap $t.Scenario)
            foreach ($r in @($rows | Where-Object { $_ -and $null -ne (Get-Prop $_ 'run_id') })) {
                $summary.runs += [ordered]@{ run_id = $r.run_id; scenario = $r.scenario; status = $r.status; result = $r.result }
            }
        }
        if (@($summary.runs | Where-Object { $_.status -eq 'failed' }).Count -gt 0 -and $summary.status -eq 'ok') { $summary.status = 'partial' }
    } catch {
        $summary.status = 'failed'; $summary.note = $_.Exception.Message
    } finally {
        $summary.end = (Get-Date).ToString('o')
        $summary.duration_s = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
        Add-JsonLine (Join-Path $info.LogDir 'pipeline.jsonl') $summary
        Write-Step "== $GameSlug pipeline: $($summary.status) $($summary.note)"
    }
    return $summary
}

# ---------------------------------------------------------------------------------------------------------------------

if ($DrainQueue) {
    # One drainer at a time (separate from the per-game lock, which build/record take per step).
    New-Item -ItemType Directory -Force (Join-Path $QueueDir 'done') | Out-Null
    try { $drainLock = [System.IO.File]::Open((Join-Path $QueueDir '_drainer.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch [System.IO.IOException] { Write-Step 'another queue drainer is running'; return }
    # This process keeps the pipeline.ps1/common.ps1 it started with (build.ps1/record.ps1 are re-read per call): when
    # either changes, hand over to a fresh drainer between jobs instead of running stale code.
    $codeFiles = @((Join-Path $PSScriptRoot 'pipeline.ps1'), (Join-Path $PSScriptRoot 'common.ps1'))
    $codeStamp = ($codeFiles | ForEach-Object { (Get-Item $_).LastWriteTimeUtc } | Measure-Object -Maximum).Maximum
    $handOver = $false
    try {
        while ($true) {
            if ((($codeFiles | ForEach-Object { (Get-Item $_).LastWriteTimeUtc } | Measure-Object -Maximum).Maximum) -gt $codeStamp) { $handOver = $true; break }
            # Paused (builds\_queue\_paused.txt, e.g. "stop recording" from the user): start no job; queued requests wait.
            if (Test-Path (Join-Path $QueueDir '_paused.txt')) { Write-Step "queue paused ($((Get-Content (Join-Path $QueueDir '_paused.txt') -TotalCount 1)))"; break }
            $next = Get-ChildItem $QueueDir -Filter *.json -File | Where-Object { $_.Name -notlike '_*' } | Sort-Object Name | Select-Object -First 1
            if (-not $next) {
                # Queue empty: an idle-wait override (_idle-override.txt) stays (the user's standing "record now" is one),
                # unless it says "one_drain": true; that one is retired so idle waiting is the default again.
                $ov = Join-Path $QueueDir '_idle-override.txt'
                $ovData = if (Test-Path $ov) { Read-JsonFile $ov } else { $null }
                if ($ovData -and (Get-Prop $ovData 'one_drain') -eq $true) {
                    Move-Item -Force $ov (Join-Path (Join-Path $QueueDir 'done') ("_idle-override-retired-{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss')))
                    Write-Step 'queue empty: one-drain idle-wait override retired'
                }
                break
            }
            $req = Read-JsonFile $next.FullName
            # Recording priority for the whole job and the gap to the next one (see Start-RecordingWantsGpuHold).
            Start-RecordingWantsGpuHold "queue job $($next.Name)"
            $scenariosReq = if (Get-Prop $req 'scenarios') { [int[]]$req.scenarios } else { $null }
            $maxReq = if (Get-Prop $req 'max_seconds') { ConvertTo-MaxSecondsMap $req.max_seconds } else { ConvertTo-MaxSecondsMap '' }
            $backendReq = if (Get-Prop $req 'backend') { [string]$req.backend } else { '' }
            $res = Invoke-GamePipeline $req.game ([int]$req.runs) $scenariosReq $req.commit "queue:$(Get-Prop $req 'requested_by')" $maxReq $backendReq
            $req | Add-Member -NotePropertyName result -NotePropertyValue $res -Force
            Write-JsonFile (Join-Path (Join-Path $QueueDir 'done') $next.Name) $req
            Remove-Item $next.FullName
        }
    } finally {
        # On hand-over the flag stays (under a minute old); the next drainer takes it over.
        if (-not $handOver) { Stop-RecordingWantsGpuHold }
        $drainLock.Dispose()
    }
    if ($handOver) {
        Write-Step 'pipeline code changed: handing the queue over to a fresh drainer'
        Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-DrainQueue') | Out-Null
    }
    return
}

if (-not $Game) { throw 'give a game or -DrainQueue' }
$scenarioList = @($Scenarios | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { [int]$_ })
Invoke-GamePipeline $Game $Runs $scenarioList $Commit 'manual'
