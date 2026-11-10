<#
.SYNOPSIS
  Add the commit recorder to a game repo's post-commit hook (idempotent).
.DESCRIPTION
  Appends one line to <repo>\.git\hooks\post-commit that runs <hooks dir>\record-unity-commit.ps1, which writes every new
  commit to <root>\.recording\<repo name>\commits.jsonl. Git LFS's own post-commit lines stay first: when the hook does
  not exist yet, `git lfs update` creates it before the line is appended. A repo whose hook already calls
  record-unity-commit.ps1 is left alone (pass -Force to rewrite the line, e.g. after moving the hooks dir). record-unity-commit.ps1
  exits at once when the committing checkout is on the orphan `tasks` branch (the game's tasks, unity-write-tasks
  skill): a commit there, e.g. from a tasks worktree, is not recorded.
  Not ported yet: the Unreal factory's per-commit live creation replay line. The Unity creation replay comes with the
  verifier; this script will add its post-commit line then (and -Force will rewrite older hooks).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File machine\install-git-hook.ps1 %UGF_ROOT%\games\stealth
#>
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [string]$HooksDir,   # where bootstrap.ps1 installed record-unity-commit.ps1; default the config's hooks_dir (Get-UGFHooksDir)
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
$line = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$script`" `"`$(pwd -W 2>/dev/null || pwd)`" >/dev/null 2>&1 || true"
$marker = '# recording: append this commit to <root>/.recording/<repo>/commits.jsonl (machine/install-git-hook.ps1)'

$text = if (Test-Path -LiteralPath $hookPath) { [IO.File]::ReadAllText($hookPath) } else { "#!/bin/sh`n" }
$text = $text -replace "`r`n", "`n"
$hasRec = $text -match 'record-unity-commit\.ps1'
if ($hasRec -and -not $Force) { Write-Host "post-commit already records commits: $hookPath"; return }
if ($Force) {
    # drop the old recorder line (and its comment), keep everything else
    $text = (($text -split "`n") | Where-Object { $_ -notmatch 'record-unity-commit\.ps1' -and $_ -notmatch '^# .*recording' }) -join "`n"
}
if (-not $text.EndsWith("`n")) { $text += "`n" }
$text += "$marker`n$line`n"
[IO.File]::WriteAllText($hookPath, $text, (New-Object Text.UTF8Encoding($false)))
Write-Host "post-commit records commits via $script : $hookPath"
