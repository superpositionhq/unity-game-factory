<#
.SYNOPSIS
  post-commit hook of a game: show the creation replay's last findings once, start the per-commit replay job.
.DESCRIPTION
  Installed by machine/install-git-hook.ps1 (bootstrap.ps1 runs it for every game repo under <root>\games). Does
  nothing when the repo's ReplayConfig.json has "live": false (a game without a ReplayConfig.json replays with the
  defaults), and nothing for a commit on the orphan `tasks` branch (the game's tasks are not part of the replayed
  history). Returns at once: the job (`unity_replay.py live --game <repo>`, docs/unity-replay.md, "Live replay") runs
  detached at below-normal priority, takes editor slots only through unity-heavy.ps1 -Low, and catches up with every
  commit made while it runs. Its findings land in <work_root>\work\live\feedback.md; this hook prints them at the next
  commit. Python: $env:UGF_PYTHON, else python on PATH, else the py launcher.
.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File <tool checkout>\tools\unity-replay\live-hook.ps1 <root>\games\<slug>
#>
param([Parameter(Mandatory = $true)][string]$Repo)
$ErrorActionPreference = 'Stop'
try {
    if ($env:UGF_NO_RECORDING -or $env:GF_NO_RECORDING) { exit 0 }   # a task try's agent: not a game session
    # Only a game of this machine's root: the repo must be exactly <root>\games\<slug> for the root this shell resolves
    # (UGF_ROOT, else the machine config). Any other repo with this hook line (a scratch or test copy of a game, a task
    # check's copy, a clone in builds\, a game of another root) gets nothing, silently: no folder made, no job started.
    $checkout = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent      # the tool checkout
    . (Join-Path $checkout 'machine\lib\ugf-root.ps1')
    $root = Get-UGFRoot
    $Repo = [IO.Path]::GetFullPath($Repo).TrimEnd('\')
    $slug = Split-Path -Leaf $Repo
    if (-not $slug -or $Repo -ne [IO.Path]::GetFullPath((Join-Path $root "games\$slug")).TrimEnd('\')) { exit 0 }
    if (-not (Test-Path -LiteralPath (Join-Path $Repo '.git'))) { exit 0 }
    if ((git -C $Repo symbolic-ref --short -q HEAD) -eq 'tasks') { exit 0 }   # the tasks branch is not game history
    $cfgPath = Join-Path $Repo 'ReplayConfig.json'
    $cfg = $null
    if (Test-Path -LiteralPath $cfgPath) {
        $cfg = [IO.File]::ReadAllText($cfgPath) | ConvertFrom-Json
        if ($cfg.PSObject.Properties['live'] -and -not $cfg.live) { exit 0 }
    }
    $workRoot = if ($cfg -and $cfg.PSObject.Properties['work_root'] -and $cfg.work_root) { [string]$cfg.work_root } else { "{root}/unity-replay/$slug" }
    $workRoot = $workRoot.Replace('{root}', $root).Replace('/', '\')
    $live = Join-Path $workRoot 'work\live'
    New-Item -ItemType Directory -Force $live | Out-Null

    # 1. the last finished job's findings, once
    $fb = Join-Path $live 'feedback.md'
    $shown = Join-Path $live 'feedback.shown'
    if ((Test-Path -LiteralPath $fb) -and (-not (Test-Path -LiteralPath $shown) -or
            (Get-Item -LiteralPath $fb).LastWriteTime -gt (Get-Item -LiteralPath $shown).LastWriteTime)) {
        $lines = @(Get-Content -LiteralPath $fb -Encoding UTF8)
        Write-Host ("[replay] " + ($lines[0] -replace '^#\s*', ''))
        $lines | Select-Object -Skip 1 | Where-Object { $_ -match '^- ' } | Select-Object -First 12 | ForEach-Object { Write-Host "  $_" }
        Write-Host "  (all of it: $fb)"
        Set-Content -LiteralPath $shown -Value (Get-Date -Format o) -Encoding ASCII
    }

    # 2. start the job unless one runs (it takes the new commit before it exits)
    $lock = Join-Path $live 'lock'
    if (Test-Path -LiteralPath $lock) {
        try { $owner = [int](([IO.File]::ReadAllText($lock) | ConvertFrom-Json).pid) } catch { $owner = 0 }
        if ($owner -and (Get-Process -Id $owner -ErrorAction SilentlyContinue)) { exit 0 }
    }
    $py = $env:UGF_PYTHON
    if (-not $py) { $c = Get-Command python -ErrorAction SilentlyContinue; if ($c) { $py = $c.Source } }
    $pyArgs = @()
    if (-not $py) { $c = Get-Command py -ErrorAction SilentlyContinue; if ($c) { $py = $c.Source; $pyArgs = @('-3') } }
    if (-not $py) { Write-Host '[replay] no Python found (set UGF_PYTHON): live replay not started'; exit 0 }
    $script = Join-Path $PSScriptRoot 'unity_replay.py'
    $log = Join-Path $live 'job.log'
    $argLine = (($pyArgs + @('-I', '-B', "`"$script`"", 'live', '--game', "`"$Repo`"", '--log', "`"$log`"")) -join ' ')
    $p = Start-Process -FilePath $py -ArgumentList $argLine -WindowStyle Hidden -PassThru
    try { $p.PriorityClass = [Diagnostics.ProcessPriorityClass]::BelowNormal } catch { }
} catch {
    Write-Host "[replay] live hook: $($_.Exception.Message)"
}
exit 0
