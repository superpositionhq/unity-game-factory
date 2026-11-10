<#
.SYNOPSIS
  Check that this machine can run unity-game-factory sessions; prints a PASS / WARN / FAIL report. Read-only.
.DESCRIPTION
  Toolchain: Unity Hub, the Unity 6.3 LTS editor new games use (the config's unity_version) with Windows Build Support
  (IL2CPP), the editors the games here name, Visual Studio's C++ tools for IL2CPP builds (WARN only: Mono builds need
  none), git + Git LFS, gh (logged in, can see the org's repos), Python. Recording (what the recorder will need; it is
  not available yet): NVIDIA driver (NVENC with the pinned ffmpeg), refresh rate, display sleep off, the pinned ffmpeg
  (tools/sfx.py uses it today). Space: free disk on the root's drive. Content: the asset
  library folder and the Unity Asset Store download cache. Agents (the config's "agents": Claude Code and/or Codex):
  installed, signed in where it can tell. Setup done by bootstrap.ps1: config, job slots, unity-heavy.ps1, the
  recording hooks and each agent's wiring (Claude Code settings.json; Codex hooks.json + trust), skills, root CLAUDE.md /
  AGENTS.md.
  Exit code = number of FAILs. -Json writes the report as JSON too.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File machine\check.ps1
  powershell -ExecutionPolicy Bypass -File machine\check.ps1 -Root C:\ugf-test\UnityWork -ClaudeDir C:\ugf-test\home\.claude -CodexDir C:\ugf-test\home\.codex `
      -AgentsSkillsDir C:\ugf-test\home\.agents\skills -HooksDir C:\ugf-test\home\.unity-game-factory\hooks -Json C:\ugf-test\check.json
#>
param(
    [string]$Root,
    [string]$ClaudeDir = (Join-Path $env:USERPROFILE '.claude'),
    [string]$CodexDir,                                          # default: CODEX_HOME / %USERPROFILE%\.codex
    [string]$AgentsSkillsDir = (Join-Path $env:USERPROFILE '.agents\skills'),
    [string]$HooksDir,                                          # default: config hooks_dir
    [string]$ConfigPath,
    [string]$Org,                   # default: the config's github_org (UGF_ORG)
    [int]$MinFreeGB = 200,          # WARN below this, FAIL below a third of it
    [int]$MinDriver = 610,
    [string]$Json
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'lib\ugf-root.ps1')
. (Join-Path $PSScriptRoot 'lib\codex-hooks.ps1')
if ($ConfigPath) { $env:UGF_CONFIG = $ConfigPath }
if ($Root) { $env:UGF_ROOT = $Root }
$cfg = Get-UGFConfig
$Root = $cfg.root
if (-not $CodexDir) { $CodexDir = Get-UGFCodexHome }
if (-not $HooksDir) { $HooksDir = Get-UGFHooksDir $cfg }
$HooksDir = [IO.Path]::GetFullPath($HooksDir)
$Agents = @(Get-UGFAgents $cfg)
if (-not $Org) { $Org = Get-UGFOrg $cfg }
$results = New-Object Collections.Generic.List[object]

function Add-Result([string]$Status, [string]$Check, [string]$Detail, [string]$Fix = '') {
    $results.Add([pscustomobject]@{ status = $Status; check = $Check; detail = $Detail; fix = $Fix })
}
function Try-Check([string]$Check, [scriptblock]$Body) {
    try { & $Body } catch { Add-Result FAIL $Check "check errored: $($_.Exception.Message)" }
}
function Run([string]$Exe, [string[]]$ArgList) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $out = & $Exe @ArgList 2>&1 | ForEach-Object { "$_" }; return [pscustomobject]@{ code = $LASTEXITCODE; out = ($out -join "`n") } }
    catch { return [pscustomobject]@{ code = -1; out = $_.Exception.Message } }
    finally { $ErrorActionPreference = $old }
}

