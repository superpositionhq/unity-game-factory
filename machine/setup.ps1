<#
.SYNOPSIS
  One entry point for a clean Windows 11 PC: from nothing to building Unity games. Idempotent and resumable: run it
  again after any manual step (or reboot) and it continues where it stopped.
.DESCRIPTION
  1. Hardware precheck against the stated minimums (below).
  2. Software through winget (asks once, lists what is missing; winget accepts each package's licence):
     Git (+ Git LFS), GitHub CLI, Python 3.12, 7-Zip, Unity Hub, the Codex CLI when Codex is one of the agents, and the
     Claude desktop app (optional) when Claude Code is.
  3. Windows settings, each asked first: long paths (admin, one UAC prompt) and no sleep while plugged in (display and
     PC; powercfg on the current power plan).
  4. GitHub sign-in (gh auth login in the browser) and git user.name / user.email; Codex sign-in (codex login in the
     browser) when Codex is one of the agents.
  5. unity-game-factory: cloned into <root>\unity-game-factory when this script runs from outside a clone, then
     machine\bootstrap.ps1 (config, tools, hooks after its own question, skills; -CloneGames when you say so) and
     machine\check.ps1.
  6. What cannot be scripted (Unity Hub sign-in with a Unity ID and a licence, the Unity 6.3 LTS editor with Windows
     Build Support (IL2CPP), the NVIDIA driver, signing in to Claude Code): exact steps, detected on the next run.
  The coding agent: -Agent claude (Claude Code), codex (OpenAI Codex CLI) or both; asked on the first run (remembered),
  passed on to bootstrap.ps1, which wires the recording hooks, skills and root instructions into each.
  Ends with a PASS / TODO list. Log: <root>\.setup\setup.log; answers: <root>\.setup\state.json (not asked again).
  The Unreal game-factory may already be set up on this PC: this one uses its own root, config, hooks and skills
  (unity-*) and leaves that one's alone; the two share only the machine-wide job slots.

  Minimums: Windows 11; 8 logical cores and 16 GB RAM (32 GB recommended: job slots scale with RAM); 200 GB free on
  the root's drive (100 GB at the very least; game repos with their store packs and each project's Library\ cache are
  several GB each, builds and the asset library grow); a DirectX 11/12 GPU for the editor. Recording gameplay (the
  recorder is not available yet) wants an NVIDIA GPU (8 GB+ VRAM, driver 610+, NVENC); without one it falls back to
  slower encoders.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org>
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org> -Agent codex
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org> -Root D:\UnityWork -CloneGames
  # dry run against a scratch root (installs, Windows settings, sign-ins and game clones are only reported):
  powershell -ExecutionPolicy Bypass -File machine\setup.ps1 -Org <org> -DryRun -Root C:\ugf-test\UnityWork `
      -ClaudeDir C:\ugf-test\home\.claude -CodexDir C:\ugf-test\home\.codex -AgentsSkillsDir C:\ugf-test\home\.agents\skills `
      -HooksDir C:\ugf-test\home\.unity-game-factory\hooks -ConfigPath C:\ugf-test\home\.unity-game-factory\config.json -Agent both
