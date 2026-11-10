# Shared helpers for build.ps1 / record.ps1 / pipeline.ps1 and the run tools. Dot-source it. Windows PowerShell 5.1
# compatible.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

# Machine root (UGF_ROOT env, else the config file, else %USERPROFILE%\UnityWork): see machine/lib/ugf-root.ps1.
. (Join-Path $PSScriptRoot '..\..\machine\lib\ugf-root.ps1')
$script:UGFConfig     = Get-UGFConfig
$script:WorkRoot      = $UGFConfig.root
$script:GamesRoot     = Join-Path $WorkRoot 'games'
$script:BuildsRoot    = Join-Path $WorkRoot 'builds'
$script:RecordingsRoot = Join-Path $WorkRoot 'recordings'
$script:LogRoot       = Join-Path $WorkRoot '.recording'
# Private build clones live outside the user profile: a player carries the folder it was built in (IL2CPP's and the
# linker's debug-symbol paths, Burst's debug information), so a clone under C:\Users\<name> ships the user name. Short to
# stay clear of the 260-character paths Unity fails past.
$script:SrcRoot       = Join-Path $UGFConfig.ugb 'src'   # default C:\UGB\src
# Temp dir for the build: the compiler and linker record their response-file and object paths under %TEMP%.
$script:BuildTempRoot = Join-Path $UGFConfig.ugb 'tmp'
# The job limiter every heavy job goes through: this checkout's copy (it finds ugf-root.ps1 in ..\lib), so the pipeline
# and the limiter it calls are always the same version; the installed <root>\tools copy takes the same machine-wide slots.
$script:Heavy         = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\machine\tools\unity-heavy.ps1'))
# The user name as it leaks: inside paths (C:\Users\<name>\...). A bare-name search also hits unrelated strings that
# merely contain it.
$script:UserNamePatterns = @("\$($env:USERNAME)\", "/$($env:USERNAME)/")
# Names that must not be in shipped files (warned about by build.ps1; the packager blocks on them).
$script:ForbiddenNamePatterns = @('superposition', 'game-factory', 'game_factory', 'gamefactory', 'game factory', 'claude', 'anthropic', 'openai')
$script:LockPath      = Join-Path $BuildsRoot '_pipeline.lock'
$script:Utf8NoBom     = New-Object System.Text.UTF8Encoding $false
$script:Inv           = [Globalization.CultureInfo]::InvariantCulture

function Write-Step([string]$Message) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message)
}

function Get-IsoNow { (Get-Date).ToString('o') }

function Add-JsonLine([string]$Path, $Object) {
    $dir = Split-Path $Path -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    $line = ($Object | ConvertTo-Json -Compress -Depth 12) + "`n"
    [System.IO.File]::AppendAllText($Path, $line, $Utf8NoBom)
}

function Write-JsonFile([string]$Path, $Object) {
    [System.IO.File]::WriteAllText($Path, ($Object | ConvertTo-Json -Depth 12) + "`n", $Utf8NoBom)
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return [System.IO.File]::ReadAllText($Path, $Utf8NoBom) | ConvertFrom-Json
}

# A property of a parsed JSON object (or a dictionary), $null when it has none: strict mode refuses a missing property.
function Get-Prop($Obj, [string]$Name) {
    if ($null -eq $Obj) { return $null }
    if ($Obj -is [System.Collections.IDictionary]) { if ($Obj.Contains($Name)) { return $Obj[$Name] } else { return $null } }
    if ($Obj.PSObject.Properties.Name -contains $Name) { return $Obj.$Name } else { return $null }
}

# ---- one heavy job at a time ---------------------------------------------------------------------------------------
# An exclusively opened lock file: the OS releases it if the process dies, and it works across sessions
# (Task Scheduler, other terminals). Holder details are in _pipeline-<game>.lock.json.

$script:LockStream = $null

# Per-game lock: a build and a recording of the same game share its clone, build folder and _run copy, so they exclude
# each other; different games only share the machine, which unity-heavy's general slots and the GPU slots already ration.
function Enter-PipelineLock([string]$Job, [string]$Game, [int]$TimeoutMinutes = 720) {
    if (-not (Test-Path $BuildsRoot)) { New-Item -ItemType Directory -Force $BuildsRoot | Out-Null }
    $LockPath = if ($Game) { Join-Path $BuildsRoot "_pipeline-$Game.lock" } else { $script:LockPath }
    $script:HeldLockPath = $LockPath
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $announced = $false
    while ($true) {
        try {
            $script:LockStream = [System.IO.File]::Open($LockPath, 'OpenOrCreate', 'ReadWrite', 'None')
            Write-JsonFile "$LockPath.json" ([ordered]@{ pid = $PID; job = $Job; since = (Get-IsoNow); host = $env:COMPUTERNAME })
            return
        } catch [System.IO.IOException] {
            if (-not $announced) {
                $holder = $null; try { $holder = Read-JsonFile "$LockPath.json" } catch { }
                Write-Step "waiting for the $(if ($Game) { "$Game " })pipeline lock (held by: $(if ($holder) { "$($holder.job), pid $($holder.pid), since $($holder.since)" } else { 'unknown' }))"
                $announced = $true
            }
            if ((Get-Date) -gt $deadline) { throw "timed out waiting for the pipeline lock $LockPath" }
            Start-Sleep -Seconds 5
        }
    }
}

function Exit-PipelineLock {
    if ($script:LockStream) {
        $script:LockStream.Dispose()
        $script:LockStream = $null
        Remove-Item "$($script:HeldLockPath).json" -ErrorAction SilentlyContinue
    }
}

# ---- games ----------------------------------------------------------------------------------------------------------