# --- toolchain ------------------------------------------------------------------------------------------------------
Try-Check 'Unity Hub' {
    $hub = Get-UGFUnityHub
    if ($hub) { Add-Result PASS 'Unity Hub' "$hub; sign-in and licence are not detectable here: Hub > Preferences > Licenses must show an active licence" }
    else { Add-Result FAIL 'Unity Hub' 'not installed' 'winget install -e --id Unity.UnityHub, then sign in with a Unity ID and activate a licence (Personal is fine)' }
}
Try-Check 'Unity 6.3 LTS editor' {
    $ver = Get-UGFUnityVersion $cfg   # the editor new games use: unity_version, a series (its newest patch) or exact
    $exe = Get-UGFUnityForVersion $ver $cfg
    if (-not $exe -and $ver) { Add-Result FAIL 'Unity 6.3 LTS editor' "unity_version $ver is not installed" "install it through Unity Hub (Installs > Install Editor > Archive), or set unity_version in $(Get-UGFConfigPath) to 6000.3 (its newest installed patch)"; return }
    if (-not $exe) { Add-Result FAIL 'Unity 6.3 LTS editor' "no $($cfg.unity_version) editor under $($cfg.unity_hub_editors)" 'Unity Hub > Installs > Install Editor > Unity 6.3 (LTS), the newest 6000.3 patch, with the module Windows Build Support (IL2CPP) (or name where the editors are: unity_hub_editors / unity_editors in the config)'; return }
    if ($ver -match '^6000\.3\.') { Add-Result PASS 'Unity 6.3 LTS editor' "$ver at $exe (unity_version $($cfg.unity_version))" }
    else { Add-Result FAIL 'Unity 6.3 LTS editor' "unity_version $ver is not 6.3 LTS" 'set unity_version to 6000.3 (its newest installed patch) or an installed 6000.3 version; new games and the template target 6000.3' }
    # Windows Build Support (IL2CPP): the editor's Data\PlaybackEngines\windowsstandalonesupport has Variations\*il2cpp*
    $ws = Join-Path (Split-Path $exe -Parent) 'Data\PlaybackEngines\windowsstandalonesupport'
    $il2cpp = (Test-Path $ws) -and @(Get-ChildItem (Join-Path $ws 'Variations') -Directory -ErrorAction SilentlyContinue | Where-Object Name -match 'il2cpp').Count -gt 0
    if ($il2cpp) { Add-Result PASS 'Windows Build Support (IL2CPP)' $ver }
    else { Add-Result WARN 'Windows Build Support (IL2CPP)' "not found for $ver (Mono player builds still work)" "Unity Hub > Installs > $ver > Add modules > Windows Build Support (IL2CPP)" }
}
# A game builds, tests and plays only on the exact editor its ProjectSettings\ProjectVersion.txt names (Get-UGFUnity).
Try-Check 'Unity editors of the games' {
    $need = [ordered]@{}
    foreach ($g in @(Get-ChildItem (Join-Path $Root 'games') -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '_*' })) {
        $pv = Join-Path $g.FullName 'ProjectSettings\ProjectVersion.txt'
        if (-not ((Test-Path $pv) -and ((Get-Content $pv -Raw) -match 'm_EditorVersion:\s*(\S+)'))) { continue }
        if (-not $need.Contains($Matches[1])) { $need[$Matches[1]] = @() }
        $need[$Matches[1]] += $g.Name
    }
    $missing = @($need.Keys | Where-Object { -not (Get-UGFUnityForVersion $_ $cfg) })
    if (-not $missing) { Add-Result PASS 'Unity editors of the games' $(if ($need.Count) { "installed: $(@($need.Keys) -join ', ')" } else { 'no game projects yet' }) }
    else { Add-Result WARN 'Unity editors of the games' "not installed: $(($missing | ForEach-Object { "$_ ($($need[$_] -join ', '))" }) -join '; ')" 'needed only to build, test or play those games: Unity Hub > Installs > Install Editor > Archive > that exact version, with Windows Build Support (IL2CPP)' }
}
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
Try-Check 'C++ tools for IL2CPP' {
    # IL2CPP compiles the generated C++ with MSVC; Mono builds and the editor itself need none. So a WARN, never a FAIL.
    $installs = if (Test-Path $vswhere) { @(& $vswhere -all -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath) } else { @() }
    if ($installs) { Add-Result PASS 'C++ tools for IL2CPP' ($installs -join '; ') }
    else { Add-Result WARN 'C++ tools for IL2CPP' 'no Visual Studio / Build Tools with the C++ x64 toolset' 'only for IL2CPP player builds: VS 2022 (or Build Tools) with "Desktop development with C++" (or "Game development with Unity" + its C++ option)' }
}
Try-Check 'git' {
    $r = Run git @('--version')
    if ($r.code -eq 0) { Add-Result PASS 'git' $r.out } else { Add-Result FAIL 'git' 'not found' 'winget install Git.Git' }
}
Try-Check 'Git LFS' {
    $r = Run git @('lfs', 'version')
    if ($r.code -ne 0) { Add-Result FAIL 'Git LFS' 'git lfs not found' 'winget install GitHub.GitLFS'; return }
    $f = Run git @('config', '--get', 'filter.lfs.process')   # global or system (Git for Windows sets it system-wide)
    if ($f.out) { Add-Result PASS 'Git LFS' ($r.out -split "`n")[0] } else { Add-Result FAIL 'Git LFS' 'installed but filters not set up' 'git lfs install --skip-repo (bootstrap.ps1 does this)' }
}
Try-Check 'GitHub CLI' {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Add-Result FAIL 'GitHub CLI' 'gh not found' 'winget install GitHub.cli'; return }
    $login = Run gh @('api', 'user', '--jq', '.login')
    if ($login.code -ne 0) { Add-Result FAIL 'GitHub CLI' 'not logged in' 'gh auth login (GitHub.com, HTTPS, browser)'; return }
    if (-not $Org) { Add-Result FAIL 'GitHub org' "logged in as $($login.out); no github_org in the config" 'machine/bootstrap.ps1 -Org <GitHub org or user that owns unity-game-factory and the game repos>'; return }
    $v = Run gh @('repo', 'view', "$Org/unity-game-factory", '--json', 'name,visibility', '--jq', '.visibility')
    if ($v.code -ne 0) { Add-Result FAIL "GitHub access to $Org" "logged in as $($login.out), but cannot see $Org/unity-game-factory" "ask an $Org owner to add the account (needs repo create rights for unity-game-<slug> repos)"; return }
    $m = Run gh @('api', "user/memberships/orgs/$Org", '--jq', '.role + " " + .state')
    $role = if ($m.code -eq 0) { $m.out } else { 'membership not readable (token lacks read:org)' }
    $n = Run gh @('repo', 'list', $Org, '--limit', '500', '--json', 'name', '--jq', '.[].name')
    $games = @(($n.out -split "`n") | Where-Object { $_ -match '^unity-game-.' -and $_ -ne 'unity-game-factory' }).Count
    Add-Result PASS "GitHub access to $Org" "logged in as $($login.out); org role: $role; unity-game-* repos visible: $games"
}
Try-Check 'Python' {
    $py = Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' } | Select-Object -First 1
    $cmd = if ($py) { $py.Source } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { $null }
    if (-not $cmd) { Add-Result FAIL 'Python' 'no python.exe (the Microsoft Store stub does not count)' 'winget install Python.Python.3.12 (sfx, thread-stats, scrub and validation tools)'; return }
    $r = Run $cmd @('-c', 'import sys; print(sys.version.split()[0])')
    if ($r.code -eq 0 -and $r.out -match '^3\.(\d+)' -and [int]$Matches[1] -ge 10) { Add-Result PASS 'Python' "$($r.out) ($cmd)" }
    else { Add-Result FAIL 'Python' "unusable: $($r.out)" 'install Python 3.10+' }
}