#>
param(
    [string]$Root,                     # default: the config's root, else asked (%USERPROFILE%\UnityWork offered)
    [string]$Org,                      # GitHub org/user that owns unity-game-factory and the game repos (config github_org)
    [switch]$CloneGames,               # also clone every <org>/unity-game-* repo (asked when not given)
    [switch]$Yes,                      # answer yes to every question (installs, settings, hooks)
    [switch]$DryRun,                   # no installs, Windows settings, sign-ins or game clones; bootstrap runs only
                                       # given -ConfigPath, -ClaudeDir, -CodexDir, -AgentsSkillsDir and -HooksDir
    [string]$RepoUrl,                  # where to clone unity-game-factory from (default https://github.com/<org>/unity-game-factory)
    [ValidateSet('', 'claude', 'codex', 'both')][string]$Agent = '',   # the coding agent(s); asked when not given
    [string]$ClaudeDir = (Join-Path $env:USERPROFILE '.claude'),
    [string]$CodexDir,                 # default: CODEX_HOME / %USERPROFILE%\.codex
    [string]$AgentsSkillsDir,          # default: %USERPROFILE%\.agents\skills (Codex's personal skills)
    [string]$HooksDir,                 # default: the config's hooks_dir
    [string]$ConfigPath,
    [switch]$SkipFfmpeg
)
$ErrorActionPreference = 'Stop'
$UnityLts = '6000.3'   # Unity 6.3 LTS: new games use its newest installed patch (config unity_version: a series or exact)
$items = New-Object Collections.Generic.List[object]
function Item([string]$Status, [string]$What, [string]$Detail = '', [string]$Todo = '') {
    $items.Add([pscustomobject]@{ status = $Status; what = $What; detail = $Detail; todo = $Todo })
    $c = @{ PASS = 'Green'; TODO = 'Yellow'; INFO = 'DarkGray'; SKIP = 'DarkGray' }[$Status]
    Write-Host ("  [{0}] {1}{2}" -f $Status, $What, $(if ($Detail) { " - $Detail" } else { '' })) -ForegroundColor $c
}
$interactive = [Environment]::UserInteractive -and -not [Console]::IsInputRedirected
function Ask([string]$Question, [bool]$Default = $false) {
    if ($Yes) { return $true }
    if (-not $interactive) { return $false }
    $hint = if ($Default) { '[Y/n]' } else { '[y/N]' }
    $a = (Read-Host "  $Question $hint").Trim()
    if (-not $a) { return $Default }
    return ($a -match '^(y|yes)$')
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Has([string]$Cmd) { [bool](Get-Command $Cmd -ErrorAction SilentlyContinue) }
function Quiet([scriptblock]$Body) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $out = & $Body 2>&1 | ForEach-Object { "$_" }; return [pscustomobject]@{ code = $LASTEXITCODE; out = ($out -join "`n") } }
    catch { return [pscustomobject]@{ code = -1; out = $_.Exception.Message } }
    finally { $ErrorActionPreference = $old }
}