function Get-GameInfo([string]$Game) {
    $dir = Join-Path $GamesRoot $Game
    if (-not (Test-Path $dir)) { throw "no game directory $dir" }
    if (-not (Test-Path (Join-Path $dir 'ProjectSettings\ProjectVersion.txt'))) { throw "$dir is not a Unity project (no ProjectSettings\ProjectVersion.txt)" }
    $bp = Get-PlayerBuildInfo $dir
    return [pscustomobject]@{
        Slug = $Game; Dir = $dir; ProjectName = $bp.ProjectName; BuildMethod = $bp.Method
        LogDir = (Join-Path $LogRoot $Game)
    }
}

# The game's player build is the template's Assets/Editor/Tools/BuildPlayer.cs, as Scripts/unity.ps1 build runs it: its
# namespace names the method (<Project>.EditorTools.BuildPlayer.BuildWindows) and it writes <Project>.exe. Every game
# made from the template has it, so games started before the pipeline existed build the same way.
function Get-PlayerBuildInfo([string]$ProjectDir) {
    $f = Join-Path $ProjectDir 'Assets\Editor\Tools\BuildPlayer.cs'
    if (-not (Test-Path -LiteralPath $f)) { throw "no Assets\Editor\Tools\BuildPlayer.cs in $ProjectDir (the template's player build; Scripts/unity.ps1 build runs it)" }
    $text = [IO.File]::ReadAllText($f)
    if ($text -notmatch '(?m)^\s*namespace\s+([A-Za-z_][\w.]*)') { throw "$f declares no namespace" }
    $ns = $Matches[1]
    if ($text -notmatch '"([A-Za-z_]\w*)\.exe"') { throw "$f names no <Project>.exe" }
    return [pscustomobject]@{ ProjectName = $Matches[1]; Method = "$ns.BuildPlayer.BuildWindows" }
}

# m_EditorVersion of a project's ProjectSettings\ProjectVersion.txt ("6000.3.28f1"); '' without one.
function Get-ProjectUnityVersion([string]$ProjectDir) {
    $pv = Join-Path $ProjectDir 'ProjectSettings\ProjectVersion.txt'
    if (-not (Test-Path -LiteralPath $pv)) { return '' }
    foreach ($l in [IO.File]::ReadAllLines($pv)) { if ($l -match '^\s*m_EditorVersion:\s*(\S+)') { return $Matches[1] } }
    return ''
}

# Which AutoPlay drop-in a project ships: the version constant in its AutoPlay*.cs (under Assets\, or an embedded
# package under Packages\); $null when it has none.
function Get-AutoPlayVersion([string]$ProjectDir) {
    foreach ($d in 'Assets', 'Packages') {
        $root = Join-Path $ProjectDir $d
        if (-not (Test-Path -LiteralPath $root)) { continue }
        foreach ($f in @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter 'AutoPlay*.cs' -ErrorAction SilentlyContinue)) {
            $t = [IO.File]::ReadAllText($f.FullName)
            if ($t -match '\bconst\s+int\s+(?:Version|AutoPlayVersion|ContractVersion)\s*=\s*(\d+)') { return [int]$Matches[1] }
        }
    }
    return $null
}

function Invoke-Git([string]$Dir, [string[]]$GitArgs, [switch]$AllowFail) {
    # PowerShell 5.1 turns native stderr into terminating errors under 'Stop'; run git under 'Continue'.
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & git -C $Dir @GitArgs 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $eap }
    if ($code -ne 0 -and -not $AllowFail) { throw "git $($GitArgs -join ' ') failed in ${Dir}: $($out -join ' ')" }
    return $out
}

# Where a repository keeps its Git LFS objects: its lfs.storage, else <git common dir>\lfs\objects.
function Get-LfsStore([string]$Repo) {
    $storage = "$(Invoke-Git $Repo @('config', '--get', 'lfs.storage') -AllowFail)".Trim()   # empty when unset
    $common = "$(Invoke-Git $Repo @('rev-parse', '--git-common-dir'))".Trim()
    if (-not [IO.Path]::IsPathRooted($common)) { $common = Join-Path $Repo $common }
    if ($storage) {
        $base = if ([IO.Path]::IsPathRooted($storage)) { $storage } else { Join-Path $common $storage }
        if (Test-Path -LiteralPath (Join-Path $base 'objects')) { return (Join-Path $base 'objects') }
        return $base
    }
    return (Join-Path $common 'lfs\objects')
}

# ---- processes ------------------------------------------------------------------------------------------------------