# --- recording hardware / display ------------------------------------------------------------------------------------
Try-Check "NVIDIA driver >= $MinDriver" {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $smi) { Add-Result WARN "NVIDIA driver >= $MinDriver" 'nvidia-smi not found (no NVIDIA GPU/driver)' 'recording prefers NVENC; without it recordings fall back to the CPU (slower)'; return }
    $r = Run $smi.Source @('--query-gpu=name,driver_version,memory.total', '--format=csv,noheader')
    $first = ($r.out -split "`n")[0]
    $parts = $first -split ',\s*'
    $drv = [double]($parts[1] -replace '[^\d.]', '')
    if ($drv -ge $MinDriver) { Add-Result PASS "NVIDIA driver >= $MinDriver" $first }
    else { Add-Result FAIL "NVIDIA driver >= $MinDriver" $first "update the driver (the pinned ffmpeg 8.1.2 NVENC needs >= 610)" }
}
Try-Check 'Primary display' {
    Add-Type -Namespace UgfCheck -Name Metrics -MemberDefinition '[DllImport("user32.dll")] public static extern int GetSystemMetrics(int i); [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
    [void][UgfCheck.Metrics]::SetProcessDPIAware()   # physical pixels, as a desktop capture sees them
    $w = [UgfCheck.Metrics]::GetSystemMetrics(0); $h = [UgfCheck.Metrics]::GetSystemMetrics(1)
    if ($w -ge 1920 -and $h -ge 1080) { Add-Result PASS 'Primary display' "${w}x${h} (holds a 1920x1080 player window)" }
    else { Add-Result FAIL 'Primary display' "${w}x${h}" 'recordings show a 1920x1080 player window on the primary display: use a display (and scaling) of at least 1920x1080' }
}
Try-Check 'Display refresh rate' {
    $rates = @(Get-CimInstance Win32_VideoController | Where-Object { $_.CurrentRefreshRate } | ForEach-Object { "$($_.Name): $($_.CurrentHorizontalResolution)x$($_.CurrentVerticalResolution) @ $($_.CurrentRefreshRate) Hz" })
    $max = (@(Get-CimInstance Win32_VideoController | ForEach-Object { [int]$_.CurrentRefreshRate }) | Measure-Object -Maximum).Maximum
    # Fractional rates (59.94, 119.88 Hz) are reported rounded down (59, 119): treat them as the 60-multiple they are.
    if ($max -ge 59 -and ($max + 1) % 60 -eq 0) { $rates = @($rates) + "reported $max Hz = a fractional $($max + 1)-class rate (e.g. 59.94), counted as $($max + 1)"; $max = $max + 1 }
    if ($max -ge 60 -and $max % 60 -eq 0) { Add-Result PASS 'Display refresh rate' ($rates -join '; ') }
    elseif ($max -ge 60) { Add-Result WARN 'Display refresh rate' ($rates -join '; ') 'recordings are 60 fps CFR: pick a multiple of 60 (60/120/240 Hz) for recording, or frames repeat/skip (Settings > Display > Advanced display)' }
    else { Add-Result FAIL 'Display refresh rate' $(if ($rates) { $rates -join '; ' } else { 'no active display' }) 'recording captures the desktop at 60 fps: needs a display at >= 60 Hz' }
}
function Get-PowerAc([string]$Sub, [string]$Setting) {
    $r = Run powercfg @('/query', 'SCHEME_CURRENT', $Sub, $Setting)
    $hex = [regex]::Matches($r.out, '0x[0-9a-fA-F]{8}') | ForEach-Object { $_.Value }
    if ($hex.Count -lt 2) { return $null }
    return [Convert]::ToInt32($hex[-2], 16)   # the last two are the AC and DC current values
}
Try-Check 'Display sleep off' {
    $ac = Get-PowerAc 'SUB_VIDEO' 'VIDEOIDLE'
    if ($null -eq $ac) { Add-Result WARN 'Display sleep off' 'could not read powercfg' ; return }
    if ($ac -eq 0) { Add-Result PASS 'Display sleep off' 'turn off display after: never (AC)' }
    # A display that went to sleep during a long build delivers no frames to a desktop capture; "never" is the safe setting.
    else { Add-Result WARN 'Display sleep off' "display turns off after $([int]($ac/60)) min (AC)" 'powercfg /change monitor-timeout-ac 0 (Settings > System > Power > Screen: Never)' }
}
Try-Check 'System sleep off' {
    $ac = Get-PowerAc 'SUB_SLEEP' 'STANDBYIDLE'
    if ($null -eq $ac) { Add-Result WARN 'System sleep off' 'could not read powercfg'; return }
    if ($ac -eq 0) { Add-Result PASS 'System sleep off' 'sleep after: never (AC)' }
    else { Add-Result WARN 'System sleep off' "PC sleeps after $([int]($ac/60)) min (AC)" 'powercfg /change standby-timeout-ac 0 (overnight queues and long builds)' }
}
Try-Check 'Free disk' {
    $drive = (Split-Path -Qualifier $Root).TrimEnd(':')
    $d = Get-PSDrive -Name $drive
    $gb = [math]::Round($d.Free / 1GB)
    if ($gb -ge $MinFreeGB) { Add-Result PASS 'Free disk' "$gb GB free on ${drive}:" }
    elseif ($gb -ge [int]($MinFreeGB / 3)) { Add-Result WARN 'Free disk' "$gb GB free on ${drive}: (want $MinFreeGB)" 'game repos with LFS are several GB each, each project''s Library\ cache a few more, builds and recordings grow' }
    else { Add-Result FAIL 'Free disk' "$gb GB free on ${drive}:" "free space; under $([int]($MinFreeGB/3)) GB builds and packaging fail" }
}
Try-Check 'Memory' {
    $gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    if ($gb -ge 30) { Add-Result PASS 'Memory' "$gb GB" } else { Add-Result WARN 'Memory' "$gb GB" 'fewer heavy slots fit: the slot formula sizes them from RAM (check Job slots below)' }
}
Try-Check 'Long paths' {
    $v = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled
    if ($v -eq 1) { Add-Result PASS 'Long paths' 'LongPathsEnabled=1' } else { Add-Result WARN 'Long paths' 'LongPathsEnabled is off' 'optional: Asset Store packs and Library\PackageCache nest deeply; keep the root short or enable long paths as admin' }
}