# --- where things go -------------------------------------------------------------------------------------------------
if ($ConfigPath) { $env:UGF_CONFIG = $ConfigPath }
$cfgFile = if ($env:UGF_CONFIG) { $env:UGF_CONFIG } else { Join-Path $env:USERPROFILE '.unity-game-factory\config.json' }
$cfgNow = if (Test-Path -LiteralPath $cfgFile) { [IO.File]::ReadAllText($cfgFile) | ConvertFrom-Json } else { $null }
if (-not $Root -and $env:UGF_ROOT) { $Root = $env:UGF_ROOT }
if (-not $Root -and $cfgNow -and $cfgNow.root) { $Root = [string]$cfgNow.root }
if (-not $Root) {
    $def = Join-Path $env:USERPROFILE 'UnityWork'
    $Root = if ($interactive -and -not $Yes) { $r = (Read-Host "  Machine root for unity-game-factory, games, builds and recordings [$def]").Trim(); if ($r) { $r } else { $def } } else { $def }
}
$Root = [IO.Path]::GetFullPath($Root.TrimEnd('\'))
$setupDir = Join-Path $Root '.setup'
New-Item -ItemType Directory -Force $setupDir | Out-Null
$statePath = Join-Path $setupDir 'state.json'
$state = if (Test-Path -LiteralPath $statePath) { [IO.File]::ReadAllText($statePath) | ConvertFrom-Json } else { [pscustomobject]@{} }
function Save-State([string]$Key, $Value) {
    if ($state.PSObject.Properties[$Key]) { $state.$Key = $Value } else { $state | Add-Member $Key $Value }
    [IO.File]::WriteAllText($statePath, ($state | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
}
function Get-State([string]$Key) { if ($state.PSObject.Properties[$Key]) { return $state.$Key } return $null }
try { Start-Transcript -Path (Join-Path $setupDir 'setup.log') -Append | Out-Null } catch { }
Write-Host "unity-game-factory setup: root $Root$(if ($DryRun) { ' (dry run: nothing is installed or changed outside the root and the scratch folders given)' })"

if (-not $Org -and $cfgNow -and $cfgNow.PSObject.Properties['github_org']) { $Org = [string]$cfgNow.github_org }
if (-not $Org) { $Org = Get-State 'org' }
if (-not $Org -and $interactive) { $Org = (Read-Host '  GitHub organisation (or user) that owns unity-game-factory and the unity-game-<slug> repos').Trim() }
if ($Org) { Save-State 'org' $Org }

# Which coding agent(s): -Agent, else the previous answer, else the config's "agents", else asked (Claude Code, Codex
# or both); a non-interactive run without an answer takes what is installed (bootstrap.ps1 -Agent auto).
if (-not $Agent) { $Agent = [string](Get-State 'agent') }
if (-not $Agent -and $cfgNow -and $cfgNow.PSObject.Properties['agents'] -and @($cfgNow.agents).Count) {
    $Agent = if (@($cfgNow.agents).Count -ge 2) { 'both' } else { [string]@($cfgNow.agents)[0] }
}
if (-not $Agent -and $interactive -and -not $Yes) {
    $a = (Read-Host '  Coding agent: claude (Claude Code), codex (OpenAI Codex CLI) or both [claude]').Trim().ToLower()
    $Agent = if ($a -in 'codex', 'both') { $a } else { 'claude' }
}
if ($Agent) { Save-State 'agent' $Agent }
$useClaude = $Agent -in '', 'claude', 'both'
$useCodex = $Agent -in 'codex', 'both'
Write-Host "  agent: $(if ($Agent) { $Agent } else { 'auto (what is installed)' })"

# --- 1. hardware -------------------------------------------------------------------------------------------------------
Write-Host "1. hardware (minimums: Windows 11, 8 threads, 16 GB RAM, 200 GB free; NVIDIA for recording)"
$os = Get-CimInstance Win32_OperatingSystem
$build = [int]$os.BuildNumber
if ($build -ge 22000) { Item PASS 'Windows' "$($os.Caption) build $build" } else { Item TODO 'Windows' "$($os.Caption) build $build" 'Windows 11 is required (desktop capture for recordings)' }
$cs = Get-CimInstance Win32_ComputerSystem
$ram = [math]::Round($cs.TotalPhysicalMemory / 1GB)
$cores = [int]$cs.NumberOfLogicalProcessors
if ($cores -ge 8) { Item PASS 'CPU' "$cores logical cores" } else { Item TODO 'CPU' "$cores logical cores" 'at least 8 logical cores (imports and player builds are slow and the job limiter allows one job)' }
if ($ram -ge 32) { Item PASS 'Memory' "$ram GB" } elseif ($ram -ge 16) { Item PASS 'Memory' "$ram GB (32 GB recommended; fewer parallel jobs)" } else { Item TODO 'Memory' "$ram GB" 'at least 16 GB RAM (32 GB recommended)' }
$drive = (Split-Path -Qualifier $Root).TrimEnd(':')
$free = [math]::Round((Get-PSDrive -Name $drive).Free / 1GB)
if ($free -ge 200) { Item PASS 'Free disk' "$free GB on ${drive}:" }
elseif ($free -ge 100) { Item PASS 'Free disk' "$free GB on ${drive}: (200 GB recommended)" }
else { Item TODO 'Free disk' "$free GB on ${drive}:" "free space or pick a roomier drive (-Root <drive>:\UnityWork): at least 100 GB, 200 GB recommended" }
$gpus = @(Get-CimInstance Win32_VideoController | Where-Object { $_.Name -notmatch 'Microsoft Basic|Remote|Virtual' })
$nv = @($gpus | Where-Object { $_.Name -match 'NVIDIA' })
Item $(if ($gpus) { 'PASS' } else { 'TODO' }) 'GPU' $(if ($gpus) { ($gpus.Name -join ', ') } else { 'no display adapter found' }) 'a DirectX 11/12 GPU for the Unity editor'
if (-not $nv) { Item INFO 'NVIDIA GPU' 'none: building works; recording falls back to AMF / CPU encoding (slower)' }

# --- 2. software -----------------------------------------------------------------------------------------------------
Write-Host "2. software (winget)"
function Test-Python { foreach ($c in @('py -3.12', 'python')) { $r = Quiet { Invoke-Expression "$c -c `"import sys; print(sys.version_info[1])`"" }; if ($r.code -eq 0 -and $r.out -match '^\d+$' -and [int]$r.out -ge 10) { return $true } }; return $false }
# winget and the Microsoft Store install Hub as an MSIX package (WindowsApps\UnityTechnologies.UnityHub_*\app\), the
# classic installer in Program Files (the same lookup as lib\ugf-root.ps1 Get-UGFUnityHub; setup runs before the clone)
function Get-UnityHubExe {
    $hub = @("$env:ProgramFiles\Unity Hub\Unity Hub.exe", "${env:LOCALAPPDATA}\Programs\Unity Hub\Unity Hub.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($hub) { return $hub }
    try {
        $pkg = Get-AppxPackage -Name 'UnityTechnologies.UnityHub' -ErrorAction Stop | Sort-Object Version -Descending | Select-Object -First 1
        if ($pkg) { $exe = Join-Path $pkg.InstallLocation 'app\Unity Hub.exe'; if (Test-Path -LiteralPath $exe) { return $exe } }
    } catch { }
    return $null
}
$packages = @(
    @{ id = 'Git.Git'; name = 'Git'; test = { Has git } },
    @{ id = 'GitHub.GitLFS'; name = 'Git LFS'; test = { (Has git) -and (Quiet { git lfs version }).code -eq 0 } },
    @{ id = 'GitHub.cli'; name = 'GitHub CLI'; test = { Has gh } },
    @{ id = 'Python.Python.3.12'; name = 'Python 3.12'; test = { Test-Python } },
    @{ id = '7zip.7zip'; name = '7-Zip'; test = { (Has 7z) -or (Test-Path "$env:ProgramFiles\7-Zip\7z.exe") } },
    @{ id = 'Unity.UnityHub'; name = 'Unity Hub'; test = { [bool](Get-UnityHubExe) } },
    @{ id = 'Anthropic.Claude'; name = 'Claude desktop app (optional: Code tab, coordinator mode)'; optional = $true; agent = 'claude'; test = { (Test-Path "$env:LOCALAPPDATA\AnthropicClaude\claude.exe") -or [bool](Get-AppxPackage -Name '*Claude*' -ErrorAction SilentlyContinue) } },
    @{ id = 'OpenAI.Codex'; name = 'Codex CLI (OpenAI)'; agent = 'codex'; test = { Has codex } }
)
$packages = @($packages | Where-Object { -not $_.agent -or ($_.agent -eq 'claude' -and $useClaude) -or ($_.agent -eq 'codex' -and $useCodex) })
$missing = @($packages | Where-Object { -not (& $_.test) })
foreach ($p in $packages) { if ($missing -notcontains $p) { Item PASS $p.name 'installed' } }
if ($missing) {
    $hasWinget = Has winget
    if (-not $hasWinget) { Item TODO 'winget' 'not found' 'install "App Installer" from the Microsoft Store, then run setup again' }
    Write-Host ("  missing: " + (($missing | ForEach-Object { $_.name }) -join '; '))
    $want = @($missing | Where-Object { -not $_.optional })
    $opt = @($missing | Where-Object { $_.optional })
    $go = $hasWinget -and -not $DryRun -and $want -and (Ask "Install these with winget (accepting each package's licence; some show a UAC prompt)?" $true)
    $goOpt = $hasWinget -and -not $DryRun -and $opt -and (Ask "Also install: $(($opt | ForEach-Object { $_.name }) -join ', ')?" $false)
    foreach ($p in $missing) {
        $run = if ($p.optional) { $goOpt } else { $go }
        if (-not $run) { Item TODO $p.name $(if ($DryRun) { 'missing (dry run)' } else { 'missing' }) "winget install -e --id $($p.id)"; continue }
        Write-Host "  winget install $($p.id) ..."
        & winget @('install', '-e', '--id', $p.id, '--accept-package-agreements', '--accept-source-agreements', '--silent') | Out-Host
        Refresh-Path
        if (& $p.test) { Item PASS $p.name 'installed now' } else { Item TODO $p.name 'install did not complete' "winget install -e --id $($p.id) (or re-run setup; a reboot may be needed)" }
    }
}
if (Has git) {
    if (-not (Quiet { git config --get filter.lfs.process }).out) { if (-not $DryRun) { Quiet { git lfs install --skip-repo } | Out-Null } }
}

# --- 3. Windows settings ------------------------------------------------------------------------------------------------
Write-Host "3. Windows settings"
$lp = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled
if ($lp -eq 1) { Item PASS 'Long paths' 'enabled' }
elseif ($DryRun -or (Get-State 'long_paths') -eq 'declined') { Item TODO 'Long paths' 'off' 'optional: as admin, Set-ItemProperty HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem LongPathsEnabled 1 (store packs and Library\PackageCache nest deeply)' }
elseif (Ask 'Enable Windows long paths (store packs and package caches nest deeply; one UAC prompt)?' $true) {
    Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile', '-Command', "Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -Value 1 -Type DWord"
    $lp = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue).LongPathsEnabled
    if ($lp -eq 1) { Item PASS 'Long paths' 'enabled now' } else { Item TODO 'Long paths' 'still off' 'run setup again and accept the UAC prompt' }
} else { Save-State 'long_paths' 'declined'; Item SKIP 'Long paths' 'declined (keep the root short, e.g. C:\UnityWork)' }
function Get-AcMinutes([string]$Sub, [string]$Setting) {
    $r = Quiet { powercfg /query SCHEME_CURRENT $Sub $Setting }
    $hex = @([regex]::Matches($r.out, '0x[0-9a-fA-F]{8}') | ForEach-Object { $_.Value })
    if ($hex.Count -lt 2) { return $null }; return [int]([Convert]::ToInt32($hex[-2], 16) / 60)
}
$sleep = Get-AcMinutes 'SUB_SLEEP' 'STANDBYIDLE'; $disp = Get-AcMinutes 'SUB_VIDEO' 'VIDEOIDLE'
if ($sleep -eq 0 -and $disp -eq 0) { Item PASS 'No sleep while plugged in' 'PC and display: never (AC)' }
elseif ($DryRun -or (Get-State 'power') -eq 'declined') { Item TODO 'No sleep while plugged in' "PC sleeps after $sleep min, display after $disp min (AC)" 'powercfg /change standby-timeout-ac 0; powercfg /change monitor-timeout-ac 0' }
elseif (Ask "Set the PC and display to never sleep while plugged in (long builds, overnight queues; now $sleep / $disp min)?" $true) {
    Quiet { powercfg /change standby-timeout-ac 0 } | Out-Null; Quiet { powercfg /change monitor-timeout-ac 0 } | Out-Null
    Item PASS 'No sleep while plugged in' 'set (AC: never)'
} else { Save-State 'power' 'declined'; Item SKIP 'No sleep while plugged in' 'declined' }

# --- 4. GitHub sign-in and git identity ------------------------------------------------------------------------------
Write-Host "4. GitHub and git"
$ghOk = $false
if (Has gh) {
    $ghOk = (Quiet { gh auth status }).code -eq 0
    if (-not $ghOk -and -not $DryRun -and $interactive) {
        Write-Host '  GitHub sign-in: a browser page opens; sign in with the account that is a member of the org.'
        & gh auth login --hostname github.com --git-protocol https --web
        $ghOk = (Quiet { gh auth status }).code -eq 0
    }
    if ($ghOk) { if (-not $DryRun) { Quiet { gh auth setup-git } | Out-Null }; Item PASS 'GitHub sign-in' (Quiet { gh api user --jq .login }).out }
    else { Item TODO 'GitHub sign-in' 'not signed in' 'gh auth login --web (then run setup again)' }
} else { Item TODO 'GitHub sign-in' 'needs the GitHub CLI' 'install it (step 2), then run setup again' }
if (Has git) {
    foreach ($k in 'user.name', 'user.email') {
        $v = (Quiet { git config --global --get $k }).out
        if (-not $v -and -not $DryRun -and $interactive -and -not $Yes) { $v = (Read-Host "  git $k (for your commits)").Trim(); if ($v) { Quiet { git config --global $k $v } | Out-Null } }
        if ($v) { Item PASS "git $k" $v } else { Item TODO "git $k" 'not set' "git config --global $k `"<value>`"" }
    }
}
if ($useCodex) {
    # Codex sign-in: `codex login status` exits 0 when signed in (ChatGPT account or API key).
    if (-not (Has codex)) { Item TODO 'Codex sign-in' 'needs the Codex CLI' 'install it (step 2), then run setup again' }
    else {
        $cxOk = (Quiet { codex login status }).code -eq 0
        if (-not $cxOk -and -not $DryRun -and $interactive) {
            Write-Host '  Codex sign-in: a browser page opens; sign in with the ChatGPT account (or the API key) you were given.'
            & codex login
            $cxOk = (Quiet { codex login status }).code -eq 0
        }
        if ($cxOk) { Item PASS 'Codex sign-in' ((Quiet { codex login status }).out -split "`n")[0] }
        else { Item TODO 'Codex sign-in' 'not signed in' 'codex login (or codex login --device-auth), then run setup again' }
    }
}
if (-not $Org) { Item TODO 'GitHub org' 'not set' 'run setup again with -Org <org> (the organisation or user that owns unity-game-factory)' }
elseif ($ghOk) {
    $see = (Quiet { gh repo view "$Org/unity-game-factory" --json name }).code -eq 0
    if ($see) { Item PASS 'GitHub org' "$Org/unity-game-factory visible" } else { Item TODO 'GitHub org' "cannot see $Org/unity-game-factory" "ask an owner of $Org to add your account (with rights to create private repos)" }
}

# --- 5. unity-game-factory, bootstrap, check ---------------------------------------------------------------------------
Write-Host "5. unity-game-factory"
$here = Split-Path $PSScriptRoot -Parent
$inClone = (Test-Path (Join-Path $here 'machine\bootstrap.ps1')) -and (Test-Path (Join-Path $here '.git'))
$repo = if ($inClone) { $here } else { Join-Path $Root 'unity-game-factory' }
if (-not (Test-Path (Join-Path $repo 'machine\bootstrap.ps1'))) {
    $src = if ($RepoUrl) { $RepoUrl } elseif ($Org) { "https://github.com/$Org/unity-game-factory.git" } else { $null }
    if (-not $src -or -not (Has git) -or ($src -like 'https://github.com/*' -and -not $ghOk)) { Item TODO 'unity-game-factory clone' "not at $repo" 'needs git, GitHub sign-in and the org (steps above); then run setup again' }
    elseif ($DryRun -and -not $RepoUrl) { Item TODO 'unity-game-factory clone' "would clone $src into $repo (dry run)" '' }
    else {
        Write-Host "  cloning $src into $repo ..."
        $r = Quiet { git clone --quiet $src $repo }
        if ($r.code -eq 0) { Item PASS 'unity-game-factory clone' $repo } else { Item TODO 'unity-game-factory clone' "git clone failed: $($r.out)" "git clone $src $repo" }
    }
} else { Item PASS 'unity-game-factory clone' $repo }
$bootstrapOk = $false
# A dry run changes nothing outside the root, and bootstrap.ps1 writes the config, the hooks dir, the skills and (after
# its question) the agents' settings: in a dry run it runs only when every one of those is given (a scratch home).
$notGiven = @('ConfigPath', 'ClaudeDir', 'CodexDir', 'AgentsSkillsDir', 'HooksDir' | Where-Object { -not $PSBoundParameters.ContainsKey($_) })
if ($DryRun -and $notGiven) { Item INFO 'bootstrap.ps1' "not run: a dry run runs it only with every scratch folder given (missing -$($notGiven -join ', -'))" }
elseif (Test-Path (Join-Path $repo 'machine\bootstrap.ps1')) {
    $clone = $CloneGames.IsPresent
    if (-not $clone) {
        $prev = Get-State 'clone_games'
        if ($null -ne $prev) { $clone = [bool]$prev }
        elseif ($interactive -and -not $DryRun) {
            $clone = Ask "Clone every $Org/unity-game-* repo into $Root\games now (each brings its store packs; several GB each)?" $false
            Save-State 'clone_games' $clone
        }
    }
    $ba = [ordered]@{ Root = $Root; ClaudeDir = $ClaudeDir }
    if ($Agent) { $ba.Agent = $Agent }
    if ($CodexDir) { $ba.CodexDir = $CodexDir }
    if ($AgentsSkillsDir) { $ba.AgentsSkillsDir = $AgentsSkillsDir }
    if ($HooksDir) { $ba.HooksDir = $HooksDir }
    if ($Org) { $ba.Org = $Org }
    if ($env:UGF_CONFIG) { $ba.ConfigPath = $env:UGF_CONFIG }
    if ($Yes) { $ba.Yes = $true }
    if ($clone -and -not $DryRun) { $ba.CloneGames = $true }
    if ($SkipFfmpeg) { $ba.SkipFfmpeg = $true }
    Write-Host "  machine\bootstrap.ps1 ..."
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'machine\bootstrap.ps1') @(foreach ($k in $ba.Keys) { if ($ba[$k] -is [bool]) { "-$k" } else { "-$k"; $ba[$k] } })
    $bootstrapOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $old
    if ($bootstrapOk) { Item PASS 'bootstrap.ps1' 'done (its warnings are above)' } else { Item TODO 'bootstrap.ps1' "exit $LASTEXITCODE" 'read the bootstrap output above, fix, run setup again' }
}

# --- 6. what cannot be scripted -------------------------------------------------------------------------------------------
Write-Host "6. sign-ins and installs only you can do"
$cfgNew = if (Test-Path -LiteralPath $cfgFile) { [IO.File]::ReadAllText($cfgFile) | ConvertFrom-Json } else { $null }
$hubEditors = if ($cfgNew -and $cfgNew.unity_hub_editors) { [string]$cfgNew.unity_hub_editors } else { 'C:\Program Files\Unity\Hub\Editor' }
$wantVer = if ($cfgNew -and $cfgNew.unity_version) { [string]$cfgNew.unity_version } else { $UnityLts }
# the editors installed (as lib\ugf-root.ps1 Get-UGFInstalledUnity), and the one new games use: a series is its newest
# final patch, an exact version itself (Get-UGFUnityVersion)
$have = @(Get-ChildItem -LiteralPath $hubEditors -Directory -ErrorAction SilentlyContinue | Where-Object { Test-Path (Join-Path $_.FullName 'Editor\Unity.exe') } | ForEach-Object Name)
if ($cfgNew -and $cfgNew.unity_editors) { $have += @($cfgNew.unity_editors.PSObject.Properties | Where-Object { Test-Path -LiteralPath ([string]$_.Value) } | ForEach-Object Name) }
$useVer = if ($wantVer -notmatch '^\d+\.\d+$') { @($have) -eq $wantVer | Select-Object -First 1 } else {
    @($have | Where-Object { $_ -match ('^' + [regex]::Escape($wantVer) + '\.\d+f\d+$') } | Sort-Object { [int]($_.Split('.')[2] -replace 'f.*') }, { [int]($_ -replace '^.*f') } -Descending) | Select-Object -First 1
}
if (Get-UnityHubExe) {
    # the licence Unity Hub writes for a signed-in account, or a serial licence (as check.ps1 'Unity licence')
    $lic = @((Join-Path $env:LOCALAPPDATA 'Unity\licenses\UnityEntitlementLicense.xml'), (Join-Path $env:ProgramData 'Unity\Unity_lic.ulf')) | Where-Object { Test-Path -LiteralPath $_ }
    if ($lic) { Item PASS 'Unity licence' ($lic -join '; ') }
    else { Item INFO 'Unity licence' 'open Unity Hub, sign in with a Unity ID (create one if needed) and activate a licence (Preferences > Licenses > Add; Personal is fine): every editor run needs one' }
}
if ($useVer) { Item PASS 'Unity 6.3 LTS editor' "$useVer (unity_version $wantVer)" }
else {
    Item TODO 'Unity 6.3 LTS editor' "no $wantVer editor in $hubEditors" ("in Unity Hub: Installs > Install Editor > Unity 6.3 (LTS), the newest 6000.3 patch " +
        "(an exact unity_version: that version, under Archive), with the module Windows Build Support (IL2CPP); about 10 GB. Then run setup again.")
}
Item INFO 'C++ tools for IL2CPP' 'only for IL2CPP player builds: Visual Studio 2022 (or Build Tools) with "Desktop development with C++" (check.ps1 reports it)'
if ($nv) {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    $drv = if ($smi) { [double](((Quiet { & $smi.Source --query-gpu=driver_version --format=csv,noheader }).out -split "`n")[0] -replace '[^\d.]', '') } else { 0 }
    if ($drv -ge 610) { Item PASS 'NVIDIA driver' "$drv" } else { Item TODO 'NVIDIA driver' $(if ($drv) { "$drv" } else { 'nvidia-smi not found' }) 'install the current Game Ready or Studio driver (610 or newer) from nvidia.com/drivers or the NVIDIA app, then run setup again' }
}
Item INFO 'Asset Store' 'only to download store packs for a NEW game: sign in to the Unity Asset Store with the account that owns them (Package Manager > My Assets); cloned games already carry their packs'
if ($useClaude) { Item INFO 'Claude Code sign-in' 'run claude once (or open the desktop app) and sign in with your account; not detectable' }
Item INFO 'First session' "start Claude Code (claude) or Codex (codex) in $Root and paste the brief (docs/new-machine.md, 'The first session')"


# --- check + summary -----------------------------------------------------------------------------------------------------
$check = Join-Path $repo 'machine\check.ps1'
if (Test-Path $check) {
    Write-Host "7. machine\check.ps1"
    $json = Join-Path $setupDir 'check.json'
    $ca = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $check, '-Root', $Root, '-ClaudeDir', $ClaudeDir, '-Json', $json)
    if ($CodexDir) { $ca += @('-CodexDir', $CodexDir) }
    if ($AgentsSkillsDir) { $ca += @('-AgentsSkillsDir', $AgentsSkillsDir) }
    if ($HooksDir) { $ca += @('-HooksDir', $HooksDir) }
    if ($env:UGF_CONFIG) { $ca += @('-ConfigPath', $env:UGF_CONFIG) }
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & powershell @ca | Out-Null
    $ErrorActionPreference = $old
    if (Test-Path $json) {
        $cr = [IO.File]::ReadAllText($json) | ConvertFrom-Json
        # check.ps1 rows that setup already reported above (same subject under setup's name)
        $same = @{ 'Unity 6.3 LTS editor' = 'Unity 6.3 LTS editor'; 'Unity Hub' = 'Unity Hub'; 'Unity licence' = 'Unity licence'; 'Long paths' = 'Long paths'; 'System sleep off' = 'No sleep while plugged in'
                   'Display sleep off' = 'No sleep while plugged in'; 'GitHub CLI' = 'GitHub sign-in'; 'NVIDIA driver >= 610' = 'NVIDIA driver'; 'Memory' = 'Memory'
                   'Codex' = 'Codex sign-in' }
        $known = @($items | ForEach-Object { $_.what })
        foreach ($r in $cr.results) {
            if ($r.status -eq 'PASS') { continue }
            if ($same.ContainsKey($r.check) -and $known -contains $same[$r.check]) { continue }
            $st = if ($r.status -eq 'FAIL') { 'TODO' } else { 'INFO' }
            Item $st "check: $($r.check)" $r.detail $r.fix
        }
        Item $(if ($cr.fail -eq 0) { 'PASS' } else { 'TODO' }) 'check.ps1' "$($cr.fail) FAIL, $($cr.warn) WARN (full report: $json)"
    }
}
Write-Host ""
Write-Host "unity-game-factory setup summary (root $Root)"
$todo = @($items | Where-Object status -eq 'TODO')
foreach ($i in $items | Where-Object { $_.status -in 'PASS', 'TODO' }) {
    Write-Host ("  {0}  {1,-36} {2}" -f $i.status, $i.what, $i.detail) -ForegroundColor $(if ($i.status -eq 'PASS') { 'Green' } else { 'Yellow' })
    if ($i.status -eq 'TODO' -and $i.todo) { Write-Host ("        -> {0}" -f $i.todo) -ForegroundColor DarkGray }
}
foreach ($i in $items | Where-Object status -eq 'INFO') { Write-Host ("  note  {0}: {1}{2}" -f $i.what, $i.detail, $(if ($i.todo) { " ($($i.todo))" } else { '' })) -ForegroundColor DarkGray }
Write-Host ""
if ($todo) { Write-Host "$($todo.Count) TODO. Do them, then run setup again: it picks up where it stopped. Log: $setupDir\setup.log" -ForegroundColor Yellow }
else { Write-Host "Ready. Next: the first session (docs/new-machine.md, 'The first session'). Log: $setupDir\setup.log" -ForegroundColor Green }
[IO.File]::WriteAllText((Join-Path $setupDir 'summary.json'), ([ordered]@{ time = (Get-Date).ToString('o'); root = $Root; todo = $todo.Count; items = $items } | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
try { Stop-Transcript | Out-Null } catch { }
exit $todo.Count
