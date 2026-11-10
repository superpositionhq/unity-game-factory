<#
.SYNOPSIS
  Check one AutoPlay outputDir against docs/autoplay-contract.md (no video needed). For game sessions testing by hand.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File validate-run.ps1 C:\Users\<you>\UnityWork\games\harbor-run\Logs\autoplay\run1
  (the folder given to the player with -outputDir; without one the drop-in writes to <persistentDataPath>\AutoPlay\<timestamp>)
#>
param([Parameter(Mandatory = $true, Position = 0)][string]$Dir)

. (Join-Path $PSScriptRoot 'common.ps1')
Add-Type -AssemblyName System.Web.Extensions
$ser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
$ser.MaxJsonLength = 64MB
$problems = New-Object System.Collections.ArrayList
$notes = New-Object System.Collections.ArrayList

function Read-Rows([string]$Name, [string]$KindField) {
    $path = Join-Path $Dir $Name
    $r = @{ rows = 0; bad = 0; backwards = 0; kinds = @{}; first = $null }
    if (-not (Test-Path $path)) { [void]$problems.Add("missing $Name"); return $r }
    $prev = 0
    foreach ($line in [System.IO.File]::ReadLines($path)) {
        if ($line.Trim() -eq '') { continue }
        $r.rows++
        try { $o = $ser.DeserializeObject($line) } catch { $r.bad++; continue }
        if ($o -isnot [System.Collections.IDictionary]) { $r.bad++; continue }
        if ($null -eq $r.first) { $r.first = $o }
        $stamped = $true
        foreach ($f in 't_ns', 'qpc', 'frame') { if (-not $o.ContainsKey($f)) { [void]$problems.Add("${Name} row $($r.rows) has no $f"); $stamped = $false; break } }
        if ($stamped) {
            if ([long]$o['t_ns'] -lt $prev) { $r.backwards++ }
            $prev = [long]$o['t_ns']
        }
        $k = "$(if ($o.ContainsKey($KindField)) { $o[$KindField] })"
        if ($r.kinds.ContainsKey($k)) { $r.kinds[$k]++ } else { $r.kinds[$k] = 1 }
    }
    if ($r.bad) { [void]$problems.Add("$Name has $($r.bad) unparseable lines") }
    if ($r.backwards) { [void]$problems.Add("$Name t_ns goes backwards $($r.backwards) times") }
    return $r
}

$inputs = Read-Rows 'inputs.jsonl' 'type'
$telemetry = Read-Rows 'telemetry.jsonl' 'event'
if (-not $inputs.kinds.ContainsKey('inject')) { [void]$problems.Add('inputs.jsonl has no inject rows') }
foreach ($e in 'run_start', 'scenario_start', 'scenario_end', 'run_end') { if (-not $telemetry.kinds.ContainsKey($e)) { [void]$problems.Add("telemetry.jsonl has no $e") } }
foreach ($e in 'score', 'state') { if (-not $telemetry.kinds.ContainsKey($e)) { [void]$notes.Add("telemetry has no '$e' events (required for all games)") } }