function Write-HeavyLog([string]$Event, [string]$Label, $Extra) {
    # the row as unity-heavy.ps1 writes it: invariant-culture time (a time in another culture's format does not parse),
    # appends serialised by the same named mutex
    $row = [ordered]@{ time = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffzzz', $Inv); event = $Event; label = $Label; pid = $PID; cwd = (Get-Location).Path }
    if ($Extra) { foreach ($k in $Extra.Keys) { $row[$k] = $Extra[$k] } }
    try {
        $path = Join-Path $LogRoot '_heavy-jobs.jsonl'
        if (-not (Test-Path $LogRoot)) { New-Item -ItemType Directory -Force $LogRoot | Out-Null }
        $line = ($row | ConvertTo-Json -Compress) + "`n"
        $m = New-Object Threading.Mutex($false, 'Global\ugf-heavy-log')
        [void](Enter-UGFMutex $m 10000)
        try { [IO.File]::AppendAllText($path, $line, $Utf8NoBom) } finally { try { $m.ReleaseMutex() } catch { } }
    } catch { }   # shared file; never fail a build or a run over it
}

# One job through the machine-wide limiter (unity-heavy.ps1: a general slot, and a GPU slot as well for a job that
# renders), the way every game's Scripts/unity.ps1 runs Unity. Returns the job's exit code (125: the limiter could not
# run it). The limiter's own lines (waiting for a slot) are printed. Strict mode is off for the call: it would carry
# into the limiter's script, which reads job-log rows that lack some fields.
function Invoke-Heavy([string]$Label, [string[]]$Command, [switch]$Gpu) {
    Set-StrictMode -Off
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try {
        # named parameters written out: an array splat would hand "-Label" to the command list
        if ($Gpu) { & $Heavy -Label $Label -Gpu -- @Command *>&1 | ForEach-Object { if ("$_".Trim()) { Write-Host "  $_" } } }
        else { & $Heavy -Label $Label -- @Command *>&1 | ForEach-Object { if ("$_".Trim()) { Write-Host "  $_" } } }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $eap }
    if ($null -eq $code) { return 125 }
    return $code
}

# A command line as Windows programs read it (the limiter quotes the same way): an argument with a space or a quote in
# quotes, backslashes before a quote doubled.
function Format-CommandLine([string[]]$Command) {
    ($Command | ForEach-Object {
        $a = [string]$_
        if ($a -and $a -notmatch '[\s"]') { $a } else { '"' + (($a -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"' }
    }) -join ' '
}

# ---- the machine-wide GPU slots (a recording has the GPU to itself) ----------------------------------------------------
# The same named mutexes unity-heavy.ps1 takes for every rendering job (a player, the editor without -nographics).

# Recordings get priority: while a recording waits, builds\_queue\_recording-wants-gpu exists (refreshed every minute)
# and unity-heavy.ps1 holds back new session GPU jobs while it is under 20 min old. Removed once the slots are held.
$script:RecordingWantsGpuFlag = Join-Path $BuildsRoot '_queue\_recording-wants-gpu'
function Set-RecordingWantsGpu([string]$Label) {
    try {
        New-Item -ItemType Directory -Force (Split-Path $RecordingWantsGpuFlag) | Out-Null
        Set-Content -Path $RecordingWantsGpuFlag -Value "$((Get-Date).ToString('o')) pid $PID $Label" -Encoding ASCII
    } catch { }
}
function Clear-RecordingWantsGpu {
    if (('UnityPipeline.FlagKeeper' -as [type]) -and [UnityPipeline.FlagKeeper]::Active) { return }   # the drainer holds it for the job
    try { if (Test-Path $RecordingWantsGpuFlag) { Remove-Item -Force $RecordingWantsGpuFlag } } catch { }
}
# The queue drainer holds the flag for a whole job (first build step to the end of the last run, and between jobs),
# so no session GPU job slips in between runs. A thread-pool timer rewrites it every 60 s while PowerShell is busy.
if (-not ('UnityPipeline.FlagKeeper' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Threading;
namespace UnityPipeline {
    public static class FlagKeeper {
        static Timer timer; static string path; static string text;
        public static bool Active { get { return timer != null; } }
        static void Write(object _) { try { Directory.CreateDirectory(Path.GetDirectoryName(path)); File.WriteAllText(path, DateTime.Now.ToString("o") + " " + text); } catch { } }
        public static void Start(string flagPath, string label) {
            lock (typeof(FlagKeeper)) { path = flagPath; text = label; if (timer == null) timer = new Timer(Write, null, 0, 60000); else Write(null); }
        }
        public static void Stop() {
            lock (typeof(FlagKeeper)) {
                if (timer != null) { timer.Dispose(); timer = null; }
                try { if (path != null && File.Exists(path)) File.Delete(path); } catch { }
            }
        }
    }
}
'@
}
# Per-scenario AutoPlay time limits. Spec: "" (default 600 s for all), "900" (all), "1=300,3=900" (listed scenarios; the
# rest 600, or "*=700" for the rest), or the {"1":300,"*":700} object a queue job stores. Returns a hashtable keyed "1","*".
function ConvertTo-MaxSecondsMap($Spec) {
    $map = @{ '*' = 600 }
    $pairs = @()
    if ($Spec -is [string] -or $null -eq $Spec) {
        foreach ($part in @("$Spec" -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
            if ($part -match '^\d+$') { $pairs += , @('*', $part) }
            elseif ($part -match '^(\d+|\*)\s*=\s*(\d+)$') { $pairs += , @($matches[1], $matches[2]) }
            else { throw "bad -MaxSeconds part '$part' (use 900 or 1=300,3=900)" }
        }
    } else { foreach ($p in $Spec.PSObject.Properties) { $pairs += , @([string]$p.Name, [string]$p.Value) } }
    foreach ($kv in $pairs) {
        $s = [int]$kv[1]
        if ($s -lt 30 -or $s -gt 7200) { throw "MaxSeconds $s for scenario $($kv[0]) is outside 30..7200" }
        $map[[string]$kv[0]] = $s
    }
    return $map
}
function Get-MaxSeconds($Map, $Scenario) { if ($Map.ContainsKey("$Scenario")) { return [int]$Map["$Scenario"] } else { return [int]$Map['*'] } }

function Start-RecordingWantsGpuHold([string]$Label) { [UnityPipeline.FlagKeeper]::Start($RecordingWantsGpuFlag, "pid $PID $Label") }
# Also removes a flag this process did not write: a drainer that took over after a code change (hand-over) and found
# the queue empty would otherwise leave the old drainer's flag, holding session GPU jobs back for 20 min.
function Stop-RecordingWantsGpuHold {
    [UnityPipeline.FlagKeeper]::Stop()
    try { if (Test-Path $RecordingWantsGpuFlag) { Remove-Item -Force $RecordingWantsGpuFlag } } catch { }
}

# GPU slots: Global\ue-gpu-slot-<n>, "gpu_slots" in the machine config, else the hardware formula (ugf-root.ps1
# Get-UGFSlotPlan), one per session GPU job (unity-heavy.ps1). A recording takes ALL of them, so a capture has the GPU
# to itself. Slots are collected as running GPU jobs end; the recording-wants-gpu flag keeps new session GPU jobs from
# taking freed ones. Mutexes: a recorder killed mid-run leaves its slots abandoned, and the next taker gets them.
function Get-GpuSlotCount { return [math]::Min(8, [int](Get-UGFSlotPlan $UGFConfig).gpu_slots) }

function Enter-GpuSlot([string]$Label, [switch]$Recording) {
    $n = Get-GpuSlotCount
    $mx = Get-UGFSlotMutexes gpu $n
    $t0 = Get-Date
    Write-HeavyLog 'wait' $Label @{ gpu = $true; gpu_slots = $(if ($Recording) { $n } else { 1 }); slots = 'mutex' }
    $said = $false
    $held = New-Object Collections.Generic.List[int]
    try {
        if ($Recording) { Set-RecordingWantsGpu $Label }
        while ($true) {
            if ($Recording) {
                for ($i = 0; $i -lt $n; $i++) { if (-not $held.Contains($i) -and (Enter-UGFMutex $mx[$i] 0)) { $held.Add($i) } }
                if ($held.Count -eq $n) { break }
            } else {
                $i = Enter-UGFSlot $mx
                if ($i -ge 0) { $held.Add($i); break }
            }
            if ($Recording) { Set-RecordingWantsGpu $Label }
            if (-not $said) { Write-Step "[gpu] waiting for $(if ($Recording) { "all $n GPU slots ($($held.Count) held)" } else { 'a GPU slot' }) since $($t0.ToString('HH:mm:ss'))$(if ($Recording) { '; recording priority flag set' })"; $said = $true }
            Start-Sleep -Seconds 3
        }
    } catch {
        foreach ($i in $held) { Exit-UGFSlot $mx $i }
        throw
    } finally { if ($Recording) { Clear-RecordingWantsGpu } }
    Write-HeavyLog 'start' $Label @{ gpu = $true; gpu_slots = $held.Count; slot = -1; gpu_slot = @($held); waited_s = [int]((Get-Date) - $t0).TotalSeconds }
    return [pscustomobject]@{ Mutexes = $mx; Held = @($held); Label = $Label; Since = Get-Date }
}

function Exit-GpuSlot($Slot) {
    if (-not $Slot) { return }
    foreach ($i in $Slot.Held) { Exit-UGFSlot $Slot.Mutexes $i }
    Write-HeavyLog 'end' $Slot.Label @{ gpu = $true; duration_s = [int]((Get-Date) - $Slot.Since).TotalSeconds; slots = 'mutex' }
}

function Get-VramUsedMB {
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $v = & nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1 } catch { $v = $null } finally { $ErrorActionPreference = $eap }
    if ("$v".Trim() -match '^\d+$') { return [int]"$v".Trim() } else { return $null }
}

function Get-VramTotalMB {
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $v = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null | Select-Object -First 1 } catch { $v = $null } finally { $ErrorActionPreference = $eap }
    if ("$v".Trim() -match '^\d+$') { return [int]"$v".Trim() } else { return $null }
}

function Wait-VramFree([string]$Label, [int]$MaxUsedMB = 4096, [int]$MaxMinutes = 120) {
    if ($MaxUsedMB -le 0) { $tot = Get-VramTotalMB; $MaxUsedMB = if ($tot) { [int]($tot / 2) } else { 8192 } }   # 0: half the GPU's VRAM
    # Per-process VRAM is N/A under WDDM, so this uses the total in use before our game starts (desktop ~1-4 GB).
    # Returns $true when below the limit, $false after MaxMinutes.
    $t0 = Get-Date; $next = $t0
    while ($true) {
        $used = Get-VramUsedMB
        if ($null -eq $used -or $used -le $MaxUsedMB) {
            if ((Get-Date) -gt $t0.AddSeconds(5)) { Write-HeavyLog 'vram_ok' $Label @{ gpu = $true; vram_used_mb = $used; waited_s = [int]((Get-Date) - $t0).TotalSeconds } }
            return $true
        }
        if ((Get-Date) -ge $next) {
            # the editor (Unity), players (an exe under a Build or builds folder) and capture
            $heavy = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '(?i)^Unity$|^ffmpeg$' -or "$($_.Path)" -match '(?i)\\(Build|Builds)\\' } | ForEach-Object { "$($_.ProcessName)($($_.Id))" } | Select-Object -First 8)
            Write-Step "[gpu] $used MB VRAM in use (limit $MaxUsedMB MB before launch): waiting. GPU-heavy processes: $(if ($heavy.Count) { $heavy -join ', ' } else { 'none recognised' })"
            Write-HeavyLog 'vram_wait' $Label @{ gpu = $true; vram_used_mb = $used; limit_mb = $MaxUsedMB; processes = ($heavy -join ', ') }
            $next = (Get-Date).AddMinutes(5)
        }
        if ((Get-Date) -gt $t0.AddMinutes($MaxMinutes)) { return $false }
        Start-Sleep -Seconds 30
    }
}

# The first lines of a failed Unity log that say why (compiler errors, exceptions, a failed build row, the licence),
# else its last 15 lines. Not every line with "error": a licensed editor logs Licensing errors on every run.
function Get-ErrorExcerpt([string]$LogPath, [int]$MaxLines = 25) {
    if (-not (Test-Path $LogPath)) { return '' }
    $pattern = '(error CS\d+|\w+Exception: |Aborting batchmode|Scripts have compiler errors|executeMethod .* could not be found|another Unity instance|No valid Unity Editor license|\[workflow\] .*\(failed|Error building Player|Build Finished, Result: Failure|BuildFailedException|did not run properly|Fatal error|Unhandled Exception)'
    $lines = @(Select-String -Path $LogPath -Pattern $pattern -CaseSensitive:$false | Select-Object -First $MaxLines | ForEach-Object { $_.Line.Trim() })
    if ($lines.Count -eq 0) { $lines = @(Get-Content $LogPath -Tail 15) }
    $text = ($lines -join "`n")
    if ($text.Length -gt 4000) { $text = $text.Substring(0, 4000) }
    return $text
}

function Set-BelowNormalPriority {
    try { (Get-Process -Id $PID).PriorityClass = 'BelowNormal' } catch { }
}

function Find-FFmpeg {
    # Order: $env:UGF_FFMPEG, the pinned copy in <root>\tools\ffmpeg-8.1.2 (machine/get-ffmpeg.ps1), PATH, the winget package.
    if ($env:UGF_FFMPEG -and (Test-Path $env:UGF_FFMPEG)) { return $env:UGF_FFMPEG }
    # Pinned by the user's choice: gyan.dev ffmpeg 8.1.2 full build (SHA-256 in docs/unity-pipeline.md). Its NVENC needs NVIDIA driver >= 610.
    $pinned = Join-Path $WorkRoot 'tools\ffmpeg-8.1.2\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe'
    if (Test-Path $pinned) { return $pinned }
    $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $pkg = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    $hit = Get-ChildItem $pkg -Directory -Filter 'Gyan.FFmpeg*' -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ChildItem $_.FullName -Recurse -Filter ffmpeg.exe -File } | Select-Object -First 1
    if ($hit) { return $hit.FullName }
    throw "ffmpeg not found: run machine\get-ffmpeg.ps1 (the pinned 8.1.2 into $WorkRoot\tools)"
}

function Find-FFprobe {
    $ff = Find-FFmpeg
    $probe = Join-Path (Split-Path $ff) 'ffprobe.exe'
    if (Test-Path $probe) { return $probe }
    throw "ffprobe not found next to $ff"
}

# ---- Win32: windows, DPI, QPC/UTC clock pairs ------------------------------------------------------------------------

if (-not ('UnityPipeline.Win' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
namespace UnityPipeline {
public static class Win {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr v);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] static extern int GetSystemMetrics(int i);
    [DllImport("kernel32.dll")] static extern void GetSystemTimePreciseAsFileTime(out long ft);
    [DllImport("kernel32.dll")] static extern bool QueryPerformanceCounter(out long c);
    [DllImport("kernel32.dll")] static extern bool QueryPerformanceFrequency(out long f);

    public static bool MakeDpiAware() { return SetProcessDpiAwarenessContext(new IntPtr(-4)); } // per-monitor v2

    /// <summary>The first visible top-level window of the process whose title contains titleContains and whose window
    /// class is className (either empty: any; PowerShell passes $null as an empty string).</summary>
    public static IntPtr FindWindowOfPid(uint pid, string titleContains, string className) {
        IntPtr found = IntPtr.Zero;
        EnumWindows((h, l) => {
            uint p; GetWindowThreadProcessId(h, out p);
            if (p != pid || !IsWindowVisible(h)) return true;
            if (!string.IsNullOrEmpty(titleContains) && !Title(h).Contains(titleContains)) return true;
            if (!string.IsNullOrEmpty(className) && ClassOf(h) != className) return true;
            found = h; return false;
        }, IntPtr.Zero);
        return found;
    }
    public static string Title(IntPtr h) { var sb = new StringBuilder(512); GetWindowText(h, sb, 512); return sb.ToString(); }
    public static string ClassOf(IntPtr h) { var sb = new StringBuilder(256); GetClassName(h, sb, 256); return sb.ToString(); }
    /// <summary>Client area in physical screen pixels: x, y, width, height.</summary>
    public static int[] ClientRectOnScreen(IntPtr h) {
        RECT r; if (!GetClientRect(h, out r)) return null;
        POINT p = new POINT(); if (!ClientToScreen(h, ref p)) return null;
        return new int[] { p.X, p.Y, r.Right - r.Left, r.Bottom - r.Top };
    }
    public static bool SetTopmost(IntPtr h, bool on) {
        // SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        return SetWindowPos(h, new IntPtr(on ? -1 : -2), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010);
    }
    public static int[] PrimaryScreenSize() { return new int[] { GetSystemMetrics(0), GetSystemMetrics(1) }; }
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
    [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint flags);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    /// <summary>True when a 5x5 grid of points over the client area all hit this window (nothing covers it).</summary>
    public static bool IsClientUncovered(IntPtr h) {
        int[] c = ClientRectOnScreen(h); if (c == null) return false;
        for (int i = 0; i < 5; i++) for (int j = 0; j < 5; j++) {
            POINT p = new POINT(); p.X = c[0] + 4 + (c[2] - 8) * i / 4; p.Y = c[1] + 4 + (c[3] - 8) * j / 4;
            if (GetAncestor(WindowFromPoint(p), 2) != h) return false;   // GA_ROOT
        }
        return true;
    }
    [DllImport("user32.dll")] static extern short GetAsyncKeyState(int vk);
    [StructLayout(LayoutKind.Sequential)] struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO lii);
    [DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint flags);
    /// <summary>Milliseconds since the last real keyboard/mouse input in this session (the bot's Input System events don't count).</summary>
    public static uint IdleMs() { var l = new LASTINPUTINFO(); l.cbSize = 8; GetLastInputInfo(ref l); return (uint)Environment.TickCount - l.dwTime; }
    /// <summary>Keep the display and system awake while recording (ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED); false = release.</summary>
    public static void KeepDisplayOn(bool on) { SetThreadExecutionState(on ? 0x80000003u : 0x80000000u); }
    /// <summary>True while the left or right mouse button is held (a window move then is most likely a user drag).</summary>
    public static bool MouseButtonDown() { return (GetAsyncKeyState(0x01) & 0x8000) != 0 || (GetAsyncKeyState(0x02) & 0x8000) != 0; }
    /// <summary>Describes the first window found over the client area ("" when uncovered): title, class, process id.</summary>
    public static string CoveringWindow(IntPtr h) {
        int[] c = ClientRectOnScreen(h); if (c == null) return "no client rect";
        for (int i = 0; i < 5; i++) for (int j = 0; j < 5; j++) {
            POINT p = new POINT(); p.X = c[0] + 4 + (c[2] - 8) * i / 4; p.Y = c[1] + 4 + (c[3] - 8) * j / 4;
            IntPtr root = GetAncestor(WindowFromPoint(p), 2);
            if (root != h) {
                uint pid; GetWindowThreadProcessId(root, out pid);
                string exe = "?"; try { exe = System.Diagnostics.Process.GetProcessById((int)pid).ProcessName; } catch { }
                return "'" + Title(root) + "' class " + ClassOf(root) + " process " + exe + " (pid " + pid + ") at " + p.X + "," + p.Y;
            }
        }
        return "";
    }
    /// <summary>Move the window so its client area's top-left lands at (x, y); size and z-order unchanged.</summary>
    public static bool MoveClientTo(IntPtr h, int x, int y) {
        RECT w; if (!GetWindowRect(h, out w)) return false;
        int[] c = ClientRectOnScreen(h); if (c == null) return false;
        return SetWindowPos(h, IntPtr.Zero, w.Left + (x - c[0]), w.Top + (y - c[1]), 0, 0, 0x0001 | 0x0004 | 0x0010);   // NOSIZE|NOZORDER|NOACTIVATE
    }
    public static long QpcFrequency() { long f; QueryPerformanceFrequency(out f); return f; }
    public static long Qpc() { long c; QueryPerformanceCounter(out c); return c; }
    /// <summary>QPC before, UTC as FILETIME (100 ns since 1601), QPC after.</summary>
    public static long[] ClockPair() { long q0, q1, ft; QueryPerformanceCounter(out q0); GetSystemTimePreciseAsFileTime(out ft); QueryPerformanceCounter(out q1); return new long[] { q0, ft, q1 }; }
}
}
'@
}