# --- pinned ffmpeg ---------------------------------------------------------------------------------------------------
Try-Check 'ffmpeg 8.1.2 (pinned)' {
    $exe = Join-Path $Root 'tools\ffmpeg-8.1.2\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe'
    $arc = Join-Path $Root 'tools\ffmpeg-8.1.2\ffmpeg-8.1.2-full_build.7z'
    if (-not (Test-Path $exe)) { Add-Result FAIL 'ffmpeg 8.1.2 (pinned)' "missing $exe" 'machine\get-ffmpeg.ps1'; return }
    $ok = (Test-Path $arc) -and ((Get-FileHash $arc -Algorithm SHA256).Hash -eq '0FFF188997A499B5382E0F66E845D4556C48C54F0113EBED4853D556DBDD7059')
    $nv = Run $exe @('-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:r=60', '-t', '0.1', '-c:v', 'h264_nvenc', '-f', 'null', '-')
    $enc = if ($nv.code -eq 0) { 'h264_nvenc opens' } else { 'h264_nvenc does NOT open (recordings fall back to libx264)' }
    if ($ok) { Add-Result $(if ($nv.code -eq 0) { 'PASS' } else { 'WARN' }) 'ffmpeg 8.1.2 (pinned)' "archive SHA-256 verified; $enc" }
    else { Add-Result WARN 'ffmpeg 8.1.2 (pinned)' "ffmpeg.exe present but the archive is missing or does not match the pin; $enc" 'machine\get-ffmpeg.ps1 -Force' }
}

