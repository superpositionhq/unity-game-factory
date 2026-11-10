<#
.SYNOPSIS
  Create a new game repo from templates\unity-game (Unity 6.3 LTS): project skeleton (version pin, Visible Meta Files +
  Force Text, the editor tools assembly), Scripts\unity.ps1 (builds, editor steps, tests and plays through the
  heavy-job limiter), first workflow.jsonl row, git + LFS, the post-commit hook (commit recorder), first commit, the
  first editor open (packages, URP, settings; a second commit) when the editor is installed, and the private GitHub
  repo <org>/unity-game-<slug> (not pushed; <org> = -Org, else the config's github_org).
.DESCRIPTION
  Placeholders replaced in file names and contents: __PROJECT__ (C# namespace / assembly prefix / exe name), __SLUG__,
  __TITLE__, __DESCRIPTION__, __UNITY_VERSION__. The editor version is -UnityVersion, else the config's unity_version
  (default 6000.3: the newest installed 6000.3 editor; an exact version pins it); with no such editor installed it
  stops, unless -UnityVersion names one. The first workflow.jsonl row (op project.create) is written at the moment the
  project is created; the first commit names it. Pushing is left to the coordinator's go-ahead (unity-commit-always
  skill).
  -Path is required: the absolute project folder <root>\games\<slug>, written out in the command (the recording hooks
  see the command text, so %UGF_ROOT% or $env:UGF_ROOT would not map the session). That call files this session under
  the game, and the hooks import its earlier calls from the transcript.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File <root>\unity-game-factory\templates\new-game.ps1 -Slug <game> `
      -Path <root>\games\<game> -Title "<Title>" -Description "<one line>" -Reason "<why>"
  (<root> written out, e.g. C:\Users\<you>\UnityWork)
#>
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^(?!.*--)[a-z0-9][a-z0-9-]*[a-z0-9]$', Options = 'None')][string]$Slug,
    # required: the absolute <root>\games\<slug>, written out
    [string]$Path,
    # default from the slug: island-survival -> IslandSurvival
    [string]$Project,
    # default from the slug: Island Survival
    [string]$Title,
    [string]$Description = '',
    # workflow row id prefix; default the slug's initials (is, rr, td) or its first two letters
    [string]$IdPrefix,
    [string]$Reason = 'Create the project from the standard Unity skeleton (Unity 6.3 LTS, visible meta files, text serialization, editor tools, LFS for every binary type)',
    # default: the config's unity_version (the newest installed 6000.3 editor)
    [string]$UnityVersion,
    [string]$Root,
    # default: the config's hooks_dir (machine/lib/ugf-root.ps1 Get-UGFHooksDir)
    [string]$HooksDir,
    # default: the config's github_org (UGF_ORG)
    [string]$Org,
    # skip the first editor open (tests, or no licence yet): run Scripts/unity.ps1 setup later
    [switch]$NoSetup,
    # skip creating the GitHub repo (tests, offline)
    [switch]$NoGitHub
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $repo 'machine\lib\ugf-root.ps1')
if (-not $Root) { $Root = Get-UGFRoot }
if (-not $HooksDir) { $HooksDir = Get-UGFHooksDir }
if (-not $Org) { $Org = Get-UGFOrg }
if (-not $Org -and -not $NoGitHub) { throw 'no GitHub org: set github_org (machine/bootstrap.ps1 -Org <org>), pass -Org, or -NoGitHub' }
# Pre-flight, first: the recording hooks tie this session to the game when a tool call names the project folder as an
# absolute path, so the call must carry -Path <root>\games\<slug> literally (not %UGF_ROOT% / $env:UGF_ROOT, which the
# hook sees unexpanded). The session's earlier calls are then imported from its transcript (machine/README.md).
$want = Join-Path $Root "games\$Slug"
if (-not $Path) { throw "pass -Path $want (the absolute project folder, written out, so the recording hooks file this session under the game)" }
if (-not [IO.Path]::IsPathRooted($Path) -or [IO.Path]::GetFullPath($Path).TrimEnd('\') -ne [IO.Path]::GetFullPath($want).TrimEnd('\')) {
    throw "-Path must be the absolute folder $want (got '$Path')"
}
Write-Host "project folder: $Path (this call maps the session to $Slug for recording)"
$words = $Slug -split '-'
# Invariant: under a Turkish culture 'i'.ToUpper() is a dotted capital I (ice-cave was refused as a project name)
if (-not $Project) { $Project = ($words | ForEach-Object { $_.Substring(0, 1).ToUpperInvariant() + $_.Substring(1) }) -join '' }
if (-not $Title) { $Title = ($words | ForEach-Object { $_.Substring(0, 1).ToUpperInvariant() + $_.Substring(1) }) -join ' ' }
if (-not $IdPrefix) { $IdPrefix = if ($words.Count -ge 2) { ($words | ForEach-Object { $_[0] }) -join '' } else { $Slug.Substring(0, 2) } }
# Case-sensitive (-cnotmatch, Options = 'None' above): PowerShell matches ignore case, and an id like Ba-00001 or
# 3m-00001 fails the row schema for good (rows are never edited).
if ($Project -cnotmatch '^[A-Z][A-Za-z0-9]{1,30}$') { throw "project name '$Project' must be PascalCase letters/digits (pass -Project)" }
if ($IdPrefix -cnotmatch '^[a-z]+$') { throw "workflow row id prefix '$IdPrefix' must be lower-case letters (pass -IdPrefix)" }
# The title lands in C# string literals (ProjectSetup.cs: company and product name) and on the comment line that opens
# Scripts\unity.ps1: keep it plain text. (The description lands only in README.md.)
if ($Title -match '["\\\r\n]') { throw "no quotes, backslashes or line breaks in the title: '$Title'" }

# Names that must never appear inside a game (code, config, commits, builds).
foreach ($v in @($Slug, $Project, $Title, $Description, $Reason)) {
    if ($v -match '(?i)superposition|game[-_ ]?factory|claude|anthropic|openai' -or ($Org -and $v -match ('(?i)' + [regex]::Escape($Org)))) { throw "banned name in '$v' (see the unity-game-session skill)" }
}
if ((Test-Path -LiteralPath $Path) -and @(Get-ChildItem -LiteralPath $Path -Force).Count) { throw "$Path exists and is not empty" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git not found (run machine\bootstrap.ps1 first)' }

# The editor: -UnityVersion, else the config's unity_version (Get-UGFUnityVersion: 6000.3, its newest installed patch,
# unless set to an exact version). ProjectVersion.txt needs an exact version, and a game's first commit must not name
# an editor the PC does not have: without it installed, stop here (-UnityVersion may name one that comes later).
if (-not $UnityVersion) {
    $UnityVersion = Get-UGFUnityVersion
    if (-not $UnityVersion) { throw 'no Unity 6.3 LTS editor is installed: install the newest 6000.3 patch through Unity Hub (Installs > Install Editor, with Windows Build Support (IL2CPP)), or pass -UnityVersion 6000.3.<patch>' }
    if (-not (Get-UGFUnityForVersion $UnityVersion)) { throw "Unity $UnityVersion (unity_version in the config) is not installed: install it through Unity Hub (with Windows Build Support (IL2CPP)), set unity_version to 6000.3 for the newest installed patch, or pass -UnityVersion <version>" }
}
if ($UnityVersion -cnotmatch '^6000\.3\.\d+[abfp]\d+$') { throw "Unity $UnityVersion is not 6.3 LTS (6000.3.x)" }

$template = Join-Path $PSScriptRoot 'unity-game'
$map = [ordered]@{ '__PROJECT__' = $Project; '__SLUG__' = $Slug; '__TITLE__' = $Title; '__DESCRIPTION__' = $Description; '__UNITY_VERSION__' = $UnityVersion }
$utf8 = New-Object Text.UTF8Encoding($false)
function Expand([string]$s) { foreach ($k in $map.Keys) { $s = $s.Replace($k, $map[$k]) }; return $s }

New-Item -ItemType Directory -Force $Path | Out-Null
$Path = (Resolve-Path -LiteralPath $Path).Path
$count = 0
foreach ($f in Get-ChildItem -LiteralPath $template -Recurse -File -Force) {
    $rel = Expand ($f.FullName.Substring($template.Length + 1))
    $dst = Join-Path $Path $rel
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    [IO.File]::WriteAllText($dst, (Expand ([IO.File]::ReadAllText($f.FullName))), $utf8)
    $count++
}

# workflow.jsonl, first row: the operation this script just performed.
$scriptSha = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
# null when this folder is no git work tree (a copy, or one git refuses): under 'Stop' the line git writes to stderr
# would end the script here, with the skeleton half made
$templateCommit = & { $ErrorActionPreference = 'Continue'; & git -C $repo rev-parse --short=12 HEAD 2>$null }
$rowId = '{0}-{1:D5}' -f $IdPrefix, 1
$row = [ordered]@{
    schema = 'unity-workflow/v0'; id = $rowId; seq = 1; time = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffzzz', [Globalization.CultureInfo]::InvariantCulture)
    actor = 'agent'; op = 'project.create'; target = 'ProjectSettings/ProjectVersion.txt'
    params = [ordered]@{ engine = "unity $UnityVersion"; template = 'unity-game'; template_commit = $templateCommit; files = $count; namespace = $Project }
    reason = $Reason; reason_source = 'agent_note'; status = 'observed'
    source = [ordered]@{ script = 'new-game.ps1'; sha256 = $scriptSha; commit = $null }
}
[IO.File]::WriteAllText((Join-Path $Path 'workflow.jsonl'), ($row | ConvertTo-Json -Compress -Depth 6) + "`n", $utf8)

# git + LFS + recorder, then the first commit (the post-commit hook records it).
$old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
& git -C $Path init -q -b main 2>&1 | Out-Null
& git -C $Path lfs install --local 2>&1 | Out-Null
$ErrorActionPreference = $old
& (Join-Path $repo 'machine\install-git-hook.ps1') -Repo $Path -HooksDir $HooksDir | Out-Null

function Commit-All([string]$Message) {
    $ErrorActionPreference = 'Continue'
    & git -C $Path add -A 2>&1 | Out-Null
    $msgFile = Join-Path $env:TEMP "new-game-$PID.txt"
    [IO.File]::WriteAllText($msgFile, $Message, $utf8)
    & git -C $Path commit -q -F $msgFile 2>&1 | Out-Null
    $code = $LASTEXITCODE
    Remove-Item $msgFile -ErrorAction SilentlyContinue
    # what is left (the files, git, no commit) makes a second run refuse the folder as not empty
    if ($code -ne 0) { throw "commit failed (git user.name / user.email set?): set them, delete $Path and run new-game.ps1 again" }
    return (& git -C $Path rev-parse --short HEAD)
}
$sha = Commit-All "Create the $Title project (Unity $UnityVersion skeleton)`n`nVisible meta files and text serialization, the editor tools assembly (workflow log,`nfirst-open setup, player build), root-anchored .gitignore, LFS for every binary type.`n`nworkflow: $rowId"

# The first editor open: packages, URP, TextMeshPro's essential resources, shared settings (Scripts\unity.ps1 setup),
# committed with the files it made.
$setup = 'skipped (-NoSetup): run Scripts/unity.ps1 setup, then commit'
if (-not $NoSetup) {
    $editor = Get-UGFUnity $Path -ErrorAction SilentlyContinue
    if ($editor -and (Test-Path -LiteralPath $editor)) {
        Write-Host "first editor open with Unity $UnityVersion (packages, URP, settings; a few minutes)"
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Path 'Scripts\unity.ps1') setup
        if ($LASTEXITCODE -eq 0) {
            $rows = @(Get-Content -LiteralPath (Join-Path $Path 'workflow.jsonl') | Where-Object { $_.Trim() } | ForEach-Object { ($_ | ConvertFrom-Json).id })
            $span = if ($rows.Count -gt 1) { "$($rows[1])..$($rows[-1])" } else { $rowId }
            $setup = "done, commit $(Commit-All "Set up packages, URP and the shared player settings`n`nFirst editor open: URP, Input System, Cinemachine, uGUI, NavMesh, Timeline and`nTest Framework added by name, the URP asset made the default pipeline,`nTextMeshPro's essential resources imported, Linear colour, Input System only,`nrun in background. Generated .meta files and project settings committed.`n`nworkflow: $span")"
        } else {
            $setup = "FAILED (exit $LASTEXITCODE): read Logs/unity-ps1/setup_*.log, fix (licence? editor? network?), run Scripts/unity.ps1 setup again, then commit"
        }
    } else {
        $setup = "not run: Unity $UnityVersion is not installed (install it through Unity Hub with Windows Build Support (IL2CPP)), then run Scripts/unity.ps1 setup and commit"
    }
}

$remote = $null
if (-not $NoGitHub) {
    $full = "$Org/unity-game-$Slug"
    $ErrorActionPreference = 'Continue'
    & gh repo view $full --json name 2>&1 | Out-Null
    $exists = ($LASTEXITCODE -eq 0)
    if ($exists) {
        # never linked unseen: it may be another game's (same slug) or public, and a push would ship store content there
        Write-Warning "$full already exists: not linked. Check that it is this game's and private, then: git remote add origin https://github.com/$full.git"
    } else {
        & gh repo create $full --private --description $Title 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
            & git -C $Path remote add origin "https://github.com/$full.git"
            $remote = "https://github.com/$full (private; not pushed: push when the coordinator says)"
        } else { Write-Warning "could not create $full; create it later: gh repo create $full --private" }
    }
    $ErrorActionPreference = $old
}

Write-Host "created $Title ($Project, Unity $UnityVersion) at $Path"
Write-Host "  files: $count, first row $rowId, commit $sha"
Write-Host "  first open: $setup"
Write-Host "  remote: $(if ($remote) { $remote } else { 'none' })"
Write-Host "  next: write the design doc, build through Scripts/unity.ps1, log every operation in workflow.jsonl"
