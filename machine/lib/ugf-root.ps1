# Machine root for unity-game-factory tooling. Dot-source it; Windows PowerShell 5.1 compatible.
#
# Everything machine-specific hangs off one root (the "UnityWork" folder holding games\, tasks\, builds\, recordings\,
# .recording\, deliverables\, asset-library\, tools\ and the unity-game-factory clone). Resolution order:
#   1. $env:UGF_ROOT
#   2. "root" in the config file: $env:UGF_CONFIG, else %USERPROFILE%\.unity-game-factory\config.json (bootstrap.ps1 writes it)
#   3. %USERPROFILE%\UnityWork
# The same config file also holds "unity_hub_editors" (the Unity Hub's editor folder), "unity_version" (the editor new
# games use: "6000.3", its newest installed patch, or an exact version; Get-UGFUnityVersion), optional "unity_editors"
# ({"6000.3.28f1": "<path to Unity.exe>", ...}), "record_extra_projects" (top-level folders under the root that the
# recording hooks treat as projects besides games\<slug>), "github_org" (the GitHub organisation or user that owns
# unity-game-factory and the private unity-game-<slug> repos; Get-UGFOrg), "agents" (the coding agents bootstrap.ps1
# wired up: "claude", "codex"), "hooks_dir" (where the recording hooks live, shared by both agents;
# Get-UGFHooksDir) and "ugb" (default C:\UGB: the release builds' private clones and build temp, outside the user profile
# so the user name is not compiled into a player). Installed copies of the hooks and unity-heavy.ps1 carry a copy of this
# file next to them.
#
# Another factory may run on the same machine with its own root and config (%USERPROFILE%\.game-factory\).
# The two never share a root, a config or a hooks folder; they share only the machine-wide job slots (the mutexes
# below), and unity-heavy.ps1 also honours the other factory's recording flag and reads its job log
# (Get-UGFRecordingFlags, Get-UGFJobLogs), so both together never oversubscribe the PC.

function Get-UGFConfigPath {
    if ($env:UGF_CONFIG) { return $env:UGF_CONFIG }
    return (Join-Path $env:USERPROFILE '.unity-game-factory\config.json')
}

$script:UGFDefaultUnityVersion = '6000.3'   # Unity 6.3 LTS: new games use its newest installed patch