function Get-ClockSample([string]$Label) {
    $pair = [UnityPipeline.Win]::ClockPair()
    $f = [UnityPipeline.Win]::QpcFrequency()
    $utc = [DateTime]::FromFileTimeUtc($pair[1])
    $unixNs = ($pair[1] - 116444736000000000) * 100
    return [ordered]@{
        label = $Label; source = 'pipeline'; qpc = $pair[0]; qpc_after = $pair[2]; t_ns = (Convert-QpcToNs $pair[0] $f)
        unix_ns = $unixNs; utc = $utc.ToString('yyyy-MM-ddTHH:mm:ss.fffffffZ', $Inv)
    }
}

function Convert-QpcToNs([long]$Qpc, [long]$Freq) {
    return [long]([math]::Floor($Qpc / $Freq)) * 1000000000 + [long](($Qpc % $Freq) * 1000000000 / $Freq)
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Invoke-Native([string]$Exe, [string[]]$NativeArgs) {
    # Runs a native tool capturing stdout only; stderr is discarded without tripping ErrorActionPreference=Stop.
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { return (& $Exe @NativeArgs 2>$null) } finally { $ErrorActionPreference = $eap }
}

# The manifest of a bundle: sha256 + bytes of every file in it but manifest.json itself (raw\ and stills\ included).
function Write-BundleManifest([string]$RunDir, [string]$RunId) {
    $files = [ordered]@{}
    foreach ($f in Get-ChildItem -LiteralPath $RunDir -Recurse -File | Where-Object { $_.Name -ne 'manifest.json' } | Sort-Object FullName) {
        $rel = $f.FullName.Substring($RunDir.TrimEnd('\').Length + 1).Replace('\', '/')
        $files[$rel] = [ordered]@{ sha256 = (Get-FileSha256 $f.FullName); bytes = $f.Length }
    }
    Write-JsonFile (Join-Path $RunDir 'manifest.json') ([ordered]@{ schema = 'manifest/v1'; run_id = $RunId; files = $files })
}

# Refresh the manifest entries of these bundle files (relative paths), others untouched; entries under -DropPrefix go
# first (files that were replaced as a set, such as stills/).
function Update-BundleManifest([string]$RunDir, [string[]]$RelPaths, [string]$DropPrefix = '') {
    $manPath = Join-Path $RunDir 'manifest.json'
    $man = Read-JsonFile $manPath
    if (-not $man) { return }
    $files = [ordered]@{}
    foreach ($p in $man.files.PSObject.Properties) { if (-not $DropPrefix -or -not $p.Name.StartsWith($DropPrefix)) { $files[$p.Name] = $p.Value } }
    foreach ($rel in $RelPaths) {
        $f = Get-Item -LiteralPath (Join-Path $RunDir $rel.Replace('/', '\'))
        $files[$rel] = [ordered]@{ sha256 = (Get-FileSha256 $f.FullName); bytes = $f.Length }
    }
    $man.files = $files
    Write-JsonFile $manPath $man
}

# README screenshots: $Count evenly spaced stills from a run's video.mkv (CPU decode, pinned ffmpeg) into
# <run>\stills\NN.jpg and recordings\<game>\_stills\<run_id>_NN.jpg. Never throws: errors come back in .error.
function Export-RunStills([string]$RunDir, [string]$RunId, [string]$GameStillsDir, [int]$Count = 8) {
    $result = [ordered]@{ count = 0; files = @(); copied_to = $GameStillsDir; error = $null }
    try {
        $video = Join-Path $RunDir 'video.mkv'
        if (-not (Test-Path $video)) { throw 'no video.mkv' }
        $ff = Find-FFmpeg; $fp = Find-FFprobe
        $durText = "$(Invoke-Native $fp @('-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', $video) | Select-Object -First 1)".Trim()
        $dur = 0.0
        if (-not [double]::TryParse($durText, [Globalization.NumberStyles]::Float, $Inv, [ref]$dur) -or $dur -le 0) { throw "could not read the video duration ('$durText')" }
        $dir = Join-Path $RunDir 'stills'
        New-Item -ItemType Directory -Force $dir | Out-Null
        New-Item -ItemType Directory -Force $GameStillsDir | Out-Null
        $files = New-Object System.Collections.ArrayList
        for ($i = 1; $i -le $Count; $i++) {
            $t = [math]::Round($dur * $i / ($Count + 1), 3)
            $out = Join-Path $dir ('{0:D2}.jpg' -f $i)
            $null = Invoke-Native $ff @('-hide_banner', '-loglevel', 'error', '-y', '-ss', $t.ToString($Inv), '-i', $video, '-frames:v', '1', '-q:v', '2', $out)
            if (-not (Test-Path $out) -or (Get-Item $out).Length -eq 0) { throw "ffmpeg wrote no still at $t s" }
            Copy-Item $out (Join-Path $GameStillsDir ('{0}_{1:D2}.jpg' -f $RunId, $i)) -Force
            [void]$files.Add([ordered]@{ file = ('stills/{0:D2}.jpg' -f $i); t_s = $t })
        }
        $result.files = @($files); $result.count = $files.Count
    } catch { $result.error = $_.Exception.Message }
    return $result
}

# Strings that must not ship (the Windows user name in compiled-in source and debug-symbol paths, ...): case-insensitive
# byte search for each pattern in ASCII and UTF-16LE across every file under $Dir. Returns one row per file and pattern.
if (-not ('UnityPipeline.ByteScan' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
namespace UnityPipeline {
    public static class ByteScan {
        // Counts matches of every ASCII pattern (case-insensitive) as 1-byte or 2-byte little-endian chars, in one read
        // of the file (a pass per pattern took minutes over an IL2CPP build's gigabyte of generated sources and symbols).
        // Returns { ascii, utf16 } per pattern; examples[k] is the first match's context.
        public static long[][] CountAll(string path, string[] patterns, out string[] examples) {
            int m = patterns.Length, maxLen = 1;
            byte[][] p = new byte[m][];
            var starts = new System.Collections.Generic.List<int>[256];   // patterns by their first byte
            for (int k = 0; k < m; k++) {
                p[k] = System.Text.Encoding.ASCII.GetBytes(patterns[k].ToLowerInvariant());
                if (p[k].Length == 0) continue;
                maxLen = Math.Max(maxLen, p[k].Length);
                if (starts[p[k][0]] == null) starts[p[k][0]] = new System.Collections.Generic.List<int>();
                starts[p[k][0]].Add(k);
            }
            long[][] counts = new long[m][]; for (int k = 0; k < m; k++) counts[k] = new long[2];
            examples = new string[m];
            int overlap = 2 * maxLen;
            byte[] buf = new byte[(1 << 22) + overlap]; int keep = 0;
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, 1 << 16)) {
                while (true) {
                    int read = fs.Read(buf, keep, buf.Length - keep);
                    int len = keep + read;
                    bool last = read == 0;
                    int limit = last ? len : len - overlap;   // only start matches that fit wholly in this window
                    if (limit < 0) limit = 0;                 // a short read (or a file shorter than the overlap): carry it all over
                    for (int i = 0; i < limit; i++) {
                        var cand = starts[Lower(buf[i])];
                        if (cand == null) continue;
                        foreach (int k in cand) {
                            byte[] q = p[k]; int n = q.Length;
                            if (i + n <= len) {
                                int j = 1; while (j < n && Lower(buf[i + j]) == q[j]) j++;
                                if (j == n) { counts[k][0]++; if (examples[k] == null) examples[k] = Context(buf, i, len); }
                            }
                            if (i + 2 * n <= len) {
                                int j = 0; while (j < n && Lower(buf[i + 2 * j]) == q[j] && buf[i + 2 * j + 1] == 0) j++;
                                if (j == n) { counts[k][1]++; if (examples[k] == null) examples[k] = Context(buf, i, len); }
                            }
                        }
                    }
                    if (last) break;
                    keep = len - limit; Buffer.BlockCopy(buf, limit, buf, 0, keep);
                }
            }
            return counts;
        }
        static byte Lower(byte b) { return (b >= 65 && b <= 90) ? (byte)(b + 32) : b; }
        static string Context(byte[] buf, int i, int len) {
            int s = Math.Max(0, i - 40), e = Math.Min(len, i + 60);
            var sb = new System.Text.StringBuilder();
            for (int j = s; j < e; j++) { byte b = buf[j]; if (b >= 32 && b < 127) sb.Append((char)b); else if (b != 0) sb.Append('.'); }
            return sb.ToString();
        }
    }
}
'@
}
function Find-LeakedStrings([string]$Dir, [string[]]$Patterns) {
    $Patterns = @($Patterns | Where-Object { $_ })
    if (-not $Patterns) { return }
    foreach ($f in @(Get-ChildItem -LiteralPath $Dir -Recurse -File -ErrorAction SilentlyContinue)) {
        $ex = $null
        $c = [UnityPipeline.ByteScan]::CountAll($f.FullName, [string[]]$Patterns, [ref]$ex)
        for ($k = 0; $k -lt $Patterns.Count; $k++) {
            if ($c[$k][0] + $c[$k][1] -gt 0) {
                [pscustomobject]@{ file = $f.FullName.Substring($Dir.TrimEnd('\').Length + 1); pattern = $Patterns[$k]; count = $c[$k][0] + $c[$k][1]; ascii = $c[$k][0]; utf16 = $c[$k][1]; example = $ex[$k] }
            }
        }
    }
}

# Wake the display before a recording. The power plan's display timeout can equal the 5-minute idle gate, so by the
# time the user counts as away the display is often already off; ES_DISPLAY_REQUIRED keeps a display on but doesn't
# turn one back on, and Desktop Duplication (ddagrab) gets no frames from a display that is off.
# A 1-pixel mouse move out and back is ordinary input that wakes it (outside any game run; the bot never uses it).
# Separate type from UnityPipeline.Win so a process that already loaded Win (the drainer) can still add this.
if (-not ('UnityPipeline.Display' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace UnityPipeline {
    public static class Display {
        [DllImport("kernel32.dll")] static extern uint SetThreadExecutionState(uint flags);
        [DllImport("user32.dll")] static extern void mouse_event(uint flags, int dx, int dy, uint data, UIntPtr extra);
        const uint MOUSEEVENTF_MOVE = 0x0001;
        public static void Wake() {
            SetThreadExecutionState(0x80000003u);   // ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            mouse_event(MOUSEEVENTF_MOVE, 1, 0, 0, UIntPtr.Zero);
            mouse_event(MOUSEEVENTF_MOVE, -1, 0, 0, UIntPtr.Zero);
        }
    }
}
'@
}
function Invoke-WakeDisplay([int]$SettleSeconds = 3) {
    [UnityPipeline.Display]::Wake()
    Start-Sleep -Seconds $SettleSeconds   # monitor power-up and the first DWM frames
}

# Dataset Gameplay/ file: <run>\gameplay.mp4 = video.mkv's H.264 stream copied (no re-encode) + system audio as AAC,
# aligned on the shared QPC clock: offset = audio start (system_audio.start_offset_ns, from audio_clock.jsonl)
# minus video frame 0 (video_start_offset_ns). Audio that starts later is delayed, earlier is trimmed, then padded to
# the video's end. CPU only, below-normal priority. Never throws: errors come back in .error.
function Export-GameplayMp4([string]$RunDir, $VideoStartNs, $AudioStartNs) {
    $result = [ordered]@{ file = 'gameplay.mp4'; video = 'h264 (stream copy of video.mkv)'; audio = $null; audio_offset_s = $null
                          duration_s = $null; bytes = $null; error = $null }
    $tmp = Join-Path $RunDir 'gameplay.tmp.mp4'
    try {
        $video = Join-Path $RunDir 'video.mkv'
        $audio = Join-Path $RunDir 'system_audio.mka'
        if (-not (Test-Path $video)) { throw 'no video.mkv' }
        $ffArgs = @('-hide_banner', '-loglevel', 'error', '-y', '-i', "`"$video`"")
        $haveAudio = (Test-Path $audio) -and ($null -ne $VideoStartNs) -and ($null -ne $AudioStartNs)
        if ($haveAudio) {
            $offset = ([double]([long]$AudioStartNs - [long]$VideoStartNs)) / 1e9
            $result.audio_offset_s = [math]::Round($offset, 4)
            $align = if ($offset -ge 0) { 'adelay=delays={0}:all=1' -f [math]::Round($offset * 1000).ToString($Inv) }
                     else { 'atrim=start={0},asetpts=PTS-STARTPTS' -f (-$offset).ToString('0.000000', $Inv) }
            $ffArgs += @('-i', "`"$audio`"", '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
                         '-af', "$align,apad", '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-shortest')
            $result.audio = 'aac 192k stereo from system_audio.mka, aligned on the QPC clock'
        } else {
            $ffArgs += @('-map', '0:v:0', '-c:v', 'copy', '-an')
            $result.audio = 'none (no aligned system audio)'
        }
        $ffArgs += @('-movflags', '+faststart', '-threads', '2', "`"$tmp`"")
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = (Find-FFmpeg); $psi.Arguments = ($ffArgs -join ' ')
        $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true; $psi.RedirectStandardError = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        try { $p.PriorityClass = 'BelowNormal' } catch { }
        $err = $p.StandardError.ReadToEnd(); $p.WaitForExit()
        if ($p.ExitCode -ne 0 -or -not (Test-Path $tmp)) { throw "ffmpeg exit $($p.ExitCode): $($err.Trim())" }
        # Check: one H.264 video stream (+ one AAC stream when audio was muxed) and a duration close to video.mkv's.
        $probe = (Invoke-Native (Find-FFprobe) @('-v', 'error', '-show_entries', 'stream=codec_type,codec_name:format=duration', '-of', 'json', $tmp)) -join "`n" | ConvertFrom-Json
        $codecs = @($probe.streams | ForEach-Object { "$($_.codec_type):$($_.codec_name)" })
        $want = if ($haveAudio) { @('video:h264', 'audio:aac') } else { @('video:h264') }
        if (($codecs -join ',') -ne ($want -join ',')) { throw "unexpected streams: $($codecs -join ', ')" }
        $srcDur = [double]::Parse(("$(Invoke-Native (Find-FFprobe) @('-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', $video) | Select-Object -First 1)").Trim(), $Inv)
        $dur = [double]::Parse("$($probe.format.duration)", $Inv)
        if ([math]::Abs($dur - $srcDur) -gt 0.5) { throw ("duration {0:N2} s vs video.mkv {1:N2} s" -f $dur, $srcDur) }
        Move-Item -Force $tmp (Join-Path $RunDir 'gameplay.mp4')
        $result.duration_s = [math]::Round($dur, 3); $result.bytes = (Get-Item (Join-Path $RunDir 'gameplay.mp4')).Length
    } catch {
        $result.error = $_.Exception.Message
        if (Test-Path $tmp) { Remove-Item -Force $tmp -ErrorAction SilentlyContinue }
    }
    return $result
}
