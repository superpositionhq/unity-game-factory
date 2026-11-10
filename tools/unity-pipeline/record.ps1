<#
.SYNOPSIS
  Record AutoPlay runs of a game's release player: launch with the contract flags, capture the window with ffmpeg,
  validate, and write one gameplay bundle per run. See docs/unity-pipeline.md and docs/autoplay-contract.md.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File record.ps1 harbor-run -Build %UGF_ROOT%\builds\harbor-run\a1b2c3d4 -Scenario 1 -Runs 3
  powershell -ExecutionPolicy Bypass -File record.ps1 harbor-run -Build latest -Scenario 2 -Runs 1 -Skill 0.5 -Seed 42

  Bundle: recordings\<game>\<run-id>\ video.mkv, system_audio.mka, inputs.jsonl, telemetry.jsonl, outcome.json,
  metadata.json, validation.json, manifest.json, stills\, gameplay.mp4, raw\ (the game's outputDir, ffmpeg logs).
  Failed runs are kept and marked (validation.json status "failed", FAILED file). One row per run in
  .recording\<game>\runs.jsonl.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [Parameter(Mandatory = $true)][string]$Build,
    [int]$Scenario = 1,   # a scenario: start state + win/lose condition (a level, chapter, race stage, start setup)
    [int]$Runs = 1,
    [double]$Skill = -1,
    [long]$Seed = -1,
    [int]$MaxSeconds = 600,
    [ValidateSet('auto', 'gfxcapture', 'ddagrab', 'gdigrab-region', 'gdigrab-window')][string]$Capture = 'auto',
    [switch]$NoStablePath,
    [double]$IdleMinutes = 5,   # user's decision: record only after this long without keyboard/mouse input (0 = don't wait)
    [int]$MaxVramInUseMB = 4096,   # before launch, wait while more VRAM than this is in use by other processes (nvidia-smi total); 0: half the GPU's VRAM
    [int]$OutputIndex = 0,
    [int]$CaptureRate = 240,
    [string]$ExtraArgs = '',
    [ValidateSet(30, 60)][int]$OutputFps = 60,   # video frame rate (CFR); 30 only for a game that cannot hold 60 (note it with -CaptureNote)
    [string]$CaptureNote = ''   # what the recording does differently (e.g. a lower quality level); metadata.json capture_notes, then the dataset's manifest and README
)

. (Join-Path $PSScriptRoot 'common.ps1')
if ($MaxVramInUseMB -le 0) { $vt = Get-VramTotalMB; $MaxVramInUseMB = if ($vt) { [int]($vt / 2) } else { 8192 } }
[void][UnityPipeline.Win]::MakeDpiAware()   # physical pixels for window rects (displays may run above 100 % scaling)

$info = Get-GameInfo $Game
# Coordinator override (e.g. "record now, don't wait for idle"): builds\_queue\_idle-override.txt
# {"idle_minutes": 0, ...}. Applies when -IdleMinutes isn't given; pipeline.ps1 retires a one_drain one when the queue is empty.
$idleOverride = Read-JsonFile (Join-Path $BuildsRoot '_queue\_idle-override.txt')   # .txt: the drainer reads *.json as requests
if ($idleOverride -and -not $PSBoundParameters.ContainsKey('IdleMinutes')) {
    $IdleMinutes = [double]$idleOverride.idle_minutes
    Write-Step "idle wait override in effect: $IdleMinutes min ($(Get-Prop $idleOverride 'reason'))"
}
if ($Build -eq 'latest') {
    $Build = (Get-ChildItem (Join-Path $BuildsRoot $Game) -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '_*' -and (Test-Path (Join-Path $_.FullName 'build_info.json')) } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    if (-not $Build) { throw "no release build of $Game under $BuildsRoot\$Game (run build.ps1)" }
}
$buildInfo = Read-JsonFile (Join-Path $Build 'build_info.json')
if (-not $buildInfo -or $buildInfo.status -ne 'ok') { throw "$Build has no build_info.json with status ok (run build.ps1)" }
# The AutoPlay drop-in writes every file a run is checked on: a build without it cannot be recorded (its game would play
# on without ever writing ready.json).
$autoplayVersion = Get-Prop $buildInfo 'autoplay_version'
if ($null -eq $autoplayVersion) { throw "$Build was built from a commit without the AutoPlay drop-in (build_info.json autoplay_version is null): add it to the game (docs/autoplay-contract.md), commit, build again" }
$projectName = [string]$buildInfo.project
$exe = Join-Path $Build "Windows\$projectName.exe"
if (-not (Test-Path -LiteralPath $exe)) { $exe = [string]$buildInfo.exe_path }
if (-not (Test-Path -LiteralPath $exe)) { throw "no player in $Build (expected Windows\$projectName.exe)" }

$ffmpeg = Find-FFmpeg
$ffprobe = Find-FFprobe
$ffmpegVersion = (Invoke-Native $ffmpeg @('-hide_banner', '-version') | Select-Object -First 1)
$qpcFreq = [UnityPipeline.Win]::QpcFrequency()
$eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
# Encoder preference: NVENC (NVIDIA; the pinned ffmpeg needs driver >= 610), then AMF (AMD, e.g. an integrated Radeon),
# then libx264 on the CPU.
$Encoder = 'libx264'
foreach ($enc in 'h264_nvenc', 'h264_amf') {
    & $ffmpeg -hide_banner -loglevel error -f lavfi -i 'color=c=black:s=256x256:r=60' -t 0.1 -c:v $enc -f null - 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $Encoder = $enc; break }
}
$ErrorActionPreference = $eap
Write-Step "ffmpeg: $ffmpeg ($ffmpegVersion), encoder $Encoder"
$skillCycle = @(1.0, 0.75, 0.5, 0.25)
$rng = New-Object System.Random

# ---------------------------------------------------------------------------------------------------------------------