function Get-UGFConfig {
    $cfg = [ordered]@{
        root                  = (Join-Path $env:USERPROFILE 'UnityWork')
        unity_hub_editors     = 'C:\Program Files\Unity\Hub\Editor'
        unity_version         = $script:UGFDefaultUnityVersion
        ugb                   = 'C:\UGB'
        record_extra_projects = @()
    }
    $path = Get-UGFConfigPath
    if (Test-Path -LiteralPath $path) {
        # a path typed with single backslashes is the usual cause: name the file, not just the parser's complaint
        try { $json = [IO.File]::ReadAllText($path) | ConvertFrom-Json }
        catch { throw "$path is not valid JSON ($($_.Exception.Message)): write a Windows path in it with doubled backslashes or forward slashes" }
        foreach ($p in $json.PSObject.Properties) { $cfg[$p.Name] = $p.Value }
    }
    if ($env:UGF_ROOT) { $cfg.root = $env:UGF_ROOT }
    foreach ($k in 'root', 'unity_hub_editors', 'ugb') {
        $v = ([string]$cfg[$k]).TrimEnd('\', '/')
        if ($v -match '^[A-Za-z]:$') { $v += '\' }
        $cfg[$k] = [IO.Path]::GetFullPath($v)
    }
    $cfg.record_extra_projects = @($cfg.record_extra_projects | Where-Object { $_ })
    return [pscustomobject]$cfg
}

function Get-UGFRoot { return (Get-UGFConfig).root }

# The coding agents this machine is set up for ("claude", "codex"): "agents" in the config (bootstrap.ps1 -Agent writes
# it); else the ones found installed (the claude / codex command or their home folder); else both.
function Get-UGFAgents($Cfg = (Get-UGFConfig)) {
    if ($Cfg.PSObject.Properties['agents'] -and @($Cfg.agents | Where-Object { $_ }).Count) { return @($Cfg.agents | ForEach-Object { ([string]$_).ToLower() } | Where-Object { $_ -in 'claude', 'codex' } | Select-Object -Unique) }
    $found = @()
    if ((Get-Command claude -ErrorAction SilentlyContinue) -or (Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.claude'))) { $found += 'claude' }
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
    if ((Get-Command codex -ErrorAction SilentlyContinue) -or (Test-Path -LiteralPath $codexHome)) { $found += 'codex' }
    if (-not $found) { $found = @('claude', 'codex') }
    return $found
}

# The recording hooks' folder (record-unity-action.ps1, record-unity-commit.ps1, the session map), one for every agent:
# "hooks_dir" in the config, else %USERPROFILE%\.unity-game-factory\hooks. Never another factory's hooks folder: each
# factory's hooks record only the sessions mapped to its own root, and each keeps its own session map.
function Get-UGFHooksDir($Cfg = (Get-UGFConfig)) {
    if ($Cfg.PSObject.Properties['hooks_dir'] -and $Cfg.hooks_dir) { return [IO.Path]::GetFullPath([string]$Cfg.hooks_dir) }
    return (Join-Path $env:USERPROFILE '.unity-game-factory\hooks')
}

# Unity.exe for a project: the exact version its ProjectSettings\ProjectVersion.txt names (m_EditorVersion) picks the
# install, so a game keeps building on the editor it was made with (an upgrade is a deliberate, committed step).
# $Project is the project folder; without one, or without a ProjectVersion.txt, the editor new games use
# (Get-UGFUnityVersion). $null with a warning naming what to install when it is missing (none under -ErrorAction
# SilentlyContinue / Ignore): callers decide whether that is fatal.
function Get-UGFUnity {
    [CmdletBinding()]
    param([Parameter(Position = 0)][string]$Project, [Parameter(Position = 1)]$Cfg = (Get-UGFConfig))
    $ver = ''
    if ($Project) {
        $pv = Join-Path $Project 'ProjectSettings\ProjectVersion.txt'
        if (Test-Path -LiteralPath $pv) { foreach ($l in [IO.File]::ReadAllLines($pv)) { if ($l -match '^\s*m_EditorVersion:\s*(\S+)') { $ver = $Matches[1]; break } } }
    }
    if (-not $ver) { $ver = Get-UGFUnityVersion $Cfg }
    $exe = Get-UGFUnityForVersion $ver $Cfg
    if ($exe) { return $exe }
    if ($ErrorActionPreference -notin 'SilentlyContinue', 'Ignore') {
        $what = if ($ver) { "Unity $ver is not installed: install it through Unity Hub (Installs > Install Editor, or Archive for an older patch: version $ver" }
        else { "no Unity $($Cfg.unity_version) editor is installed: install the newest $($Cfg.unity_version) patch through Unity Hub (Installs > Install Editor" }
        Write-Warning "$what, with Windows Build Support (IL2CPP)), or name its Unity.exe in unity_editors in $(Get-UGFConfigPath)"
    }
    return $null
}

# Unity.exe for an exact editor version: "unity_editors" in the config, else
# <unity_hub_editors>\<version>\Editor\Unity.exe. '' when that version is not installed (callers say which version to
# install through Unity Hub).
function Get-UGFUnityForVersion([string]$Version, $Cfg = (Get-UGFConfig)) {
    if (-not $Version) { return '' }
    if ($Cfg.PSObject.Properties['unity_editors'] -and $Cfg.unity_editors -and $Cfg.unity_editors.PSObject.Properties[$Version]) {
        $p = [IO.Path]::GetFullPath([string]$Cfg.unity_editors.$Version)
        if (Test-Path -LiteralPath $p -PathType Leaf) { return $p }   # a file: an entry naming the Editor folder does not count
    }
    $p = Join-Path $Cfg.unity_hub_editors "$Version\Editor\Unity.exe"
    if (Test-Path -LiteralPath $p -PathType Leaf) { return $p }
    return ''
}

# The editor version new games use: "unity_version" in the config, default 6000.3 (Unity 6.3 LTS). A series ("6000.3")
# means its newest installed final patch (Unity Hub installs each patch beside the others and never updates one in
# place, so a pinned patch goes stale); an exact version ("6000.3.28f1") pins new games to it. '' when no editor of the
# series is installed.
function Get-UGFUnityVersion($Cfg = (Get-UGFConfig)) {
    $v = [string]$Cfg.unity_version
    if (-not $v) { $v = $script:UGFDefaultUnityVersion }
    if ($v -notmatch '^\d+\.\d+$') { return $v }
    $n = Get-UGFNewestUnity $v $Cfg
    if ($n) { return $n.Version }
    return ''
}

# The editors installed: objects { Version; Path (full path to Unity.exe) } for every
# <unity_hub_editors>\<version>\Editor\Unity.exe and every "unity_editors" entry that exists, newest first (versions
# compared numerically: 6000.3.9f1 < 6000.3.26f1).
function Get-UGFInstalledUnity($Cfg = (Get-UGFConfig)) {
    $found = @{}
    if (Test-Path -LiteralPath $Cfg.unity_hub_editors) {
        foreach ($d in Get-ChildItem -LiteralPath $Cfg.unity_hub_editors -Directory -ErrorAction SilentlyContinue) {
            $exe = Join-Path $d.FullName 'Editor\Unity.exe'
            if (Test-Path -LiteralPath $exe -PathType Leaf) { $found[$d.Name] = $exe }
        }
    }
    if ($Cfg.PSObject.Properties['unity_editors'] -and $Cfg.unity_editors) {
        foreach ($p in $Cfg.unity_editors.PSObject.Properties) { if (Test-Path -LiteralPath ([string]$p.Value) -PathType Leaf) { $found[$p.Name] = [string]$p.Value } }
    }
    @($found.Keys | Sort-Object { ConvertTo-UGFVersionKey $_ } -Descending | ForEach-Object { [pscustomobject]@{ Version = $_; Path = $found[$_] } })
}

# Unity Hub's exe, or $null. winget and the Microsoft Store install Hub as an MSIX package under
# C:\Program Files\WindowsApps\UnityTechnologies.UnityHub_<version>_x64__...\app\ (no folder in Program Files, no
# uninstall registry entry); the classic installer puts it in Program Files\Unity Hub.
function Get-UGFUnityHub {
    $hub = @("$env:ProgramFiles\Unity Hub\Unity Hub.exe", "${env:LOCALAPPDATA}\Programs\Unity Hub\Unity Hub.exe") |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($hub) { return $hub }
    try {
        $pkg = Get-AppxPackage -Name 'UnityTechnologies.UnityHub' -ErrorAction Stop | Sort-Object Version -Descending | Select-Object -First 1
        if ($pkg) { $exe = Join-Path $pkg.InstallLocation 'app\Unity Hub.exe'; if (Test-Path -LiteralPath $exe) { return $exe } }
    } catch { }
    return $null
}

# Sort key for a Unity version ("6000.3.26f1" -> 6000.0003.0026.f.01): stream letters order a < b < f < p.
function ConvertTo-UGFVersionKey([string]$Version) {
    if ($Version -match '^(\d+)\.(\d+)\.(\d+)([abfp])(\d+)') {
        return '{0:D5}.{1:D4}.{2:D4}.{3}.{4:D3}' -f [int]$Matches[1], [int]$Matches[2], [int]$Matches[3], $Matches[4], [int]$Matches[5]
    }
    return "00000.$Version"
}

# The newest installed final ("f") editor of a series ("6000.3" = Unity 6.3 LTS) as { Version; Path }, or $null.
# templates/new-game.ps1 writes its version into a new project's ProjectVersion.txt.
function Get-UGFNewestUnity([string]$Series = '6000.3', $Cfg = (Get-UGFConfig)) {
    $pre = [regex]::Escape($Series) + '\.\d+f\d+$'
    $hit = Get-UGFInstalledUnity $Cfg | Where-Object { $_.Version -cmatch "^$pre" } | Select-Object -First 1
    if ($hit) { return $hit }
    return $null
}

# GitHub organisation (or user) that owns unity-game-factory and the private unity-game-<slug> repos: $env:UGF_ORG,
# else "github_org" in the config file (bootstrap.ps1 -Org writes it), else '' (callers that need it say how to set it).
function Get-UGFOrg($Cfg = (Get-UGFConfig)) {
    if ($env:UGF_ORG) { return $env:UGF_ORG.Trim() }
    if ($Cfg.PSObject.Properties['github_org'] -and $Cfg.github_org) { return ([string]$Cfg.github_org).Trim() }
    return ''
}

# Output root for packages (the creation replay's _replay\<slug>\<sha8>\; the dataset packager's commit maps, audit
# files, package-log.jsonl and run lock in <slug>\, its zip next to the game repo unless its --out names another
# folder): $env:UGF_OUT, else "out" in the config file, else <root>\deliverables.
# Point it at a roomy drive (packages and zips run to GBs per game).
function Get-UGFOut {
    if ($env:UGF_OUT) { return [IO.Path]::GetFullPath($env:UGF_OUT.TrimEnd('\', '/')) }
    $cfg = Get-UGFConfig
    if ($cfg.PSObject.Properties['out'] -and $cfg.out) { return [IO.Path]::GetFullPath(([string]$cfg.out).TrimEnd('\', '/')) }
    return (Join-Path $cfg.root 'deliverables')
}

# Refuse to start a disk-heavy job (the dataset packager, the creation replay, the task check and the task try are
# Python and use ugfroot.py check_free) when the drive holding $Path has less than the floor free: $env:UGF_MIN_FREE_GB,
# else "min_free_gb" in the config file, else 50. A full disk mid-job corrupts the result.
function Assert-UGFFreeSpace([string]$Path, [string]$What = 'this job') {
    $min = 50
    $cfg = Get-UGFConfig
    if ($cfg.PSObject.Properties['min_free_gb'] -and $cfg.min_free_gb) { $min = [double]$cfg.min_free_gb }
    if ($env:UGF_MIN_FREE_GB) { $min = [double]$env:UGF_MIN_FREE_GB }
    $full = [IO.Path]::GetFullPath($Path)
    # a game folder may be a junction to another drive (games\<game> -> D:\...): count the drive the data lands on
    for ($d = $full; $d; $d = Split-Path $d -Parent) {
        $it = Get-Item -LiteralPath $d -Force -ErrorAction SilentlyContinue
        if ($it -and $it.LinkType -and $it.Target) { $full = [IO.Path]::GetFullPath([string]@($it.Target)[0] + $full.Substring($d.Length)); break }
    }
    $drive = New-Object IO.DriveInfo ([IO.Path]::GetPathRoot($full))
    $free = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
    if ($free -lt $min) {
        throw ("{0}: only {1} GB free on {2} (floor {3} GB; UGF_MIN_FREE_GB / min_free_gb). Free space or point --scratch (the task check and the task try) / UGF_OUT (packages) at another drive." -f $What, $free, $drive.Name, $min)
    }
    return $free
}

# Regex matching a path under the root in the spellings tool calls use: C:\a\b, C:/a/b, /c/a/b (Git Bash), /mnt/c/a/b.
# The drive must start a path (not follow a letter, digit, dot or hyphen): D:/backup/c/a/b is not under C:\a\b, and
# a path glued to an option (git -C/c/a/b) does not count either.
# Append the part after the root yourself, e.g. (Get-UGFRootPattern) + '[\\/]+games[\\/]+([A-Za-z0-9_-]+)'.
function Get-UGFRootPattern([string]$Root = (Get-UGFRoot)) {
    $full = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $drive = $full.Substring(0, 1)
    $rest = @($full.Substring(2).Split('\') | Where-Object { $_ } | ForEach-Object { [regex]::Escape($_) })
    $head = "(?<![\w.-])(?:$drive`:|/$drive|/mnt/$drive)"
    if ($rest.Count -eq 0) { return "(?i)$head" }
    return "(?i)$head[\\/]+" + ($rest -join '[\\/]+')
}

# The root of another factory on this machine, or '' when none is set up here ($env:GF_ROOT, else "root" in
# %USERPROFILE%\.game-factory\config.json, else %USERPROFILE%\Work if it holds a clone named game-factory). Used only to see
# that factory's recording flag and job log, so the two factories share the machine's slots fairly.
function Get-UGFOtherFactoryRoot {
    $r = ''
    if ($env:GF_ROOT) { $r = $env:GF_ROOT }
    else {
        $cfg = if ($env:GF_CONFIG) { $env:GF_CONFIG } else { Join-Path $env:USERPROFILE '.game-factory\config.json' }
        if (Test-Path -LiteralPath $cfg) {
            try { $j = [IO.File]::ReadAllText($cfg) | ConvertFrom-Json; if ($j.root) { $r = [string]$j.root } } catch { }
        }
        if (-not $r) {
            $w = Join-Path $env:USERPROFILE 'Work'
            if (Test-Path -LiteralPath (Join-Path $w 'game-factory')) { $r = $w }
        }
    }
    if (-not $r) { return '' }
    $full = [IO.Path]::GetFullPath($r.TrimEnd('\', '/'))
    if ($full -eq [IO.Path]::GetFullPath((Get-UGFRoot).TrimEnd('\'))) { return '' }
    return $full
}

# The "a recording waits for the GPU" flags unity-heavy.ps1 honours: ours (<root>\builds\_queue\_recording-wants-gpu,
# written by tools/unity-pipeline/record.ps1 and the queue's drainer) and the other factory's when one is set up here
# (its limiter, ue-heavy.ps1, reads only its own). A running recording takes every GPU slot of the machine.
function Get-UGFRecordingFlags {
    $flags = @(Join-Path (Get-UGFRoot) 'builds\_queue\_recording-wants-gpu')
    $other = Get-UGFOtherFactoryRoot
    if ($other) { $flags += (Join-Path $other 'builds\_queue\_recording-wants-gpu') }
    , $flags
}

# The heavy-job logs both limiters write (ours first): unity-heavy.ps1 reads waits and recent GPU starts from both, so
# its jobs see the other factory's (ue-heavy.ps1 reads only its own).
function Get-UGFJobLogs {
    $logs = @(Join-Path (Get-UGFRoot) '.recording\_heavy-jobs.jsonl')
    $other = Get-UGFOtherFactoryRoot
    if ($other) { $logs += (Join-Path $other '.recording\_heavy-jobs.jsonl') }
    , $logs
}

# Machine-wide job slots (unity-heavy.ps1). Config keys win: heavy_slots (general slots: builds, batchmode editor runs,
# tests; GPU jobs hold one too), gpu_slots (concurrent rendering jobs; a recording takes all of them), gpu_vram_limit_mb
# (a GPU job starts only while less VRAM than this is in use; default half the VRAM). Without them the slots are
# computed from the hardware (bootstrap.ps1 writes the computed values to the config), with the same formula as the other
# factory's limiter, so both factories agree on the counts:
#   heavy_slots = clamp(1..8, min(floor((RAM GB - 6) / 6), floor(logical cores / 4), floor((commit limit GB - 6) / 8)))
#                 (~6 GB per heavy editor process, 6 GB kept for the desktop and the sessions)
#   gpu_slots   = clamp(1..4, min(floor(VRAM GB of the largest NVIDIA GPU / 4), heavy_slots - 1)); 1 without nvidia-smi
#                 (~4 GB per renderer; one general slot always left for compiles)
function Get-UGFHardware {
    $cs = Get-CimInstance Win32_ComputerSystem
    $os = Get-CimInstance Win32_OperatingSystem
    $vram = @()
    try {
        $out = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
        $vram = @($out | ForEach-Object { "$_".Trim() } | Where-Object { $_ -match '^\d+$' } | ForEach-Object { [int]$_ })
    } catch { }
    [pscustomobject]@{
        logical_cores = [int]$cs.NumberOfLogicalProcessors
        ram_gb        = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
        commit_gb     = [math]::Round($os.TotalVirtualMemorySize / 1MB, 1)
        gpu_count     = $vram.Count
        vram_mb       = $(if ($vram.Count) { ($vram | Measure-Object -Maximum).Maximum } else { 0 })
    }
}

function Get-UGFComputedSlots($Hw = (Get-UGFHardware)) {
    $heavy = [math]::Min([math]::Floor(($Hw.ram_gb - 6) / 6), [math]::Floor($Hw.logical_cores / 4))
    $heavy = [math]::Min($heavy, [math]::Floor(($Hw.commit_gb - 6) / 8))
    $heavy = [int][math]::Max(1, [math]::Min(8, $heavy))
    $gpu = if ($Hw.vram_mb -gt 0) { [math]::Min([math]::Floor($Hw.vram_mb / 1024 / 4), $heavy - 1) } else { 1 }
    $gpu = [int][math]::Max(1, [math]::Min(4, $gpu))
    [pscustomobject]@{ heavy_slots = $heavy; gpu_slots = $gpu; hardware = $Hw }
}

# The slots in effect and where each comes from: 'config' (set by hand), 'config (bootstrap)' (written by bootstrap.ps1
# from the formula, recorded in slots_auto), or 'computed' (no config key: the formula at run time).
function Get-UGFSlotPlan($Cfg = (Get-UGFConfig)) {
    $auto = if ($Cfg.PSObject.Properties['slots_auto']) { $Cfg.slots_auto } else { $null }
    $computed = $null
    $plan = [ordered]@{}
    foreach ($k in 'heavy_slots', 'gpu_slots') {
        if ($Cfg.PSObject.Properties[$k] -and [int]$Cfg.$k -gt 0) {
            $plan[$k] = [int]$Cfg.$k
            $plan["${k}_source"] = if ($auto -and $auto.PSObject.Properties[$k] -and [int]$auto.$k -eq [int]$Cfg.$k) { 'config (bootstrap)' } else { 'config' }
        } else {
            if (-not $computed) { $computed = Get-UGFComputedSlots }
            $plan[$k] = $computed.$k
            $plan["${k}_source"] = 'computed'
        }
    }
    $plan['gpu_vram_limit_mb'] = if ($Cfg.PSObject.Properties['gpu_vram_limit_mb'] -and [int]$Cfg.gpu_vram_limit_mb -gt 0) { [int]$Cfg.gpu_vram_limit_mb } else { 0 }
    [pscustomobject]$plan
}

# ---- machine-wide job slots: one named mutex per slot (unity-heavy.ps1) ---------------------------------------------
# A slot is the mutex Global\ue-heavy-slot-<n> (general) or Global\ue-gpu-slot-<n> (GPU), n < heavy_slots / gpu_slots.
# The names are another factory's on purpose: its ue-heavy.ps1 takes the same mutexes, so the two factories draw
# from one set of slots and together never run more heavy or GPU jobs than the machine holds. Unlike a counted
# semaphore nothing leaks: a holder that dies without releasing (killed job, crashed editor) leaves its mutex
# "abandoned", and the next taker gets it. The count is the config's at every call, so a new heavy_slots or gpu_slots
# takes effect at once. A mutex belongs to the thread that took it: take and release it in the same script.
function Get-UGFSlotMutexes([ValidateSet('heavy', 'gpu')][string]$Kind, [int]$Count) {
    $prefix = if ($Kind -eq 'gpu') { 'Global\ue-gpu-slot-' } else { 'Global\ue-heavy-slot-' }
    , @(for ($i = 0; $i -lt $Count; $i++) { New-Object Threading.Mutex($false, "$prefix$i") })
}

# Take a mutex within TimeoutMs; an abandoned one (its holder died) is taken over. $true when held.
function Enter-UGFMutex($Mutex, [int]$TimeoutMs = 0) {
    try { return [bool]$Mutex.WaitOne($TimeoutMs) }
    catch {
        $e = $_.Exception
        while ($e -and -not ($e -is [Threading.AbandonedMutexException])) { $e = $e.InnerException }
        if ($e) { return $true }
        throw
    }
}

# One free slot among indices From..Count-1 (Skip: indices this script already holds), without waiting; -1 if none.
function Enter-UGFSlot($Mutexes, [int]$From = 0, [int[]]$Skip = @()) {
    for ($i = [math]::Max(0, $From); $i -lt $Mutexes.Count; $i++) {
        if ($Skip -contains $i) { continue }
        if (Enter-UGFMutex $Mutexes[$i] 0) { return $i }
    }
    return -1
}

function Exit-UGFSlot($Mutexes, [int]$Index) {
    if ($Index -ge 0 -and $Index -lt $Mutexes.Count) { try { $Mutexes[$Index].ReleaseMutex() } catch { } }
}
