<#
.SYNOPSIS
  Add the commit recorder and the live creation replay to a game repo's post-commit hook (idempotent).
.DESCRIPTION
  Appends two lines to <repo>\.git\hooks\post-commit. The first runs <hooks dir>\record-unity-commit.ps1, which writes
  every new commit to <root>\.recording\<repo name>\commits.jsonl; it is silent (a recorder that fails must never print
  into a commit's output). The second runs this checkout's tools\unity-replay\live-hook.ps1, which prints the creation
  replay's last findings once and starts the replay of the new commits in the background (docs/unity-replay.md, "Live
  replay"); it does nothing for a repo whose ReplayConfig.json has "live": false. Its output (the replay's findings for
  the game session) is meant to be seen, so it is not silenced.
  Git LFS's own post-commit lines stay first: when the hook does not exist yet, `git lfs update` creates it before the
  lines are appended. A repo whose hook already runs this hooks dir's record-unity-commit.ps1 and this checkout's
  live-hook.ps1 is left alone; a line that names another hooks dir or another checkout (moved since) is replaced, and
  when another tool's hook ends in `exit` or `exec` the lines go before that (after it, they never ran); an `exit` or
  `exec` higher up, which the lines cannot be put before, gets a warning. -Force rewrites the lines in any case.
  machine\bootstrap.ps1 runs this for every game repo under <root>\games, so after a pull of this repo and a bootstrap
  every game has the current lines; a game repo elsewhere needs this run once.
  Both scripts exit at once when the committing checkout is on the orphan `tasks` branch (the game's tasks,
  docs/game-format.md): a commit there, e.g. from a tasks worktree, is neither recorded nor replayed.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File machine\install-git-hook.ps1 %UGF_ROOT%\games\stealth
#>
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    # where bootstrap.ps1 installed record-unity-commit.ps1; default the config's hooks_dir (Get-UGFHooksDir)
    [string]$HooksDir,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
if (-not $HooksDir) { . (Join-Path $PSScriptRoot 'lib\ugf-root.ps1'); $HooksDir = Get-UGFHooksDir }
$Repo = (Resolve-Path -LiteralPath $Repo).Path
if (-not (Test-Path -LiteralPath (Join-Path $Repo '.git'))) { throw "not a git repo (no .git): $Repo" }
$hookPath = (& git -C $Repo rev-parse --git-path hooks/post-commit)
if (-not [IO.Path]::IsPathRooted($hookPath)) { $hookPath = Join-Path $Repo $hookPath }
$hookPath = [IO.Path]::GetFullPath($hookPath)
New-Item -ItemType Directory -Force (Split-Path $hookPath) | Out-Null

$usesLfs = (Test-Path -LiteralPath (Join-Path $Repo '.gitattributes')) -and
    ((Get-Content -LiteralPath (Join-Path $Repo '.gitattributes') -Raw) -match 'filter=lfs')
if (-not (Test-Path -LiteralPath $hookPath) -and $usesLfs) {
    # git-lfs refuses to replace another tool's hook ("Hook already exists: pre-push") on stderr, which under 'Stop'
    # ended this script before the recorder went in
    $ErrorActionPreference = 'Continue'
    & git -C $Repo lfs update 2>&1 | Out-Null   # writes LFS's pre-push / post-checkout / post-commit / post-merge hooks
    $ErrorActionPreference = 'Stop'
}

$script = ($HooksDir -replace '\\', '/').TrimEnd('/') + '/record-unity-commit.ps1'
# The hook line is silent (a recorder that fails must never print into a commit's output), so a recorder that isn't
# there is said here: otherwise the repo's commits go unrecorded without a word.
if (-not (Test-Path -LiteralPath $script)) { Write-Warning "$script is not there (machine\bootstrap.ps1 installs it): this repo's commits are not recorded until it is" }
$line = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`" `"`$(pwd -W 2>/dev/null || pwd)`" >/dev/null 2>&1 || true"
$marker = '# recording: append this commit to <root>/.recording/<repo>/commits.jsonl (machine/install-git-hook.ps1)'

# The live creation replay (tools/unity-replay/live-hook.ps1 of this checkout): its output is the replay's findings for
# the game session, so it is not silenced.
$liveHook = ((Split-Path $PSScriptRoot -Parent) -replace '\\', '/') + '/tools/unity-replay/live-hook.ps1'
if (-not (Test-Path -LiteralPath $liveHook)) { Write-Warning "$liveHook is not there: this repo's commits are not replayed until it is" }
$liveLine = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$liveHook`" `"`$(pwd -W 2>/dev/null || pwd)`" || true"
$liveMarker = '# live replay: replay the new commits in the background, print the last findings (machine/install-git-hook.ps1)'

$text = if (Test-Path -LiteralPath $hookPath) { [IO.File]::ReadAllText($hookPath) } else { "#!/bin/sh`n" }
$text = $text -replace "`r`n", "`n"
# drop older recorder and live-replay lines (one naming a hooks dir or a checkout moved since: its commits went
# unrecorded or unreplayed) and their comments, keep everything else
$new = (($text -split "`n") | Where-Object { $_ -notmatch 'record-unity-commit\.ps1|unity-replay[\\/]live-hook\.ps1' -and $_ -ne $marker -and $_ -ne $liveMarker }) -join "`n"
if (-not $new.EndsWith("`n")) { $new += "`n" }
$block = "$marker`n$line`n$liveMarker`n$liveLine`n"
# another tool's hook that ends in `exit` or `exec` (blank lines after it too): the lines go before it, or never run
$end = [regex]::Match($new, '(?m)^[ \t]*(exit|exec)\b[^\n]*\n\s*\z')
$new = if ($end.Success) { $new.Substring(0, $end.Index) + $block + $end.Value } else { $new + $block }
# one higher up (inside an if) cannot be moved past, and the recorder's line is silent: say so on every run
if ($new.Substring(0, $new.IndexOf($line)) -match '(?m)^[ \t]*(exit|exec)\b') {
    Write-Warning "$hookPath can end before the recorder's and the live replay's lines (an exit or exec above them): move the lines above that, or this repo's commits are neither recorded nor replayed"
}
# already in place (lines an older copy of this script left after such an exit are moved)
if ($new -ceq $text -and -not $Force) { Write-Host "post-commit already records commits and starts the live replay: $hookPath"; return }
[IO.File]::WriteAllText($hookPath, $new, (New-Object Text.UTF8Encoding($false)))
Write-Host "post-commit records commits via $script and starts the live replay via $liveHook : $hookPath"