$outcome = $null
try { $outcome = Read-JsonFile (Join-Path $Dir 'outcome.json') } catch { [void]$problems.Add("outcome.json is not JSON: $($_.Exception.Message)") }
if ($outcome) { [void]$notes.Add("AutoPlay drop-in version $(Get-Prop $outcome 'autoplay_version'), engine $(Get-Prop $outcome 'engine'), schema $(Get-Prop $outcome 'schema')") }
if (-not $outcome) { if (-not (Test-Path (Join-Path $Dir 'outcome.json'))) { [void]$problems.Add('missing outcome.json') } }
else {
    if ((Get-Prop $outcome 'result') -notin @('win', 'lose', 'timeout', 'abort')) { [void]$problems.Add("outcome.result is '$(Get-Prop $outcome 'result')'") }
    if (Get-Prop $outcome 'go_timed_out') { [void]$notes.Add('go_timed_out is true (expected when testing by hand with -goTimeout 0)') }
    $dur = Get-Prop $outcome 'duration_s'
    if ($dur -and [double]$dur -gt 0) { [void]$notes.Add(("scenario {5} ({6}) ran {0:N1} s at {1:N1} fps, {2} injected inputs, result {3}, score {4}" -f [double]$dur, ([double](Get-Prop $outcome 'frames') / [double]$dur), (Get-Prop $outcome 'inputs_injected'), (Get-Prop $outcome 'result'), (Get-Prop $outcome 'score'), (Get-Prop $outcome 'scenario'), (Get-Prop $outcome 'scenario_name'))) }
}
$clock = $null
try { $clock = Read-JsonFile (Join-Path $Dir 'clock.json') } catch { [void]$problems.Add("clock.json is not JSON: $($_.Exception.Message)") }
if (-not $clock) { if (-not (Test-Path (Join-Path $Dir 'clock.json'))) { [void]$problems.Add('missing clock.json') } }
else {
    $labels = @(@(Get-Prop $clock 'samples') | Where-Object { $_ } | ForEach-Object { $_.label })
    foreach ($l in 'start', 'go', 'audio_start', 'audio_stop', 'end') { if ($l -notin $labels) { [void]$problems.Add("clock.json has no '$l' sample") } }
}
$wav = Join-Path $Dir 'audio.wav'
if (-not (Test-Path $wav)) { [void]$problems.Add('missing audio.wav') }
else {
    $ffmpeg = Find-FFmpeg
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $vol = & $ffmpeg -hide_banner -nostats -i $wav -af volumedetect -f null - 2>&1 | ForEach-Object { "$_" }
    $ErrorActionPreference = $eap
    $max = $vol | Select-String 'max_volume: (\S+) dB' | Select-Object -First 1
    $dur = $vol | Select-String 'Duration: (\d+):(\d+):([\d\.]+)' | Select-Object -First 1
    if ($dur) { $s = [int]$dur.Matches[0].Groups[1].Value * 3600 + [int]$dur.Matches[0].Groups[2].Value * 60 + [double]::Parse($dur.Matches[0].Groups[3].Value, $Inv); [void]$notes.Add(("audio.wav {0:N1} s, max volume {1} dB" -f $s, $(if ($max) { $max.Matches[0].Groups[1].Value } else { '?' }))) }
    else { [void]$problems.Add('audio.wav has no duration (not finalised)') }
    $clockFile = Join-Path $Dir 'audio_clock.jsonl'
    if (Test-Path $clockFile) {
        # per-buffer audio clock: the WAV must span first buffer -> last buffer on the wall clock
        $rows = @(foreach ($l in [System.IO.File]::ReadLines($clockFile)) { if ($l -match '"frame":(\d+),"frames":(\d+),"qpc":\d+,"t_ns":(\d+),"silence_before":(\d+),.*"rate":(\d+)') { [pscustomobject]@{ f = [long]$matches[1]; n = [long]$matches[2]; t = [long]$matches[3]; s = [long]$matches[4]; r = [double]$matches[5] } } })
        if ($rows.Count -eq 0) { [void]$problems.Add('audio_clock.jsonl has no rows') }
        else {
            $r0 = $rows[0]
            # where each row puts the WAV's frame 0 (t_ns - frame / rate); the drift is each row's distance from their
            # median (the first buffers arrive in a burst, so the first row is no anchor)
            $offs = @($rows | ForEach-Object { [double]$_.t - [double]$_.f / $_.r * 1e9 } | Sort-Object)
            $mid = $offs[[int][math]::Floor(($offs.Count - 1) / 2)]
            $maxDrift = 0.0; foreach ($r in $rows) { $d = [math]::Abs(([double]$r.t - [double]$r.f / $r.r * 1e9 - $mid) / 1e6); if ($d -gt $maxDrift) { $maxDrift = $d } }
            $gapsN = @($rows | Where-Object { $_.s -gt 0 }).Count; $silS = (($rows | ForEach-Object { $_.s }) | Measure-Object -Sum).Sum / $r0.r
            [void]$notes.Add(("audio_clock: {0} buffers, {1} stalls filled ({2:N2} s silence), max drift {3:N0} ms" -f $rows.Count, $gapsN, $silS, $maxDrift))
            if ($maxDrift -gt 250) { [void]$problems.Add("audio_clock drift up to $([math]::Round($maxDrift)) ms: system_audio would be unaligned") }
        }
    } else { [void]$problems.Add('missing audio_clock.jsonl (the WAV cannot be aligned with the video)') }
    if (-not $max -or $max.Matches[0].Groups[1].Value -eq '-inf' -or [double]::Parse($max.Matches[0].Groups[1].Value, $Inv) -lt -60) { [void]$notes.Add('audio.wav is silent: check that the game plays sounds and that its AudioListener is active') }
}

[void]$notes.Add("inputs: $($inputs.rows) rows $(($inputs.kinds.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')")
[void]$notes.Add("telemetry: $($telemetry.rows) rows $(($telemetry.kinds.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')")
$status = if ($problems.Count) { 'FAIL' } else { 'PASS' }
Write-Host "$status $Dir"
foreach ($p in $problems) { Write-Host "  problem: $p" }
foreach ($n in $notes) { Write-Host "  note: $n" }
if ($problems.Count) { exit 1 }