function Start-Capture([string]$Mode, [int[]]$Rect, [string]$Title, [string]$VideoPath, [string]$LogPath, [string]$ProgressPath, [IntPtr]$Hwnd) {
    $x, $y, $w, $h = $Rect
    switch ($Mode) {
        'gfxcapture' {
            # Windows.Graphics.Capture of the game window itself (client area): other windows, dialogs, the cursor and
            # window moves never reach the video, so the game needs no topmost and the user can keep working.
            $capIn = "-f lavfi -i `"gfxcapture=hwnd=$($Hwnd.ToInt64()):capture_cursor=0:capture_border=0:display_border=0:max_framerate=120,showinfo`""
        }
        'ddagrab' {
            # Zero-copy: D3D11 frames straight into NVENC. showinfo on hardware frames costs nothing (no pixel access)
            # and gives one timestamped log line per captured frame for the start-time estimate.
            $capIn = "-f lavfi -i `"ddagrab=output_idx=${OutputIndex}:framerate=${CaptureRate}:dup_frames=0:offset_x=${x}:offset_y=${y}:video_size=${w}x${h}:draw_mouse=0,showinfo`""
        }
        'gdigrab-region' {
            $capIn = "-f gdigrab -framerate 60 -draw_mouse 0 -offset_x $x -offset_y $y -video_size ${w}x${h} -i desktop -vf showinfo"
        }
        'gdigrab-window' {
            $capIn = "-f gdigrab -framerate 60 -draw_mouse 0 -i `"title=$Title`" -vf showinfo"
        }
    }
    $tags = '-color_primaries bt709 -color_trc bt709 -colorspace bt709 -color_range tv -fps_mode cfr -r ' + $OutputFps + ' -an'
    if ($Encoder -eq 'h264_nvenc') {
        $encode = "-c:v h264_nvenc -preset p5 -tune hq -rc vbr -cq 19 -b:v 0 -maxrate 60M -bufsize 120M -g 120 -bf 0 $tags"
        if ($Mode -notin @('ddagrab', 'gfxcapture')) { $encode = "-pix_fmt yuv420p $encode" }   # ddagrab: D3D11 frames go to NVENC as they are
    } else {
        # AMF / libx264 take system-memory frames: pick the 60 fps grid first (fps filter, no pixel access), so only 60
        # frames a second are downloaded from the GPU and converted with an explicit BT.709 matrix.
        $pix = if ($Encoder -eq 'h264_amf') { 'nv12' } else { 'yuv420p' }
        $conv = "scale=out_color_matrix=bt709:out_range=tv,format=$pix"
        if ($Mode -in @('ddagrab', 'gfxcapture')) { $capIn = $capIn.TrimEnd('"') + ",fps=$OutputFps,hwdownload,format=bgra,$conv" + '"' }
        else { $capIn += ",$conv" }
        $encode = if ($Encoder -eq 'h264_amf') { "-c:v h264_amf -quality quality -rc cqp -qp_i 18 -qp_p 20 -g 120 -bf 0 $tags" }
                   else { "-c:v libx264 -preset ultrafast -crf 17 -g 120 -bf 0 -pix_fmt yuv420p $tags" }
    }
    $ffArgs = "-hide_banner -loglevel +datetime+level+info -stats_period 1 -progress `"$ProgressPath`" -y $capIn $encode `"$VideoPath`""
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'cmd.exe'
    $psi.Arguments = "/d /s /c `"`"$ffmpeg`" $ffArgs 2> `"$LogPath`"`""
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardInput = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    return [pscustomobject]@{ Process = $p; Command = "ffmpeg $ffArgs"; Mode = $Mode }
}

function Stop-Capture($Cap, [int]$TimeoutMs = 15000) {
    if ($Cap.Process.HasExited) { return }
    try { $Cap.Process.StandardInput.Write('q'); $Cap.Process.StandardInput.Flush() } catch { }
    if (-not $Cap.Process.WaitForExit($TimeoutMs)) {
        # cmd and its ffmpeg child. taskkill writes to stderr when a child is already gone or cannot be ended; under
        # $ErrorActionPreference Stop that became a terminating error and failed the whole run, so it runs with
        # Continue and its output is ignored.
        $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
        try { & taskkill.exe /T /F /PID $Cap.Process.Id 2>&1 | Out-Null } catch { } finally { $ErrorActionPreference = $eap }
        [void]$Cap.Process.WaitForExit(5000)
    }
}

function Get-CapturedFrameCount([string]$LogPath) {
    if (-not (Test-Path $LogPath)) { return 0 }
    try {
        $fs = [System.IO.File]::Open($LogPath, 'Open', 'Read', 'ReadWrite')
        $text = (New-Object System.IO.StreamReader($fs)).ReadToEnd(); $fs.Dispose()
        return ([regex]::Matches($text, 'Parsed_showinfo.*?\] \[info\] n:')).Count
    } catch { return 0 }
}

# Background Unity work (batchmode editors: builds, editor steps, tests, other sessions' jobs; shader compilers, the
# build backend, IL2CPP) runs at BelowNormal while a run is recorded, so a busy CPU does not drop the recorded game below
# 60 fps (a game recorded beside builds and replays ran at 13 fps). Only these processes are touched; their previous
# priority is restored after the run.
$script:LoweredProcs = @{}
$script:BackgroundUnityNames = @('UnityShaderCompiler', 'bee_backend', 'il2cpp', 'Unity.ILPP.Runner', 'Unity.ILPP.Trigger')
function Set-BackgroundUnityLow {
    # Unity.exe is the editor GUI too: only batchmode editors count.
    $batch = @(Get-CimInstance Win32_Process -Filter "Name='Unity.exe'" -ErrorAction SilentlyContinue | Where-Object { "$($_.CommandLine)" -match '(?i)(^|\s)-batchmode(\s|$)' } | ForEach-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue })
    foreach ($p in @(@(Get-Process -Name $script:BackgroundUnityNames -ErrorAction SilentlyContinue) + $batch | Where-Object { $_ })) {
        try {
            if ($p.PriorityClass -in @([Diagnostics.ProcessPriorityClass]::Normal, [Diagnostics.ProcessPriorityClass]::AboveNormal, [Diagnostics.ProcessPriorityClass]::High)) {
                if (-not $script:LoweredProcs.ContainsKey($p.Id)) { $script:LoweredProcs[$p.Id] = @{ prio = $p.PriorityClass; start = $p.StartTime } }
                $p.PriorityClass = 'BelowNormal'
            }
        } catch { }
    }
}
function Restore-BackgroundUnity {
    foreach ($id in @($script:LoweredProcs.Keys)) {
        try { $p = Get-Process -Id $id -ErrorAction Stop; if ($p.StartTime -eq $script:LoweredProcs[$id].start) { $p.PriorityClass = $script:LoweredProcs[$id].prio } } catch { }
    }
    $script:LoweredProcs = @{}
}

function Get-PtsUs([string]$LogPath) {
    # Microseconds per pts unit, from showinfo's "config in time_base: a/b" line: ddagrab and gdigrab use 1/1000000,
    # gfxcapture 1/10000000 (reading its pts as us made a 60 fps capture look like 6 fps and broke the start estimate).
    foreach ($line in [System.IO.File]::ReadLines($LogPath)) {
        if ($line -match 'Parsed_showinfo[^\]]*\] \[info\] config in time_base: (\d+)/(\d+)') { if ([double]$matches[2] -gt 0) { return [double]$matches[1] * 1e6 / [double]$matches[2] } }
        if ($line -match 'Parsed_showinfo[^\]]*\] \[info\] n:') { break }
    }
    return 1.0
}

function Get-VideoStart([string]$LogPath, $ClockSamples) {
    # First captured frame's wall time = min over frames of (log time - pts), plus half a millisecond for the log's
    # truncation to ms. ffmpeg logs local time from av_gettime (GetSystemTimePreciseAsFileTime); map it to QPC with
    # the pipeline's QPC/UTC pairs.
    $best = [long]::MaxValue; $n = 0; $ptsUs = Get-PtsUs $LogPath
    foreach ($line in [System.IO.File]::ReadLines($LogPath)) {
        if ($line -match '^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) \[Parsed_showinfo[^\]]*\] \[info\] n:\s*(\d+) pts:\s*(-?\d+)') {
            $local = [datetime]::ParseExact($matches[1], 'yyyy-MM-dd HH:mm:ss.fff', $Inv, 'AssumeLocal')
            $unixNs = ($local.ToUniversalTime().Ticks - 621355968000000000) * 100
            $d = $unixNs - [long]([double]$matches[3] * $ptsUs * 1000)   # wall time of frame 0 implied by this frame
            if ($d -lt $best) { $best = $d }
            $n++
            if ($n -ge 1800) { break }   # first 30 s are plenty
        }
    }
    if ($n -eq 0) { return $null }
    $firstUnixNs = $best + 500000
    # Map unix ns -> QPC ns through the pipeline clock pair nearest in time.
    $pair = $ClockSamples | Sort-Object { [math]::Abs($_.unix_ns - $firstUnixNs) } | Select-Object -First 1
    $tNs = $pair.t_ns + ($firstUnixNs - $pair.unix_ns)
    return [pscustomobject]@{ t_ns = $tNs; unix_ns = $firstUnixNs; frames_used = $n; clock_pair = $pair.label; uncertainty_ms = 1.5 }
}

function Get-InputGaps([string]$LogPath, [long]$FromUs = 0, [long]$ToUs = [long]::MaxValue) {
    # Capture input timing from showinfo: count, rate, and frames missing in gaps longer than 25 ms.
    $prev = $null; $n = 0; $missed = 0; $gaps = 0; $first = $null; $ptsUs = Get-PtsUs $LogPath
    foreach ($line in [System.IO.File]::ReadLines($LogPath)) {
        if ($line -match 'Parsed_showinfo[^\]]*\] \[info\] n:\s*\d+ pts:\s*(\d+)') {
            $pts = [long]([double]$matches[1] * $ptsUs)   # in us
            if ($pts -lt $FromUs -or $pts -gt $ToUs) { continue }
            $n++
            if ($null -eq $first) { $first = $pts }
            if ($null -ne $prev -and ($pts - $prev) -gt 25000) { $gaps++; $missed += [math]::Round(($pts - $prev) / 16666.7) - 1 }
            $prev = $pts
        }
    }
    if ($n -lt 2) { return $null }
    $span = ($prev - $first) / 1e6
    if ($span -le 0) { return $null }
    return [ordered]@{ frames = $n; span_s = [math]::Round($span, 3); rate_fps = [math]::Round($n / $span, 1); gaps_over_25ms = $gaps
        missed_60fps_frames = $missed; missed_pct = [math]::Round(100.0 * $missed / ($span * 60), 2) }
}

function Read-Progress([string]$Path) {
    $vals = @{}
    if (Test-Path $Path) {
        foreach ($l in Get-Content $Path) { if ($l -match '^(\w+)=(.*)$') { $vals[$matches[1]] = $matches[2].Trim() } }
    }
    return $vals
}

function Test-Jsonl([string]$Path) {
    # Parses every line; returns counts per type/event, first/last t_ns, monotonicity.
    $ser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $ser.MaxJsonLength = 64MB
    $r = [ordered]@{ lines = 0; bad_lines = 0; non_monotonic = 0; first_t_ns = $null; last_t_ns = $null; counts = @{} }
    if (-not (Test-Path $Path)) { return $null }
    $prev = 0
    foreach ($line in [System.IO.File]::ReadLines($Path)) {
        if ($line.Trim() -eq '') { continue }
        $r.lines++
        try { $o = $ser.DeserializeObject($line) } catch { $r.bad_lines++; continue }
        if ($o -isnot [System.Collections.IDictionary]) { $r.bad_lines++; continue }
        $t = if ($o.ContainsKey('t_ns')) { [long]$o['t_ns'] } else { $prev }
        if ($t -lt $prev) { $r.non_monotonic++ }
        $prev = $t
        if ($null -eq $r.first_t_ns) { $r.first_t_ns = $t }
        $r.last_t_ns = $t
        $k = "$(if ($o.ContainsKey('type')) { $o['type'] } elseif ($o.ContainsKey('event')) { $o['event'] })"
        if ($r.counts.ContainsKey($k)) { $r.counts[$k]++ } else { $r.counts[$k] = 1 }
    }
    return $r
}

function Get-AudioStats([string]$WavPath) {
    if (-not (Test-Path $WavPath)) { return $null }
    $probe = Invoke-Native $ffprobe @('-v', 'error', '-show_entries', 'stream=sample_rate,channels,duration', '-of', 'json', $WavPath) | Out-String | ConvertFrom-Json
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $vol = & $ffmpeg -hide_banner -nostats -i $WavPath -af volumedetect -f null - 2>&1 | ForEach-Object { "$_" }
    $ErrorActionPreference = $eap
    $mean = ($vol | Select-String 'mean_volume: (-?[\d\.]+|-inf) dB' | Select-Object -First 1)
    $max = ($vol | Select-String 'max_volume: (-?[\d\.]+|-inf) dB' | Select-Object -First 1)
    # A WAV the game never finalised (run stopped early) probes as {} with no streams: same as no audio.
    if (-not $probe -or $probe.PSObject.Properties.Name -notcontains 'streams' -or @($probe.streams).Count -eq 0) { return $null }
    $s = @($probe.streams)[0]
    return [ordered]@{
        sample_rate = [int]$s.sample_rate; channels = [int]$s.channels; duration_s = [double]::Parse("$($s.duration)", $Inv)
        mean_volume_db = $(if ($mean -and $mean.Matches[0].Groups[1].Value -ne '-inf') { [double]::Parse($mean.Matches[0].Groups[1].Value, $Inv) } else { $null })
        max_volume_db = $(if ($max -and $max.Matches[0].Groups[1].Value -ne '-inf') { [double]::Parse($max.Matches[0].Groups[1].Value, $Inv) } else { $null })
    }
}

Add-Type -AssemblyName System.Web.Extensions

# ---------------------------------------------------------------------------------------------------------------------

# Run from a stable copy (builds\<game>\_run): Windows Firewall asks once per program path for a program that listens on
# the network; a fixed path per game means one prompt per game, not one per build.
if (-not $NoStablePath) {
    $runRoot = Join-Path (Join-Path $BuildsRoot $Game) '_run'
    Enter-PipelineLock "stage $Game run copy" -Game $Game
    try {
        Write-Step "mirroring $Build\Windows -> $runRoot\Windows"
        # Unity's *_BurstDebugInformation_DoNotShip and *_BackUpThisFolder_ButDontShipItWithYourGame (debug symbols and
        # IL2CPP's generated sources, about a gigabyte a build) are no part of a run: left out, and removed when an
        # older copy has them (/XD skips them in the target too).
        & robocopy.exe (Join-Path $Build 'Windows') (Join-Path $runRoot 'Windows') /MIR /XD '*_DoNotShip' '*_ButDontShipItWithYourGame' /NJH /NJS /NP /NFL /NDL /R:2 /W:2 | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
        Get-ChildItem (Join-Path $runRoot 'Windows') -Directory | Where-Object { $_.Name -match '(_DoNotShip|_ButDontShipItWithYourGame)$' } | Remove-Item -Recurse -Force
        Copy-Item (Join-Path $Build 'build_info.json') (Join-Path $runRoot 'build_info.json') -Force
    } finally { Exit-PipelineLock }
    $exe = Join-Path $runRoot "Windows\$(Split-Path $exe -Leaf)"
}

$results = New-Object System.Collections.ArrayList
for ($i = 0; $i -lt $Runs; $i++) {
    $runSeed = if ($Seed -ge 0) { $Seed + $i } else { $rng.Next(1, [int]::MaxValue) }
    $runSkill = if ($Skill -ge 0) { $Skill } else { $skillCycle[$i % $skillCycle.Count] }
    $runId = '{0}_S{1}_{2}_s{3}' -f $Game, $Scenario, (Get-Date -Format 'yyyyMMdd-HHmmss'), $runSeed
    $runDir = Join-Path (Join-Path $RecordingsRoot $Game) $runId
    $rawDir = Join-Path $runDir 'raw'
    New-Item -ItemType Directory -Force $rawDir | Out-Null
    $videoPath = Join-Path $runDir 'video.mkv'
    $ffLog = Join-Path $rawDir 'ffmpeg.log'
    $ffProgress = Join-Path $rawDir 'ffmpeg_progress.txt'
    $clock = New-Object System.Collections.ArrayList
    $problems = New-Object System.Collections.ArrayList
    $warnings = New-Object System.Collections.ArrayList
    $proc = $null; $cap = $null; $hwnd = [IntPtr]::Zero; $rect = $null; $title = $null
    $gameExit = $null; $killed = $false; $windowMoved = $false; $captureMode = $null; $privacyStop = $null
    $coverFirst = $null; $coverWhat = ''; $coverCount = 0; $watchdog = $null
    $tStart = Get-Date
    # Display refresh: a 60 fps capture repeats/skips game frames unless the refresh is a multiple of 60 (60, 120, 240 Hz).
    $vc = Get-CimInstance Win32_VideoController | Where-Object { $_.CurrentRefreshRate -gt 1 -and $_.CurrentHorizontalResolution -gt 0 } | Select-Object -First 1
    $refreshHz = if ($vc) { [int]$vc.CurrentRefreshRate } else { $null }
    # fractional rates (59.94, 119.88 Hz) are reported rounded down (59, 119): count them as the 60-multiple they are
    if ($refreshHz -and $refreshHz -ge 59 -and ($refreshHz + 1) % 60 -eq 0) { $refreshHz++ }
    $displayMode = if ($vc) { "$($vc.CurrentHorizontalResolution)x$($vc.CurrentVerticalResolution) @ $($vc.CurrentRefreshRate) Hz ($($vc.Name))" } else { $null }
    if (-not $refreshHz -or $refreshHz % 60 -ne 0) { [void]$warnings.Add("display refresh is $refreshHz Hz, not a multiple of 60 (60 fps capture will repeat/skip game frames)") }

    # Screen capture needs the window untouched for minutes: wait until the user is away (and the session unlocked).
    # Keep the display on from now on: waiting for 5 idle minutes otherwise runs into the power plan's dim/off timer,
    # and Windows' dim overlay then covers the game. Doesn't affect the idle measurement (input only).
    [UnityPipeline.Win]::KeepDisplayOn($true)
    # Then the GPU to ourselves: every GPU slot of the machine and little VRAM in use by others. If the user came back
    # while we waited for those, give the slots back and wait again.
    $gpuSlot = $null; $vramOk = $true
    while ($true) {
        if ($IdleMinutes -gt 0) {
            $said = $false
            while ([UnityPipeline.Win]::IdleMs() -lt $IdleMinutes * 60000 -or (Get-Process LogonUI -ErrorAction SilentlyContinue)) {
                [UnityPipeline.Win]::KeepDisplayOn($true)   # refresh while waiting
                if (-not $said) { Write-Step "waiting until the user has been idle for $IdleMinutes min (and the session is unlocked)"; $said = $true }
                Start-Sleep -Seconds 15
            }
            if ($said) { Write-Step 'user idle' }
        }
        $gpuSlot = Enter-GpuSlot "record $Game $runId" -Recording
        $vramOk = Wait-VramFree "record $Game $runId" $MaxVramInUseMB
        if ($IdleMinutes -le 0 -or [UnityPipeline.Win]::IdleMs() -ge $IdleMinutes * 60000) { break }
        Write-Step 'user came back while waiting for the GPU: releasing the GPU slots and waiting again'
        Exit-GpuSlot $gpuSlot; $gpuSlot = $null
    }
    Write-Step "GPU slots held; $(Get-VramUsedMB) MB VRAM in use before launch"
    Enter-PipelineLock "record $Game $runId" -Game $Game
    [UnityPipeline.Win]::KeepDisplayOn($true)
    # The display may have gone off while we waited for the user to be away (display timeout = idle gate): wake it,
    # or ddagrab gets no frames.
    Invoke-WakeDisplay
    try {
        Write-Step "run $($i + 1)/$Runs $runId (skill $runSkill, seed $runSeed)"
        if (-not $vramOk) { throw "more than $MaxVramInUseMB MB VRAM stayed in use by other processes for 120 min; not launching" }
        [void]$clock.Add((Get-ClockSample 'record_start'))
        # The contract's flags (docs/autoplay-contract.md section 1), Unity style: one dash, the value as the next argument.
        $gameArgs = "-autoplay -scenario $Scenario -seed $runSeed -skill $($runSkill.ToString($Inv)) -outputDir `"$rawDir`" -maxSeconds $MaxSeconds " +
                    "-buildCommit $($buildInfo.commit) -runId $runId -goTimeout 300 " +
                    "-screen-fullscreen 0 -screen-width 1920 -screen-height 1080 -logFile `"$rawDir\game.log`" $ExtraArgs"
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $exe; $psi.Arguments = $gameArgs.Trim(); $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true   # the player's log is raw\game.log (-logFile)
        $psi.WorkingDirectory = Split-Path $exe
        $proc = [System.Diagnostics.Process]::Start($psi)
        $proc.BeginOutputReadLine(); $proc.BeginErrorReadLine()   # drain and discard
        try { $proc.PriorityClass = 'AboveNormal' } catch { }
        Set-BackgroundUnityLow; $lastLow = Get-Date

        # ---- wait for ready.json, find the window ----
        $deadline = (Get-Date).AddSeconds(180)
        while (-not (Test-Path (Join-Path $rawDir 'ready.json'))) {
            if ($proc.HasExited) { throw "game exited (code $($proc.ExitCode)) before ready" }
            if ((Get-Date) -gt $deadline) { throw 'no ready.json within 180 s' }
            Start-Sleep -Milliseconds 200
        }
        # The game may still hold ready.json open (sharing violation) or have written it only partly: retry for 10 s.
        $ready = $null; $readyDeadline = (Get-Date).AddSeconds(10)
        while (-not $ready) {
            try { $ready = Read-JsonFile (Join-Path $rawDir 'ready.json') }
            catch { if ((Get-Date) -gt $readyDeadline) { throw } }
            if (-not $ready) {
                if ((Get-Date) -gt $readyDeadline) { throw 'ready.json stayed empty or unreadable for 10 s' }
                Start-Sleep -Milliseconds 200
            }
        }
        $readyPid = if (Get-Prop $ready 'pid') { [uint32]$ready.pid } else { [uint32]$proc.Id }
        # A Unity player's game window is of class UnityWndClass; any visible window of the process otherwise.
        $hwnd = [UnityPipeline.Win]::FindWindowOfPid($readyPid, $null, 'UnityWndClass')
        if ($hwnd -eq [IntPtr]::Zero) { $hwnd = [UnityPipeline.Win]::FindWindowOfPid($readyPid, $null, $null) }
        if ($hwnd -eq [IntPtr]::Zero) { throw "no visible window for pid $readyPid" }
        $title = [UnityPipeline.Win]::Title($hwnd)
        # Centre the 1920x1080 client on the primary screen ourselves (any screen size that holds it; the title bar may
        # sit off-screen on an exactly-1080p display).
        $screen = [UnityPipeline.Win]::PrimaryScreenSize()
        if ($screen[0] -lt 1920 -or $screen[1] -lt 1080) { throw "primary screen is $($screen -join 'x'); recording needs room for a 1920x1080 client (check.ps1: Primary display)" }
        [void][UnityPipeline.Win]::MoveClientTo($hwnd, [int][math]::Floor(($screen[0] - 1920) / 2), [int][math]::Floor(($screen[1] - 1080) / 2))
        Start-Sleep -Milliseconds 300
        $rect = [UnityPipeline.Win]::ClientRectOnScreen($hwnd)
        Write-Step "window '$title' client $($rect -join ',') on screen $($screen -join 'x')"
        if ($rect[2] -ne 1920 -or $rect[3] -ne 1080) { throw "client area is $($rect[2])x$($rect[3]), expected 1920x1080" }
        if ($rect[0] -lt 0 -or $rect[1] -lt 0 -or $rect[0] + 1920 -gt $screen[0] -or $rect[1] + 1080 -gt $screen[1]) { throw "window not fully on the primary screen: $($rect -join ',')" }

        # ---- start capture (ddagrab, falling back to gfxcapture, then gdigrab) ----
        # ddagrab (topmost window + privacy guard) is the default. It is tried twice: a display that went off delivers
        # no Desktop Duplication frames, so the second try follows a display wake (attempt files are named ddagrab and
        # ddagrab-retry). Then gfxcapture (Windows.Graphics.Capture of the game window): it needs no live display
        # (a PC whose only monitor is off or unplugged, reached over remote desktop: ddagrab hangs there, gdigrab-region
        # reaches ~38 fps) and delivers ~59 fps with the window topmost and in the foreground. Its pts are in 1/10^7 s
        # (Get-PtsUs). gdigrab-region is the last resort.
        $modes = if ($Capture -eq 'auto') { @('ddagrab', 'ddagrab-retry', 'gfxcapture', 'gdigrab-region') } else { @($Capture) }
        if ($modes[0] -ne 'gfxcapture') {
            # A first-run Windows Firewall prompt (or anything else) on top of the game would trip the privacy guard:
            # wait for the client area to be clear (the game waits for 'go' up to -goTimeout 300).
            [void][UnityPipeline.Win]::SetTopmost($hwnd, $true)
            $t = (Get-Date).AddSeconds(240); $said = $false
            while (-not [UnityPipeline.Win]::IsClientUncovered($hwnd) -and (Get-Date) -lt $t) {
                if (-not $said) { Write-Step 'game window is covered (Windows Firewall prompt for a new program path?): waiting for it to clear'; $said = $true }
                Start-Sleep -Milliseconds 500
            }
            if (-not [UnityPipeline.Win]::IsClientUncovered($hwnd)) {
                $coveredBy = [UnityPipeline.Win]::CoveringWindow($hwnd)
                # Window capture never records other windows: fall back to it instead of giving up.
                if ($modes -notcontains 'gfxcapture') { throw "game window stayed covered for 240 s by $coveredBy; not recording" }
                [void]$warnings.Add("game window stayed covered for 240 s by ${coveredBy}: screen-region capture skipped, window capture (gfxcapture) used")
                Write-Step "game window stayed covered by ${coveredBy}: using gfxcapture"
                $modes = @('gfxcapture')
            }
        }
        foreach ($m in $modes) {
            $mode = if ($m -eq 'ddagrab-retry') { 'ddagrab' } else { $m }
            if ($m -eq 'ddagrab-retry') { Write-Step 'ddagrab got no frames: waking the display and trying ddagrab once more'; Invoke-WakeDisplay 5 }
            # Screen-region modes record whatever is on screen there: keep the game on top. gfxcapture records only the
            # game window, but it too is kept on top and brought to the foreground, so the compositor keeps delivering
            # every frame of it (the user's input still goes wherever they click).
            [void][UnityPipeline.Win]::SetTopmost($hwnd, $true)
            if ($m -eq 'gfxcapture') {
                Add-Type -Namespace RecordFg -Name W -ErrorAction SilentlyContinue -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
'@
                # A background process may not take the foreground; a synthetic Alt tap lifts the foreground lock.
                [RecordFg.W]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [void][RecordFg.W]::SetForegroundWindow($hwnd); [RecordFg.W]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
                Start-Sleep -Milliseconds 300
                if ([RecordFg.W]::GetForegroundWindow() -ne $hwnd) { [void]$warnings.Add('gfxcapture: the game window could not be brought to the foreground') }
            }
            # One set of files per attempt: a failed attempt's ffmpeg must never block the next attempt's files.
            $videoPath = Join-Path $runDir "video.$m.mkv"
            $ffLog = Join-Path $rawDir "ffmpeg-$m.log"
            $ffProgress = Join-Path $rawDir "ffmpeg_progress-$m.txt"
            [void]$clock.Add((Get-ClockSample "capture_start_$m"))
            $cap = Start-Capture $mode $rect $title $videoPath $ffLog $ffProgress $hwnd
            try { Get-CimInstance Win32_Process -Filter "ParentProcessId=$($cap.Process.Id)" | ForEach-Object { (Get-Process -Id $_.ProcessId).PriorityClass = 'AboveNormal' } } catch { }
            $t = (Get-Date).AddSeconds(10)
            while ((Get-CapturedFrameCount $ffLog) -lt 30 -and -not $cap.Process.HasExited -and (Get-Date) -lt $t) { Start-Sleep -Milliseconds 100 }
            $frames = Get-CapturedFrameCount $ffLog
            if ($frames -ge 30 -and -not $cap.Process.HasExited) { $captureMode = $mode; break }
            # ffmpeg's stderr is the attempt log (2> in Start-Capture); say whether it hung or exited, and with what.
            $how = if ($cap.Process.HasExited) { "ffmpeg exited with code $($cap.Process.ExitCode)" } else { "ffmpeg still starting after 10 s (hung in device/probe init)" }
            [void]$warnings.Add("capture attempt $m failed: $frames frames in 10 s, $how; log: $((Get-Content $ffLog -Tail 5 -ErrorAction SilentlyContinue) -join ' | ')")
            Write-Step "capture attempt $m failed: $frames frames, $how"
            Stop-Capture $cap 3000
            if (Test-Path $videoPath) { Move-Item -Force $videoPath (Join-Path $rawDir "failed-attempt-$m.mkv") }
            $cap = $null
        }
        if (-not $cap) { throw 'no capture mode worked' }
        Write-Step "capturing with $captureMode"

        # ---- go ----
        [void]$clock.Add((Get-ClockSample 'go_written'))
        [System.IO.File]::WriteAllText((Join-Path $rawDir 'go'), (Get-IsoNow), $Utf8NoBom)

        # ---- wait for the run to end: outcome.json appears at the end of the result screen ----
        $deadline = (Get-Date).AddSeconds($MaxSeconds + 90)
        $outcomePath = Join-Path $rawDir 'outcome.json'
        while (-not (Test-Path $outcomePath)) {
            if ($proc.HasExited) {
                if (Test-Path $outcomePath) { break }   # it wrote outcome.json and quit between two looks
                # Gone without outcome.json (a crash): its window closed while ffmpeg still captured that part of the
                # screen, so the video is cut to 0.5 s before this sighting, as for the privacy guard.
                $privacyStop = Get-ClockSample 'game_exited'
                [void]$problems.Add("game exited (code $($proc.ExitCode)) before writing outcome.json")
                break
            }
            if ((Get-Date) -gt $deadline) { $killed = $true; [void]$problems.Add("timeout: killed after $($MaxSeconds + 90) s"); break }
            if ($cap.Process.HasExited) { [void]$problems.Add('ffmpeg exited during the run'); break }
            if (((Get-Date) - $lastLow).TotalSeconds -ge 5) { Set-BackgroundUnityLow; $lastLow = Get-Date }   # jobs started meanwhile
            $now = [UnityPipeline.Win]::ClientRectOnScreen($hwnd)
            if ($now -and ($now[2] -ne 1920 -or $now[3] -ne 1080)) { [void]$problems.Add("game window client area changed to $($now[2])x$($now[3])"); break }
            if ([UnityPipeline.Win]::IsIconic($hwnd)) { [void]$problems.Add('game window was minimized (no frames)'); break }
            if ($now -and ($now[0] -ne $rect[0] -or $now[1] -ne $rect[1])) {
                if (-not $windowMoved) {
                    # Who moved it? A held mouse button means a user drag; otherwise the game (e.g. a resolution change)
                    # or another program.
                    Add-JsonLine (Join-Path $rawDir 'window.jsonl') ([ordered]@{ event = 'moved'; t_ns = (Get-ClockSample 'x').t_ns
                        from = $rect; to = $now; mouse_button_down = [UnityPipeline.Win]::MouseButtonDown() })
                }
                $windowMoved = $true
            }
            $covered = ($captureMode -ne 'gfxcapture') -and -not [UnityPipeline.Win]::IsClientUncovered($hwnd)
            if ($covered) {
                if (-not $coverFirst) { $coverFirst = Get-ClockSample 'privacy_first_seen'; $coverWhat = [UnityPipeline.Win]::CoveringWindow($hwnd) }
                $coverCount++
            } else { $coverFirst = $null; $coverCount = 0 }
            if ($captureMode -ne 'gfxcapture' -and ($windowMoved -or $coverCount -ge 3)) {
                # Privacy guard: a screen-region capture would now record other windows (moved window, or something
                # on top for ~0.3 s; shorter blips are tooltips/ghost windows). Stop; the video is cut to 0.5 s before
                # the first sighting below.
                $privacyStop = if ($coverFirst) { $coverFirst } else { Get-ClockSample 'privacy_stop' }
                $cover = if ($windowMoved) { '' } else { $coverWhat }
                Stop-Capture $cap
                [void]$problems.Add($(if ($windowMoved) { 'game window moved during screen-region capture: capture stopped' } else { "another window covered the game during screen-region capture: capture stopped ($cover)" }))
                $killed = $true
                break
            }
            Start-Sleep -Milliseconds 100
        }
        Stop-Capture $cap   # before the window closes: never capture what is behind it
        [void]$clock.Add((Get-ClockSample 'capture_stopped'))
        $final = Join-Path $runDir 'video.mkv'
        if (Test-Path $videoPath) { Move-Item -Force $videoPath $final }
        $videoPath = $final
        if ($windowMoved -and $captureMode -eq 'gfxcapture') { [void]$warnings.Add('game window was moved during the run (window capture follows it)') }

        if ($killed) {
            if (-not $proc.HasExited) { $proc.Kill() }
            [void]$proc.WaitForExit(10000)
        } elseif (-not $proc.WaitForExit(60000)) {
            [void]$problems.Add('game did not quit within 60 s after outcome.json'); $proc.Kill(); $killed = $true; [void]$proc.WaitForExit(10000)
        }
        $gameExit = $proc.ExitCode
        # Exit code 124 + watchdog.json: the AutoPlay drop-in's exit watchdog ended the process (contract section 3).
        # After run_end ("shutdown") the run itself is complete, so only a hang in shutdown is noted; "run" fails it.
        $wdPath = Join-Path $rawDir 'watchdog.json'
        if (Test-Path $wdPath) { try { $watchdog = Read-JsonFile $wdPath } catch { $watchdog = [pscustomobject]@{ reason = 'unreadable' } } }
        if (-not $killed -and $watchdog -and (Get-Prop $watchdog 'reason') -eq 'shutdown' -and (Test-Path $outcomePath)) { [void]$warnings.Add('game hung in shutdown after run_end: ended by the AutoPlay exit watchdog') }
        elseif (-not $killed -and $watchdog) { [void]$problems.Add("game ended by the AutoPlay exit watchdog ($(Get-Prop $watchdog 'reason'))") }
        elseif (-not $killed -and $gameExit -ne 0) { [void]$problems.Add("game exit code $gameExit") }
    } catch {
        [void]$problems.Add("run error: $($_.Exception.Message)")
        Write-Step "ERROR: $($_.Exception.Message)"
        if ($cap) { Stop-Capture $cap }
        if ($proc -and -not $proc.HasExited) { $proc.Kill(); $killed = $true; [void]$proc.WaitForExit(15000) }
    } finally {
        if ($hwnd -ne [IntPtr]::Zero -and [UnityPipeline.Win]::IsWindow($hwnd)) { [void][UnityPipeline.Win]::SetTopmost($hwnd, $false) }
        [void]$clock.Add((Get-ClockSample 'record_end'))
        Restore-BackgroundUnity
        [UnityPipeline.Win]::KeepDisplayOn($false)
        Exit-PipelineLock
        Exit-GpuSlot $gpuSlot
    }

    # ---- post-process (light work, outside the lock) ----
    if ((Split-Path $videoPath -Leaf) -ne 'video.mkv' -and (Test-Path $videoPath)) {   # run error mid-capture
        Move-Item -Force $videoPath (Join-Path $runDir 'video.mkv')
    }
    $videoPath = Join-Path $runDir 'video.mkv'
    $outcome = $null; try { $outcome = Read-JsonFile (Join-Path $rawDir 'outcome.json') } catch { [void]$problems.Add("outcome.json is not JSON: $($_.Exception.Message)") }
    $gameClock = $null; try { $gameClock = Read-JsonFile (Join-Path $rawDir 'clock.json') } catch { }
    foreach ($f in 'inputs.jsonl', 'telemetry.jsonl', 'outcome.json') {
        $src = Join-Path $rawDir $f
        if (Test-Path $src) {
            try { Copy-Item $src (Join-Path $runDir $f) -Force } catch { [void]$problems.Add("could not copy ${f}: $($_.Exception.Message)") }
        } else { [void]$problems.Add("missing $f") }
    }
    if (-not $gameClock) { [void]$problems.Add('missing clock.json') }

    $audio = Get-AudioStats (Join-Path $rawDir 'audio.wav')
    if ($audio) {
        $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
        & $ffmpeg -hide_banner -loglevel error -y -i (Join-Path $rawDir 'audio.wav') -c:a flac (Join-Path $runDir 'system_audio.mka') 2>&1 | Out-Null
        $ErrorActionPreference = $eap
    } else { [void]$problems.Add('missing audio.wav') }

    $videoStart = $null; $probe = $null; $cutEndNs = $null; $endCut = $null
    if ($captureMode -and (Test-Path $videoPath)) {
        $videoStart = Get-VideoStart $ffLog $clock
        # Where the video must end: 0.5 s before the privacy guard fired (or the game vanished), else at the game's own
        # end clock sample, which the drop-in takes before it quits (contract section 3, step 8): a player closes its
        # window right after outcome.json, before ffmpeg has stopped, and the frames after that show what was behind it.
        $endSample = @(@(Get-Prop $gameClock 'samples') | Where-Object { $_ -and $_.label -eq 'end' }) | Select-Object -First 1
        $cutNs = if ($privacyStop) { [long]$privacyStop.t_ns - 500000000 } elseif ($endSample) { [long]$endSample.t_ns } else { $null }
        if ($null -ne $cutNs -and $videoStart) {
            # 0.0, not 0: [math]::Max(0, <double>) takes the integer overload and rounds the cut to a whole second
            $keep = [math]::Max(0.0, [double]($cutNs - $videoStart.t_ns) / 1e9)
            $cut = Join-Path $runDir 'video.cut.mkv'
            $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
            & $ffmpeg -hide_banner -loglevel error -y -i $videoPath -t $keep.ToString('0.000', $Inv) -c copy $cut 2>&1 | Out-Null
            $ErrorActionPreference = $eap
            if (Test-Path $cut) {
                Move-Item -Force $cut $videoPath
                $cutEndNs = $cutNs
                $endCut = [ordered]@{ at_s = [math]::Round($keep, 3); reason = $(if ($privacyStop) { "0.5 s before $($privacyStop.label)" } else { 'the game''s end clock sample' }) }
                if ($privacyStop) { [void]$warnings.Add("video cut to $([math]::Round($keep, 1)) s (privacy guard)") }
            } else {
                Move-Item -Force $videoPath (Join-Path $runDir 'video.UNTRIMMED-may-show-other-windows.mkv')
                [void]$problems.Add('could not cut the video before the window closed or was covered: delete video.UNTRIMMED-may-show-other-windows.mkv')
            }
        } elseif ($privacyStop) {
            Move-Item -Force $videoPath (Join-Path $runDir 'video.UNTRIMMED-may-show-other-windows.mkv')
            [void]$problems.Add('no video start estimate to cut the video before the privacy stop: delete video.UNTRIMMED-may-show-other-windows.mkv')
        }
        if (Test-Path $videoPath) {
            $probe = Invoke-Native $ffprobe @('-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=codec_name,profile,pix_fmt,width,height,avg_frame_rate,nb_read_packets:format=duration', '-of', 'json', $videoPath) | Out-String | ConvertFrom-Json
            if (-not $probe -or $probe.PSObject.Properties.Name -notcontains 'streams' -or @($probe.streams).Count -eq 0) { $probe = $null; [void]$problems.Add('video.mkv has no video stream') }
        }
    } elseif ($captureMode) { [void]$problems.Add('missing video.mkv') }
    $progress = Read-Progress $ffProgress

    # ---- validation ----
    $inputs = Test-Jsonl (Join-Path $runDir 'inputs.jsonl')
    $telemetry = Test-Jsonl (Join-Path $runDir 'telemetry.jsonl')
    $checks = [ordered]@{}
    $gs = @{}; if ($gameClock) { foreach ($s in @(Get-Prop $gameClock 'samples')) { if ($s) { $gs[[string]$s.label] = $s } } }
    $scenarioStartQpc = Get-Prop $outcome 'scenario_start_qpc'; $scenarioEndQpc = Get-Prop $outcome 'scenario_end_qpc'

    if ($outcome) {
        $result = Get-Prop $outcome 'result'
        $checks.outcome = [ordered]@{ ok = ($result -in @('win', 'lose', 'timeout', 'abort') -and -not (Get-Prop $outcome 'go_timed_out')); result = $result; score = (Get-Prop $outcome 'score'); duration_s = (Get-Prop $outcome 'duration_s') }
        if ($result -notin @('win', 'lose', 'timeout', 'abort')) { [void]$problems.Add("bad outcome.result '$result'") }
        if ($result -eq 'abort') { [void]$warnings.Add('run ended with abort') }
        if (Get-Prop $outcome 'go_timed_out') { [void]$problems.Add('game never saw the go file') }
    } else { [void]$problems.Add('no outcome.json') }

    if ($inputs) {
        $injects = 0; if ($inputs.counts.ContainsKey('inject')) { $injects = $inputs.counts['inject'] }
        $checks.inputs = [ordered]@{ ok = ($injects -gt 0 -and $inputs.bad_lines -eq 0 -and $inputs.non_monotonic -eq 0); lines = $inputs.lines; injects = $injects; bad_lines = $inputs.bad_lines; non_monotonic = $inputs.non_monotonic; counts = $inputs.counts }
        if ($injects -eq 0) { [void]$problems.Add('no injected inputs') }
        if ($inputs.bad_lines -gt 0) { [void]$problems.Add("inputs.jsonl has $($inputs.bad_lines) unparseable lines") }
        if ($inputs.non_monotonic -gt 0) { [void]$problems.Add("inputs.jsonl t_ns goes backwards $($inputs.non_monotonic) times") }
    }
    if ($telemetry) {
        $missingEvents = @(@('run_start', 'scenario_start', 'scenario_end', 'run_end') | Where-Object { -not $telemetry.counts.ContainsKey($_) })
        $checks.telemetry = [ordered]@{ ok = ($missingEvents.Count -eq 0 -and $telemetry.bad_lines -eq 0); lines = $telemetry.lines; missing = @($missingEvents); counts = $telemetry.counts }
        foreach ($e in $missingEvents) { [void]$problems.Add("telemetry has no $e") }
        if ($telemetry.bad_lines -gt 0) { [void]$problems.Add("telemetry.jsonl has $($telemetry.bad_lines) unparseable lines") }
    }

    # Audio clock: the drop-in writes the WAV itself and logs every buffer it received (WAV frame index -> QPC), filling
    # stalls with silence, so the WAV is sample-accurate to wall time. Frame 0 is at the first row's t_ns.
    $audioStartNs = $null; $audioAligned = $null; $audioAnchor = $null; $audioClockInfo = $null
    $audioClockPath = Join-Path $rawDir 'audio_clock.jsonl'
    if ($audio -and (Test-Path $audioClockPath)) {
        $rows = @(foreach ($l in [System.IO.File]::ReadLines($audioClockPath)) { if ($l -match '"frame":(\d+),"frames":(\d+),"qpc":\d+,"t_ns":(\d+),"silence_before":(\d+)') { [pscustomobject]@{ f = [long]$matches[1]; n = [long]$matches[2]; t = [long]$matches[3]; s = [long]$matches[4] } } })
        if ($rows.Count -gt 0) {
            $sr = [double]$audio.sample_rate
            $first = $rows[0]; $last = $rows[$rows.Count - 1]
            # Each row says where the WAV's frame 0 lies on the QPC clock (t_ns - frame / rate). The first buffers after
            # go arrive in a burst and the rest with up to a buffer of jitter, so the first row alone puts the WAV up to a
            # buffer (~21 ms) early: the median of all rows anchors it.
            $offs = @($rows | ForEach-Object { [double]$_.t - [double]$_.f / $sr * 1e9 } | Sort-Object)
            $audioStartNs = [long]$offs[[int][math]::Floor(($offs.Count - 1) / 2)]
            $spanS = ($last.t - $first.t) / 1e9 + $last.n / $sr
            $silenceS = ((@($rows | ForEach-Object { $_.s }) | Measure-Object -Sum).Sum) / $sr
            $gaps = @($rows | Where-Object { $_.s -gt 0 }).Count
            # Drift: WAV position of each buffer vs its wall time since frame 0 (should stay within ~2 buffers).
            $maxDriftMs = 0.0
            foreach ($r in $rows) { $d = [math]::Abs((($r.t - $audioStartNs) / 1e9 - $r.f / $sr) * 1000); if ($d -gt $maxDriftMs) { $maxDriftMs = $d } }
            $audioAligned = ($maxDriftMs -le 250 -and [math]::Abs($audio.duration_s - $spanS) -le 0.25)
            $audioAnchor = 'audio_clock.jsonl (per-buffer QPC; stalls filled with silence)'
            $audioClockInfo = [ordered]@{ buffers = $rows.Count; gaps_filled = $gaps; silence_inserted_s = [math]::Round($silenceS, 3); max_drift_ms = [math]::Round($maxDriftMs, 1); span_s = [math]::Round($spanS, 3) }
            $silent = ($null -eq $audio.max_volume_db) -or ($audio.max_volume_db -lt -60)
            $checks.audio = [ordered]@{ ok = $audioAligned; aligned = $audioAligned; anchor = 'audio_clock'; duration_s = $audio.duration_s; clock = $audioClockInfo; silent = $silent; stats = $audio }
            if ($gaps -gt 0) { [void]$warnings.Add("audio stalled $gaps times; $([math]::Round($silenceS, 2)) s of silence inserted to keep alignment") }
            if (-not $audioAligned) { [void]$problems.Add("system_audio unaligned: drift up to $([math]::Round($maxDriftMs)) ms vs audio_clock, WAV $($audio.duration_s) s vs span $([math]::Round($spanS, 2)) s") }
            if ($silent) { [void]$warnings.Add('audio is silent (max volume below -60 dB)') }
        }
    }
    if ($audio -and $null -eq $audioAligned) {
        # No audio_clock rows (a run cut short): the WAV ends at the audio_stop clock sample, so it is anchored at its end.
        # Its start then lags audio_start by the scenario's load (go -> scenario_start; the audio thread is busy).
        $startLagMs = $null
        if ($gs.ContainsKey('audio_start') -and $gs.ContainsKey('audio_stop')) {
            $audioStartNs = [long]$gs['audio_stop'].t_ns - [long]([double]$audio.duration_s * 1e9)
            $startLagMs = [math]::Round(($audioStartNs - [long]$gs['audio_start'].t_ns) / 1e6, 1)
        }
        $silent = ($null -eq $audio.max_volume_db) -or ($audio.max_volume_db -lt -60)
        $lagOk = ($null -ne $startLagMs -and $startLagMs -ge -30 -and $startLagMs -le 10000)
        $audioAligned = $lagOk; $audioAnchor = 'end: audio_stop clock sample minus WAV duration'
        $checks.audio = [ordered]@{ ok = $lagOk; aligned = $lagOk; anchor = 'end'; duration_s = $audio.duration_s; start_lag_ms = $startLagMs; silent = $silent; stats = $audio }
        if (-not $lagOk) { [void]$problems.Add("audio does not fit the recorded span: start lag $startLagMs ms (allowed -30..10000 ms)") }
        if ($silent) { [void]$warnings.Add('audio is silent (max volume below -60 dB)') }
    }

    if ($probe) {
        $st = @($probe.streams)[0]
        $vdur = [double]::Parse("$($probe.format.duration)", $Inv)
        $frames = [int]$st.nb_read_packets
        $dup = [int](Get-Prop $progress 'dup_frames'); $drop = [int](Get-Prop $progress 'drop_frames')
        $capSpan = $null; $cover = $null
        if ($videoStart) {
            # the span the video should fill: from its first frame to the stop, or to where it was cut
            $stopNs = if ($null -ne $cutEndNs) { $cutEndNs } else { ($clock | Where-Object { $_.label -eq 'capture_stopped' } | Select-Object -First 1).t_ns }
            $capSpan = ($stopNs - $videoStart.t_ns) / 1e9
            $videoEndNs = $videoStart.t_ns + [long]($vdur * 1e9)
            if ($null -ne $scenarioStartQpc -and $null -ne $scenarioEndQpc) {
                $levelStartNs = Convert-QpcToNs ([long]$scenarioStartQpc) $qpcFreq
                $levelEndNs = Convert-QpcToNs ([long]$scenarioEndQpc) $qpcFreq
                $cover = ($videoStart.t_ns -lt $levelStartNs -and $videoEndNs -gt $levelEndNs)
                if (-not $cover) { [void]$problems.Add('video does not cover the scenario (start..end)') }
            }
        } else { [void]$problems.Add('could not estimate video start time from ffmpeg log') }
        # ddagrab runs event-driven (dup_frames=0): every desktop update is an input frame (up to the display rate),
        # so drops are surplus samples; dups are 60 fps slots with no new desktop image (holes). Input gaps > 25 ms are
        # stretches where the desktop (the game) did not update for more than 1.5 frames.
        $dupPct = if ($frames -gt 0) { [math]::Round(100.0 * $dup / $frames, 2) } else { 100 }
        $gaps = if ($videoStart -and $null -ne $scenarioStartQpc -and $null -ne $scenarioEndQpc) {
            Get-InputGaps $ffLog ([long]((Convert-QpcToNs ([long]$scenarioStartQpc) $qpcFreq) - $videoStart.t_ns) / 1000) ([long]((Convert-QpcToNs ([long]$scenarioEndQpc) $qpcFreq) - $videoStart.t_ns) / 1000)
        } else { Get-InputGaps $ffLog }
        $durDiff = if ($null -ne $capSpan) { [math]::Round($vdur - $capSpan, 3) } else { $null }
        $checks.video = [ordered]@{
            ok = ($frames -gt 0 -and $dupPct -le 1.0 -and $null -ne $durDiff -and $durDiff -lt 0.5 -and $durDiff -gt -0.5 -and $cover -ne $false)
            codec = $st.codec_name; profile = $st.profile; pix_fmt = $st.pix_fmt
            width = $st.width; height = $st.height; avg_frame_rate = $st.avg_frame_rate
            duration_s = $vdur; frames = $frames; dup_frames = $dup; dup_pct = $dupPct; surplus_input_frames_dropped = $drop; input = $gaps
            capture_span_s = $capSpan; duration_diff_s = $durDiff; covers_scenario = $cover
        }
        if ($frames -eq 0) { [void]$problems.Add('video has no frames') }
        if ($st.width -ne 1920 -or $st.height -ne 1080) { [void]$problems.Add("video is $($st.width)x$($st.height)") }
        if ($dupPct -gt 5.0) { [void]$problems.Add("ffmpeg duplicated $dupPct % of output frames (no new image)") }
        elseif ($dupPct -gt 1.0) { [void]$warnings.Add("ffmpeg duplicated $dupPct % of output frames (no new image)") }
        if ($gaps -and $gaps.missed_pct -gt 2.0) { [void]$warnings.Add("capture input had gaps worth $($gaps.missed_pct) % of frames") }
        # Longer than the span means the start-time estimate is wrong; shorter means no new desktop images arrived
        # before the stop (event-driven capture cannot extend past its last image).
        if ($null -ne $durDiff -and $durDiff -ge 0.5) { [void]$problems.Add("video duration $vdur s exceeds capture span $capSpan s (clock mismatch)") }
        elseif ($null -ne $durDiff -and $durDiff -le -2.0) { [void]$problems.Add("video ends $(-$durDiff) s before the end of the capture") }
        elseif ($null -ne $durDiff -and $durDiff -le -0.5) { [void]$warnings.Add("video ends $(-$durDiff) s before the end of the capture") }
        # frames / duration_s is the gameplay fps (contract section 5: both count scenario_start..scenario_end)
        $oFrames = Get-Prop $outcome 'frames'; $oDur = Get-Prop $outcome 'duration_s'
        if ($oFrames -and $oDur -and [double]$oDur -gt 0) {
            $gameFps = [math]::Round([double]$oFrames / [double]$oDur, 2)
            $checks.video.game_fps = $gameFps
            if ($gameFps -lt 55) { [void]$warnings.Add("game averaged $gameFps fps (cap 60)") }
        }
    }
    # (a move fails a screen-region capture only: window capture follows the window)
    $checks.process = [ordered]@{ ok = (-not $killed -and $gameExit -eq 0 -and -not ($windowMoved -and $captureMode -ne 'gfxcapture')); exit_code = $gameExit; killed = $killed; window_moved = $windowMoved; capture = $captureMode }
    $checks.watchdog = [ordered]@{ ok = (-not $watchdog -or ((Get-Prop $watchdog 'reason') -eq 'shutdown' -and $outcome)); reason = (Get-Prop $watchdog 'reason') }

    $status = if ($problems.Count -gt 0) { 'failed' } elseif ($warnings.Count -gt 0) { 'warn' } else { 'ok' }

    # ---- stills for README screenshots (runs whose video is valid); never changes the run's status ----
    $stills = $null
    if ($status -in @('ok', 'warn')) {
        $stills = Export-RunStills $runDir $runId (Join-Path (Join-Path $RecordingsRoot $Game) '_stills')
        if ($stills.error) { Write-Step "WARNING: stills not extracted: $($stills.error)" } else { Write-Step "$($stills.count) stills -> $runDir\stills" }
    }

    # ---- gameplay.mp4 for the dataset's Gameplay/ (ok/warn runs: video and audio both valid); never changes the status ----
    $gameplayMp4 = $null
    if ($status -in @('ok', 'warn')) {
        $gameplayMp4 = Export-GameplayMp4 $runDir $(if ($videoStart) { $videoStart.t_ns } else { $null }) $(if ($audioAligned) { $audioStartNs } else { $null })
        if ($gameplayMp4.error) { Write-Step "WARNING: gameplay.mp4 not written: $($gameplayMp4.error)" }
        else { Write-Step ("gameplay.mp4: {0:N1} s, audio offset {1} s" -f $gameplayMp4.duration_s, $gameplayMp4.audio_offset_s) }
    }

    # ---- metadata, manifest ----
    $videoStartNs = if ($videoStart) { $videoStart.t_ns } else { $null }
    $gameSamples = @(@(Get-Prop $gameClock 'samples') | Where-Object { $_ } | ForEach-Object { $_ | Add-Member -NotePropertyName source -NotePropertyValue 'game' -PassThru -Force })
    $metadata = [ordered]@{
        schema = 'unity-autoplay-bundle/v1'
        lab_bundle_schema = 3
        run_id = $runId; game = $Game; project = $projectName
        scenario = $Scenario; scenario_name = (Get-Prop $outcome 'scenario_name')
        seed = $runSeed; skill = $runSkill; max_seconds = $MaxSeconds
        output_fps = $OutputFps; extra_args = $(if ($ExtraArgs) { $ExtraArgs } else { $null }); capture_notes = $(if ($CaptureNote) { $CaptureNote } else { $null })
        result = (Get-Prop $outcome 'result'); score = (Get-Prop $outcome 'score')
        player = [ordered]@{ kind = 'bot'; name = 'autoplay'; input_injection = 'Unity Input System (virtual devices, state events)' }
        build = [ordered]@{ commit = $buildInfo.commit; short_sha = $buildInfo.short_sha; config = (Get-Prop $buildInfo 'config'); backend = (Get-Prop $buildInfo 'backend'); unity_version = (Get-Prop $buildInfo 'unity_version'); path = $Build; exe = $exe; autoplay_version = $autoplayVersion }
        clock = [ordered]@{
            source = 'QueryPerformanceCounter'; qpc_frequency = $qpcFreq; t_ns_definition = 'qpc * 1e9 / qpc_frequency'
            samples = @($gameSamples + @($clock))
        }
        video = [ordered]@{
            file = 'video.mkv'; codec = 'h264'; encoder = $Encoder; width = 1920; height = 1080; fps = $OutputFps; cfr = $true; audio = $false
            capture = $captureMode; capture_rect = $rect; window_title = $title
            ffmpeg_command = $(if ($cap) { $cap.Command } else { $null }); ffmpeg_version = $ffmpegVersion
            start_estimate = $videoStart; cut = $endCut
        }
        video_start_offset_ns = $videoStartNs
        video_start_offset_definition = 't_ns of video frame 0 on the QPC ns clock of inputs.jsonl / telemetry.jsonl: video_time_s = (t_ns - video_start_offset_ns) / 1e9'
        system_audio = [ordered]@{ file = 'system_audio.mka'; codec = 'flac'; source = 'AutoPlay audio tap (OnAudioFilterRead on the AudioListener, audio_clock.jsonl)'; start_offset_ns = $audioStartNs; start_anchor = $audioAnchor; aligned = $audioAligned; clock = $audioClockInfo; stats = $audio }
        microphone = $null
        machine = [ordered]@{ cpu = (@(Get-CimInstance Win32_Processor | ForEach-Object { $_.Name.Trim() }) -join '; '); gpu = (@(Get-CimInstance Win32_VideoController | Where-Object { $_.CurrentHorizontalResolution -gt 0 } | ForEach-Object { $_.Name }) -join '; '); display = $displayMode; display_refresh_hz = $refreshHz; os = [Environment]::OSVersion.VersionString }
        created_utc = (Get-Date).ToUniversalTime().ToString('o')
        status = $status
        stills = $stills
        gameplay_mp4 = $gameplayMp4
    }
    Write-JsonFile (Join-Path $runDir 'metadata.json') $metadata
    $validation = [ordered]@{ run_id = $runId; status = $status; problems = @($problems); warnings = @($warnings); checks = $checks; game_exit_code = $gameExit; killed = $killed }
    Write-JsonFile (Join-Path $runDir 'validation.json') $validation
    if ($status -eq 'failed') { [System.IO.File]::WriteAllText((Join-Path $runDir 'FAILED'), (($problems -join "`n") + "`n"), $Utf8NoBom) }
    Write-BundleManifest $runDir $runId

    $tEnd = Get-Date
    $row = [ordered]@{
        schema = 'unity-run/v1'; run_id = $runId; game = $Game; scenario = $Scenario; scenario_name = (Get-Prop $outcome 'scenario_name'); seed = $runSeed; skill = $runSkill
        build_commit = $buildInfo.commit; build_path = $Build; status = $status
        result = $metadata.result; score = $metadata.score; duration_s = (Get-Prop $outcome 'duration_s')
        start = $tStart.ToString('o'); end = $tEnd.ToString('o'); wall_s = [math]::Round(($tEnd - $tStart).TotalSeconds, 1)
        capture = $captureMode; video_start_offset_ns = $videoStartNs
        dup_pct = $(if ($checks.Contains('video')) { $checks.video.dup_pct } else { $null })
        problems = @($problems); warnings = @($warnings); bundle = $runDir
    }
    Add-JsonLine (Join-Path $info.LogDir 'runs.jsonl') $row
    Write-Step ("{0}: {1} ({2}){3}" -f $runId, $status, $metadata.result, $(if ($problems.Count) { ' - ' + ($problems -join '; ') } else { '' }))
    [void]$results.Add($row)
}
$results
if (@($results | Where-Object { $_.status -eq 'failed' }).Count -gt 0) { exit 1 }