# --- setup done by bootstrap.ps1 ---------------------------------------------------------------------------------------
Try-Check 'Config' {
    $p = Get-UGFConfigPath
    if (Test-Path $p) { Add-Result PASS 'Config' "$p (root $Root)" }
    elseif ($Root -eq (Join-Path $env:USERPROFILE 'UnityWork')) { Add-Result WARN 'Config' "no $p; using the default root $Root" 'machine\bootstrap.ps1 writes it' }
    else { Add-Result FAIL 'Config' "no $p" 'machine\bootstrap.ps1' }
}
Try-Check 'Job slots' {
    # the slots unity-heavy.ps1 uses and where each comes from: config (set by hand), config (bootstrap) or computed
    $sp = Get-UGFSlotPlan $cfg
    $calc = Get-UGFComputedSlots
    $vl = if ($sp.gpu_vram_limit_mb -gt 0) { "$($sp.gpu_vram_limit_mb) MB (config)" } else { 'half the VRAM' }
    $detail = "heavy_slots $($sp.heavy_slots) [$($sp.heavy_slots_source)], gpu_slots $($sp.gpu_slots) [$($sp.gpu_slots_source)], " +
        "VRAM limit $vl; formula gives $($calc.heavy_slots)/$($calc.gpu_slots) ($($calc.hardware.logical_cores) threads, " +
        "$($calc.hardware.ram_gb) GB RAM, $($calc.hardware.vram_mb) MB VRAM)"
    $ue = Get-UGFUnrealRoot
    if ($ue) { $detail += "; slots shared with the Unreal game-factory at $ue (same machine-wide mutexes)" }
    if ($sp.gpu_slots -ge $sp.heavy_slots) {
        Add-Result WARN 'Job slots' "$detail; GPU jobs also take a general slot, so gpu_slots >= heavy_slots can leave no slot for compiles" 'lower gpu_slots or raise heavy_slots in the config'
    } else { Add-Result PASS 'Job slots' $detail }
}
Try-Check 'UnityWork layout' {
    $missing = @('games', 'tasks', 'builds\_queue', 'builds\_logs', 'recordings', '.recording', 'deliverables', 'asset-library', 'tools') | Where-Object { -not (Test-Path (Join-Path $Root $_)) }
    if (-not $missing) { Add-Result PASS 'UnityWork layout' $Root } else { Add-Result FAIL 'UnityWork layout' "missing: $($missing -join ', ')" 'machine\bootstrap.ps1' }
}
Try-Check 'unity-game-factory clone' {
    $exp = Join-Path $Root 'unity-game-factory'
    if ([IO.Path]::GetFullPath($repo).TrimEnd('\') -eq $exp) { Add-Result PASS 'unity-game-factory clone' $repo }
    else { Add-Result WARN 'unity-game-factory clone' "running from $repo, briefs and docs assume $exp" "git clone https://github.com/$(if ($Org) { $Org } else { '<org>' })/unity-game-factory $exp" }
}
function Same-File([string]$A, [string]$B) { (Test-Path $A) -and (Test-Path $B) -and ((Get-FileHash $A).Hash -eq (Get-FileHash $B).Hash) }
Try-Check 'unity-heavy.ps1' {
    $dst = Join-Path $Root 'tools\unity-heavy.ps1'
    $lib = Join-Path $Root 'tools\ugf-root.ps1'
    if ((Same-File (Join-Path $PSScriptRoot 'tools\unity-heavy.ps1') $dst) -and (Same-File (Join-Path $PSScriptRoot 'lib\ugf-root.ps1') $lib)) { Add-Result PASS 'unity-heavy.ps1' $dst }
    elseif (Test-Path $dst) { Add-Result WARN 'unity-heavy.ps1' "$dst or ugf-root.ps1 next to it differs from the repo copy" 'machine\bootstrap.ps1 (keeps a backup)' }
    else { Add-Result FAIL 'unity-heavy.ps1' "missing $dst" 'machine\bootstrap.ps1' }
}
Try-Check 'Recording hooks' {
    $hd = $HooksDir
    $files = @('record-unity-action.ps1', 'record-unity-commit.ps1')
    $diff = @($files | Where-Object { -not (Same-File (Join-Path $PSScriptRoot "hooks\$_") (Join-Path $hd $_)) })
    $absent = @($files | Where-Object { -not (Test-Path (Join-Path $hd $_)) })
    $lib = Test-Path (Join-Path $hd 'ugf-root.ps1')
    if ($absent -or -not $lib) { Add-Result FAIL 'Recording hooks' "missing in ${hd}: $(@($absent) + @($(if (-not $lib) { 'ugf-root.ps1' })) -join ', ')" 'machine\bootstrap.ps1'; return }
    if (-not (Same-File (Join-Path $PSScriptRoot 'lib\ugf-root.ps1') (Join-Path $hd 'ugf-root.ps1'))) { $diff += 'ugf-root.ps1' }   # the hooks run with this copy
    if ($diff) { Add-Result WARN 'Recording hooks' "$hd`: older than the repo copy ($($diff -join ', '))" 'machine\bootstrap.ps1 (backs up the old copies)'; return }
    Add-Result PASS 'Recording hooks' $hd
}
# The events each agent must run record-unity-action.ps1 on (Codex has no PostToolUseFailure).
function Get-WiredEvents($Obj, [string[]]$Events) {
    $w = @()
    foreach ($ev in $Events) {
        $cmds = @($Obj.hooks.$ev | ForEach-Object { $_.hooks } | ForEach-Object { [string]$_.command })
        if ($cmds -match 'record-unity-action\.ps1') { $w += $ev }
    }
    return $w
}
if ($Agents -contains 'claude') {
    Try-Check 'Claude Code' {
        $cmd = Get-Command claude -ErrorAction SilentlyContinue
        $v = if ($cmd) { (Run $cmd.Source @('--version')).out } else { $null }
        if ($cmd) { Add-Result PASS 'Claude Code' "$v ($($cmd.Source)); sign-in is not detectable: run claude once and sign in" }
        else { Add-Result WARN 'Claude Code' 'claude not on PATH (the desktop app alone also works)' 'install Claude Code (https://claude.com/claude-code) or the Claude desktop app, then sign in' }
    }
    Try-Check 'Claude Code hooks' {
        $sp = Join-Path $ClaudeDir 'settings.json'
        $events = @('PostToolUse', 'PostToolUseFailure', 'Stop')
        $wired = if (Test-Path $sp) { @(Get-WiredEvents ([IO.File]::ReadAllText($sp) | ConvertFrom-Json) $events) } else { @() }
        if ($wired.Count -eq $events.Count) { Add-Result PASS 'Claude Code hooks' "$sp wires $($events -join ', ')" }
        else { Add-Result FAIL 'Claude Code hooks' "$sp wires: $(if ($wired) { $wired -join ', ' } else { 'none' })" 'machine\bootstrap.ps1 -Agent claude (asks before installing them)' }
    }
}
if ($Agents -contains 'codex') {
    Try-Check 'Codex' {
        $cmd = Get-Command codex -ErrorAction SilentlyContinue
        if (-not $cmd) { Add-Result FAIL 'Codex' 'codex not on PATH' 'winget install -e --id OpenAI.Codex (or npm install -g @openai/codex), then codex login'; return }
        $v = (Run $cmd.Source @('--version')).out
        $s = Run $cmd.Source @('login', 'status')   # exit 0 and "Logged in using ..." when signed in
        if ($s.code -eq 0) { Add-Result PASS 'Codex' "$v; $(($s.out -split "`n")[0])" }
        else { Add-Result FAIL 'Codex' "$v; not signed in" 'codex login (ChatGPT account in the browser; or --device-auth)' }
    }
    Try-Check 'Codex hooks' {
        $hp = Join-Path $CodexDir 'hooks.json'
        $events = @('PostToolUse', 'Stop')
        $h = if (Test-Path $hp) { [IO.File]::ReadAllText($hp) | ConvertFrom-Json } else { $null }
        $wired = if ($h) { @(Get-WiredEvents $h $events) } else { @() }
        if ($wired.Count -ne $events.Count) { Add-Result FAIL 'Codex hooks' "$hp wires: $(if ($wired) { $wired -join ', ' } else { 'none' })" 'machine\bootstrap.ps1 -Agent codex (asks before installing them)'; return }
        # an untrusted or changed hook is skipped by Codex without a word: compare the trust entries
        $state = Get-UGFCodexTrustState (Join-Path $CodexDir 'config.toml')
        $trust = @(Get-UGFCodexHookTrust $hp $h)
        $bad = @($trust | Where-Object { $state[$_.key] -ne $_.hash -and $state["\\?\$($_.key)"] -ne $_.hash } | ForEach-Object { $_.event })
        if (-not $bad) { Add-Result PASS 'Codex hooks' "$hp wires $($events -join ', '); trusted in config.toml" }
        else { Add-Result FAIL 'Codex hooks' "wired but not trusted (Codex skips them): $($bad -join ', ')" 'machine\bootstrap.ps1 -Agent codex, or in Codex type /hooks and trust the record-unity-action.ps1 hooks' }
    }
}
Try-Check 'Skills' {
    $names = @(Get-ChildItem (Join-Path $repo 'skills') -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like 'unity-*' } | Select-Object -ExpandProperty Name)
    if (-not $names) { Add-Result FAIL 'Skills' "no unity-* skills in $(Join-Path $repo 'skills')" 'pull unity-game-factory'; return }
    $where = @()
    if ($Agents -contains 'claude') { $where += , @('Claude Code', (Join-Path $ClaudeDir 'skills')) }
    if ($Agents -contains 'codex') { $where += , @('Codex', $AgentsSkillsDir) }
    $bad = @(foreach ($w in $where) { foreach ($n in $names) { if (-not (Same-File (Join-Path $repo "skills\$n\SKILL.md") (Join-Path $w[1] "$n\SKILL.md"))) { "$($w[0]): $n" } } })
    if (-not $bad) { Add-Result PASS 'Skills' "$($names -join ', ') in $(($where | ForEach-Object { $_[1] }) -join ' and ')" }
    else { Add-Result FAIL 'Skills' "missing or outdated: $($bad -join ', ')" 'machine\bootstrap.ps1' }
}
if ($Agents -contains 'claude') {
    Try-Check 'Root CLAUDE.md' {
        $p = Join-Path $Root 'CLAUDE.md'
        if ((Test-Path $p) -and ((Get-Content $p -Raw) -match '@.*unity-game-factory/CLAUDE\.md|@.*/CLAUDE\.md')) { Add-Result PASS 'Root CLAUDE.md' "$p imports the repo CLAUDE.md" }
        else { Add-Result FAIL 'Root CLAUDE.md' "$p missing or not importing unity-game-factory/CLAUDE.md" 'machine\bootstrap.ps1' }
    }
}
if ($Agents -contains 'codex') {
    Try-Check 'Root AGENTS.md' {
        $p = Join-Path $Root 'AGENTS.md'
        if ((Test-Path $p) -and ((Get-Content $p -Raw) -match [regex]::Escape((Join-Path $repo 'AGENTS.md')))) { Add-Result PASS 'Root AGENTS.md' "$p names the repo AGENTS.md" }
        else { Add-Result FAIL 'Root AGENTS.md' "$p missing or not naming $(Join-Path $repo 'AGENTS.md')" 'machine\bootstrap.ps1' }
    }
}
Try-Check 'Game repos record commits' {
    # _-prefixed folders (e.g. _pipeline-test) are tool test projects, not game data
    $repos = @(Get-ChildItem (Join-Path $Root 'games') -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike '_*' -and (Test-Path (Join-Path $_.FullName '.git')) })
    if (-not $repos) { Add-Result PASS 'Game repos record commits' 'no game repos yet'; return }
    $missing = @($repos | Where-Object {
        $h = Join-Path $_.FullName '.git\hooks\post-commit'
        -not ((Test-Path $h) -and ((Get-Content $h -Raw) -match 'record-unity-commit\.ps1'))
    } | Select-Object -ExpandProperty Name)
    if (-not $missing) { Add-Result PASS 'Game repos record commits' "$($repos.Count) repo(s)" } else { Add-Result FAIL 'Game repos record commits' "no recorder in: $($missing -join ', ')" 'machine\install-git-hook.ps1 <repo> (bootstrap.ps1 does all)' }
}

# --- content ---------------------------------------------------------------------------------------------------------
Try-Check 'Asset library' {
    # Store packs reach a game two ways: the Unity Asset Store's download cache (Package Manager > My Assets > Download
    # writes .unitypackage files to %APPDATA%\Unity\Asset Store-5.x\<publisher>\<category>\) and <root>\asset-library\
    # (packs from other stores and free sources). Cloned games carry the packs they use (committed through LFS), so the
    # library only feeds NEW games: never a FAIL.
    $lib = Join-Path $Root 'asset-library'
    $store = Join-Path $env:APPDATA 'Unity\Asset Store-5.x'
    $nStore = if (Test-Path $store) { @(Get-ChildItem $store -Recurse -Filter *.unitypackage -File -ErrorAction SilentlyContinue).Count } else { 0 }
    $nLib = if (Test-Path $lib) { @(Get-ChildItem $lib -Directory -ErrorAction SilentlyContinue).Count } else { 0 }
    $detail = "$nStore .unitypackage file(s) in $store; $nLib folder(s) in $lib"
    if ($nStore -or $nLib) { Add-Result PASS 'Asset library' $detail }
    else { Add-Result WARN 'Asset library' $detail 'needed only for new games: sign in to Unity Hub / the Asset Store with the account that owns the packs and download them (Package Manager > My Assets), or put other packs under asset-library\' }
}

# --- report ------------------------------------------------------------------------------------------------------------
$colors = @{ PASS = 'Green'; WARN = 'Yellow'; FAIL = 'Red' }
Write-Host ""
Write-Host "unity-game-factory machine check  (root $Root, agents $($Agents -join ' + '), hooks dir $HooksDir)"
foreach ($r in $results) {
    Write-Host ("  {0}  {1,-30} {2}" -f $r.status, $r.check, $r.detail) -ForegroundColor $colors[$r.status]
    if ($r.status -ne 'PASS' -and $r.fix) { Write-Host ("        fix: {0}" -f $r.fix) -ForegroundColor DarkGray }
}
$nFail = @($results | Where-Object status -eq 'FAIL').Count
$nWarn = @($results | Where-Object status -eq 'WARN').Count
Write-Host ("{0} checks: {1} PASS, {2} WARN, {3} FAIL" -f $results.Count, ($results.Count - $nFail - $nWarn), $nWarn, $nFail)
if ($Json) {
    $obj = [ordered]@{ time = (Get-Date).ToString('o'); root = $Root; agents = $Agents; hooks_dir = $HooksDir; claude_dir = $ClaudeDir; codex_dir = $CodexDir; fail = $nFail; warn = $nWarn; results = $results }
    [IO.File]::WriteAllText($Json, ($obj | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
}
exit $nFail
