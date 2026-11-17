<#
.SYNOPSIS
  Build one game's Windows release player at a commit. See docs/unity-pipeline.md.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File build.ps1 harbor-run
  powershell -ExecutionPolicy Bypass -File build.ps1 harbor-run -Commit milestone/autoplay-1 -Backend mono

  Builds from a private clone (C:\UGB\src\<game>: outside the user profile, so no user name is compiled into the
  player) of the committed tree, never from the game's working copy: the game session's editor keeps its project lock
  and half-edited files to itself. Uncommitted changes are not built. The player is the game's own release build
  (Assets/Editor/Tools/BuildPlayer.cs, as Scripts/unity.ps1 build runs it), run through the machine's job limiter.
  Output: builds\<game>\<short-sha>\Windows\<Project>.exe, build_info.json, logs\. One row per run in
  .recording\<game>\builds.jsonl. Holds the game's pipeline lock (one build or recording of a game at a time).

  A mobile game (the commit has a Platform.json) gets the same Windows player, which is what is played and recorded
  on this PC at the phone's size, and its Android APK (arm64, IL2CPP, release) in Android\<Project>.apk, built by the
  game's Assets/Editor/Tools/BuildAndroid.cs and read back with the SDK's aapt2. The APK step needs the editor's
  Android Build Support with its OpenJDK and Android SDK & NDK tools (machine\check.ps1 says whether the machine has
  them, docs\new-machine.md how to install them); without them the step is skipped, build_info.json says so
  (apk.status "skipped") and the build is still ok: the game can be played and recorded from it, but not released
  (a mobile game's dataset needs its APK, and the packager refuses a build without one).
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [string]$Commit = 'HEAD',
    [ValidateSet('', 'il2cpp', 'mono')][string]$Backend = '',   # '': what BuildPlayer gives a release build (IL2CPP)
    [switch]$Force
)

. (Join-Path $PSScriptRoot 'common.ps1')

$info = Get-GameInfo $Game
$commandLine = "build.ps1 $Game -Commit $Commit" + $(if ($Backend) { " -Backend $Backend" } else { '' }) + $(if ($Force) { ' -Force' } else { '' })

$sha = (Invoke-Git $info.Dir @('rev-parse', '--verify', "$Commit^{commit}")).Trim()
$short = $sha.Substring(0, 8)
$outDir = Join-Path (Join-Path $BuildsRoot $Game) $short
$logDir = Join-Path $outDir 'logs'
$winDir = Join-Path $outDir 'Windows'
$buildInfoPath = Join-Path $outDir 'build_info.json'

$existing = Read-JsonFile $buildInfoPath
if (-not $Force -and $existing -and $existing.status -eq 'ok' -and (Test-Path -LiteralPath "$($existing.exe_path)") -and
    (-not $Backend -or (Get-Prop $existing 'backend') -eq $Backend)) {
    Write-Step "$Game $short already built ($outDir); use -Force to rebuild"
    return $existing
}

Set-BelowNormalPriority
# The editor, IL2CPP's compiler and the linker write temp files under %TEMP% and the linker records such paths: keep
# them outside the user profile too.
New-Item -ItemType Directory -Force $BuildTempRoot | Out-Null
$savedTemp = $env:TEMP; $savedTmp = $env:TMP
$env:TEMP = $BuildTempRoot; $env:TMP = $BuildTempRoot
Enter-PipelineLock "build $Game $short" -Game $Game
$start = Get-Date
$steps = New-Object System.Collections.ArrayList
$failure = ''
$autoplayVersion = $null
$leakScan = $null
$unityVersion = ''
$unity = $null
$projectName = $info.ProjectName
$builtBackend = $null
$playerBytes = $null
$platform = $null
$apk = $null
$apkDir = Join-Path $outDir 'Android'
$status = 'ok'
$stamp = $start.ToString('yyyyMMdd-HHmmss')

# One Unity run through the limiter; its own log is the step's log.
function Invoke-Step([string]$Name, [string[]]$UnityArgs) {
    $log = Join-Path $logDir "$stamp-$Name.log"
    Write-Step "$Name ..."
    $t0 = Get-Date
    $command = @($unity, '-batchmode', '-nographics', '-quit', '-logFile', $log) + $UnityArgs
    $code = Invoke-Heavy "pipeline $Game $short $Name" $command
    $t1 = Get-Date
    $row = [ordered]@{
        name = $Name; command = (Format-CommandLine $command); start = $t0.ToString('o'); end = $t1.ToString('o')
        duration_s = [math]::Round(($t1 - $t0).TotalSeconds, 1); exit_code = $code; log_path = $log
        error_excerpt = $(if ($code -ne 0) { Get-ErrorExcerpt $log } else { '' })
    }
    [void]$steps.Add($row)
    Write-Step ("{0} exit {1} in {2}s" -f $Name, $code, $row.duration_s)
    return $row
}

try {
    # a rebuild never leaves an older build_info.json that says ok next to a player that is gone
    Remove-Item -LiteralPath $buildInfoPath -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $logDir | Out-Null

    # ---- source: private clone at the exact commit, LFS files copied from the game's own LFS store ----
    $src = Join-Path $SrcRoot $Game
    $env:GIT_LFS_SKIP_SMUDGE = '1'
    if (-not (Test-Path (Join-Path $src '.git'))) {
        Write-Step "cloning $($info.Dir) -> $src"
        New-Item -ItemType Directory -Force (Split-Path $src) | Out-Null
        # --local hard-links the object files, which fails across volumes ("Improper link"): a game folder that is a
        # junction to another drive is cloned with copies instead.
        # Both sides may be junctions (the game folder, or a clone folder pre-made as a junction to another drive).
        function Get-RealDrive([string]$Path) { $i = Get-Item $Path -Force -ErrorAction SilentlyContinue; if ($i -and $i.LinkType -and $i.Target) { ([string]@($i.Target)[0]).Substring(0, 1) } else { $Path.Substring(0, 1) } }
        $repoDrive = Get-RealDrive $info.Dir
        $cloneArgs = @('clone', '--quiet', '--no-checkout', '--local')
        if ($repoDrive -ne (Get-RealDrive $src)) { $cloneArgs += '--no-hardlinks' }
        Invoke-Git $WorkRoot ($cloneArgs + @($info.Dir, $src)) | Out-Null
    }
    Invoke-Git $src @('fetch', '--quiet', '--force', '--tags', 'origin', '+refs/heads/*:refs/remotes/origin/*') | Out-Null
    Invoke-Git $src @('-c', 'advice.detachedHead=false', 'checkout', '--quiet', '--force', $sha) | Out-Null
    # Library\ (the import cache) stays, so later builds import only what changed: kept by name, whatever the game's
    # .gitignore at this commit says.
    Invoke-Git $src @('clean', '-ffdq', '-e', '/[Ll]ibrary/') | Out-Null
    $lfsStore = Get-LfsStore $info.Dir
    $missing = New-Object System.Collections.ArrayList
    $copied = 0
    $lfsList = @(Invoke-Git $src @('-c', 'core.quotepath=false', 'lfs', 'ls-files', '-l') -AllowFail)
    foreach ($line in $lfsList) {
        if ($line.Length -lt 68) { continue }
        $oid = $line.Substring(0, 64); $rel = $line.Substring(67)
        $target = Join-Path $src $rel
        $item = Get-Item -LiteralPath $target -ErrorAction SilentlyContinue
        if ($item -and $item.Length -lt 1024 -and ((Get-Content -LiteralPath $target -TotalCount 1) -like 'version https://git-lfs*')) {
            $obj = Join-Path $lfsStore ("{0}\{1}\{2}" -f $oid.Substring(0, 2), $oid.Substring(2, 2), $oid)
            # a copy, never a hard link: an import that rewrote the file in the clone would change the game's object
            if (Test-Path -LiteralPath $obj) { Copy-Item -LiteralPath $obj -Destination $target -Force; $copied++ }
            else { [void]$missing.Add($rel) }
        }
    }
    Remove-Item Env:\GIT_LFS_SKIP_SMUDGE
    if ($missing.Count -gt 0) { throw "LFS objects missing from $lfsStore for: $($missing -join ', ') (git -C `"$($info.Dir)`" lfs fetch origin $sha)" }
    Write-Step "source at $short in $src ($($lfsList.Count) LFS files, $copied copied)"
    # What the game is made for at this commit: a desktop game, or an Android phone game (its Platform.json).
    $platform = Get-GamePlatform $src
    if ($platform.platform -eq 'mobile') { Write-Step "a mobile game, held in $($platform.orientation): played and recorded as its Windows player at $($platform.width)x$($platform.height); its APK is built too" }

    # The player build as the commit has it: its BuildPlayer.cs names the method and the exe.
    $bp = Get-PlayerBuildInfo $src
    $projectName = $bp.ProjectName
    # Which AutoPlay drop-in the game ships (null: none; record.ps1 refuses such a build).
    $autoplayVersion = Get-AutoPlayVersion $src
    # The game's own editor (its ProjectVersion.txt): a game keeps building on the editor it was made with.
    $unityVersion = Get-ProjectUnityVersion $src
    $unity = Get-UGFUnity $src $UGFConfig -WarningAction SilentlyContinue
    if (-not $unity) { throw "Unity $unityVersion (ProjectSettings\ProjectVersion.txt at $short) is not installed: install it through Unity Hub, with Windows Build Support (IL2CPP)" }
    Write-Step "Unity $unityVersion at $unity; player $($bp.Method) -> $projectName.exe; AutoPlay drop-in $(if ($null -ne $autoplayVersion) { "v$autoplayVersion" } else { 'none' })"

    # ---- the release player (a fresh folder: Unity refuses to build IL2CPP over a Mono build in one folder) ----
    if (Test-Path -LiteralPath $winDir) { Remove-Item -LiteralPath $winDir -Recurse -Force }
    $playerArgs = @('-projectPath', $src, '-executeMethod', $bp.Method, '-buildOut', $winDir)
    # a mobile game's clone was last opened for its APK: the editor starts on the Windows target for this build
    if ($platform.platform -eq 'mobile') { $playerArgs = @('-buildTarget', 'Win64') + $playerArgs }
    if ($Backend) { $playerArgs += @('-backend', $Backend) }
    $r = Invoke-Step 'player' $playerArgs
    # An editor that stopped with no word about the game (no compiler error, no failed build row; an IL post-processor
    # exited 1 without a message once, and the same commit built on a rerun) is tried once more. The first attempt
    # stays in steps[] marked retried. A missing licence (exit 198) is the person's to fix: never retried.
    $log = [string]$r.log_path
    $said = (Test-Path -LiteralPath $log) -and (Select-String -LiteralPath $log -Pattern 'error CS\d+|\[workflow\] .*build\.player.*\(failed|No valid Unity Editor license' -Quiet)
    if ($r.exit_code -ne 0 -and $r.exit_code -ne 198 -and -not $said) {
        $r['retried'] = $true
        Write-Step 'player: the editor stopped with no compiler error and no failed build row; trying once more'
        if (Test-Path -LiteralPath $winDir) { Remove-Item -LiteralPath $winDir -Recurse -Force }
        $r = Invoke-Step 'player-retry' $playerArgs
    }
    if ($r.exit_code -ne 0) {
        $failure = if ($r.exit_code -eq 198) { 'Unity has no active licence (exit 198): sign in to Unity Hub and activate one' } else { 'player build failed' }
        throw $failure
    }
    $exePath = Join-Path $winDir "$projectName.exe"
    if (-not (Test-Path -LiteralPath $exePath)) { throw "the build succeeded but $exePath is missing" }
    # What BuildPlayer did, from the row it wrote to the clone's workflow.jsonl (the next checkout drops it).
    $wf = Join-Path $src 'workflow.jsonl'
    $playerRow = $null
    if (Test-Path -LiteralPath $wf) {
        $lastLine = @([IO.File]::ReadAllLines($wf) | Where-Object { $_ -match '"op"\s*:\s*"build\.player"' } | Select-Object -Last 1)
        if ($lastLine) { try { $playerRow = $lastLine[0] | ConvertFrom-Json } catch { } }
    }
    $p = Get-Prop $playerRow 'params'
    if ($p) { $builtBackend = Get-Prop $p 'backend'; $playerBytes = Get-Prop $p 'bytes' }

    # Strings that must not ship: the user name (compiled-in source and debug-symbol paths) and $ForbiddenNamePatterns
    # (common.ps1). Recorded and warned about; recording still works, but such a build must not be handed out.
    $leakHits = @(Find-LeakedStrings $winDir @($UserNamePatterns + $ForbiddenNamePatterns))
    $leakScan = [ordered]@{ scanned = 'Windows\'; hits = @($leakHits | ForEach-Object { [ordered]@{ file = $_.file; pattern = $_.pattern; count = $_.count; example = $_.example } }) }
    if ($leakHits.Count) { Write-Step "WARNING: the player's files contain names that must not ship: $(($leakHits | ForEach-Object { "$($_.file) ($($_.pattern) x$($_.count))" }) -join '; ')" }
    else { Write-Step 'leak scan: no user name or forbidden names in the player''s files' }

    # ---- a mobile game's Android APK (arm64, IL2CPP, release), when this machine can build one ----
    if ($platform.platform -eq 'mobile') {
        if (Test-Path -LiteralPath $apkDir) { Remove-Item -LiteralPath $apkDir -Recurse -Force }
        $tool = Get-UGFAndroidToolchain $unity
        if (-not (Test-Path -LiteralPath (Join-Path $src 'Assets\Editor\Tools\BuildAndroid.cs'))) {
            throw 'a mobile game (Platform.json) without Assets\Editor\Tools\BuildAndroid.cs: the APK build of the mobile template is missing at this commit'
        }
        if (-not $tool.Ok) {
            $apk = [ordered]@{ status = 'skipped'; reason = $tool.Why }
            Write-Step "APK: skipped, $($tool.Why). The Windows player is built and can be recorded. This build cannot be released: a mobile game's dataset needs its APK, so build the release commit again on a machine with the Android toolchain"
        } else {
            $ns = $bp.Method -replace '\.BuildPlayer\.BuildWindows$', ''
            $apkArgs = @('-buildTarget', 'Android', '-projectPath', $src, '-executeMethod', "$ns.BuildAndroid.Build", '-buildOut', $apkDir)
            if ($tool.Sdk) {   # an SDK and NDK installed apart from Unity: the build is told where they are
                $apkArgs += @('-androidSdk', $tool.Sdk, '-androidNdk', $tool.Ndk)
                Write-Step "APK: built with the Android SDK at $($tool.Sdk) and the NDK at $($tool.Ndk) (the editor has none of its own)"
            }
            $r = Invoke-Step 'apk' $apkArgs
            if ($r.exit_code -ne 0) { $failure = 'APK build failed'; throw $failure }
            $apkPath = Join-Path $apkDir "$projectName.apk"
            if (-not (Test-Path -LiteralPath $apkPath)) { throw "the APK build succeeded but $apkPath is missing" }
            $said = if ($tool.Aapt2) { Read-ApkBadging $tool.Aapt2 $apkPath } else { $null }
            if (-not $said) { throw "the APK cannot be read back (aapt2 dump badging $apkPath)" }
            # what the APK itself says must be a phone game's: arm64 alone, the SDK levels, a package name of its own
            $wrong = @()
            if (($said.abis -join ',') -ne 'arm64-v8a') { $wrong += "ABIs '$($said.abis -join ', ')' (arm64-v8a alone)" }
            if ($null -eq $said.min_sdk -or $said.min_sdk -lt 26) { $wrong += "minSdk $($said.min_sdk) (at least 26)" }
            if ($null -eq $said.target_sdk -or $said.target_sdk -lt 34) { $wrong += "targetSdk $($said.target_sdk) (at least 34)" }
            if ($said.package -notmatch '^com\.[a-z][a-z0-9]*\.game$') { $wrong += "package '$($said.package)' (com.<project>.game)" }
            if ($wrong.Count) { throw "the APK is not what a mobile game ships: $($wrong -join '; ')" }
            # the APK is a zip: its files are scanned unpacked, as the Windows player's are, then the copy is removed
            $unpacked = Join-Path $outDir '_apk'
            if (Test-Path -LiteralPath $unpacked) { Remove-Item -LiteralPath $unpacked -Recurse -Force }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            # entry by entry: an APK holds names that differ only by case (res\9n.9.png, res\9N.9.png), which one
            # Windows folder cannot hold; the second of such a pair gets "~<n>" before its extension
            $zip = [IO.Compression.ZipFile]::OpenRead($apkPath)
            try {
                $taken = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
                $n = 0
                foreach ($entry in $zip.Entries) {
                    if (-not $entry.Name) { continue }   # a folder's own entry
                    $rel = $entry.FullName -replace '/', '\'
                    if ($rel -match '(^|\\)\.\.(\\|$)' -or [IO.Path]::IsPathRooted($rel)) { continue }
                    if (-not $taken.Add($rel)) { $n++; $rel = [IO.Path]::ChangeExtension($rel, $null).TrimEnd('.') + "~$n" + [IO.Path]::GetExtension($rel); [void]$taken.Add($rel) }
                    $to = Join-Path $unpacked $rel
                    New-Item -ItemType Directory -Force (Split-Path $to -Parent) | Out-Null
                    [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $to, $true)
                }
            } finally { $zip.Dispose() }
            $apkHits = @(Find-LeakedStrings $unpacked @($UserNamePatterns + $ForbiddenNamePatterns))
            Remove-Item -LiteralPath $unpacked -Recurse -Force
            $leakScan.scanned = 'Windows\, Android\'
            $leakScan.hits = @($leakScan.hits) + @($apkHits | ForEach-Object { [ordered]@{ file = "Android\$projectName.apk!$($_.file)"; pattern = $_.pattern; count = $_.count; example = $_.example } })
            if ($apkHits.Count) { Write-Step "WARNING: the APK's files contain names that must not ship: $(($apkHits | ForEach-Object { "$($_.file) ($($_.pattern) x$($_.count))" }) -join '; ')" }
            $apk = [ordered]@{ status = 'ok'; file = "Android\$projectName.apk"; bytes = (Get-Item -LiteralPath $apkPath).Length; sha256 = (Get-FileSha256 $apkPath)
                package = $said.package; version_code = $said.version_code; version_name = $said.version_name; min_sdk = $said.min_sdk; target_sdk = $said.target_sdk; abi = 'arm64-v8a' }
            Write-Step "APK: $($apk.file), $([math]::Round($apk.bytes / 1MB, 1)) MB, $($said.package) $($said.version_name) ($($said.version_code)), minSdk $($said.min_sdk), targetSdk $($said.target_sdk), arm64-v8a"
        }
    }
} catch {
    $status = 'failed'
    $failure = $_.Exception.Message
    Write-Step "FAILED: $failure"
} finally {
    Remove-Item Env:\GIT_LFS_SKIP_SMUDGE -ErrorAction SilentlyContinue
    $env:TEMP = $savedTemp; $env:TMP = $savedTmp
    Exit-PipelineLock
}

$end = Get-Date
$failedStep = $steps | Where-Object { $_.exit_code -ne 0 -and -not $_.Contains('retried') } | Select-Object -First 1
$lastStep = $steps | Select-Object -Last 1
$subject = "$(Invoke-Git $info.Dir @('log', '-1', '--format=%s', $sha) -AllowFail)"
$commitTime = "$(Invoke-Git $info.Dir @('log', '-1', '--format=%cI', $sha) -AllowFail)"
$row = [ordered]@{
    schema = 'unity-build/1'   # neutral: build_info.json sits next to the game's player
    game = $Game; project = $projectName
    commit = $sha; short_sha = $short; requested = $Commit; commit_subject = $subject; commit_time = $commitTime
    command = $commandLine
    start = $start.ToString('o'); end = $end.ToString('o'); duration_s = [math]::Round(($end - $start).TotalSeconds, 1)
    status = $status
    exit_code = $(if ($failedStep) { $failedStep.exit_code } elseif ($status -eq 'ok') { 0 } else { -1 })
    error_excerpt = $(if ($failedStep) { $failedStep.error_excerpt } elseif ($status -ne 'ok') { $failure } else { '' })
    log_path = $(if ($failedStep) { $failedStep.log_path } elseif ($lastStep) { $lastStep.log_path } else { $null })
    output_path = $(if ($status -eq 'ok') { $outDir } else { $null })
    exe_path = $(if ($status -eq 'ok') { Join-Path $winDir "$projectName.exe" } else { $null })
    config = 'release'
    backend = $(if ($builtBackend) { $builtBackend } elseif ($Backend) { $Backend } else { 'il2cpp' })
    player_bytes = $playerBytes
    autoplay_version = $autoplayVersion
    leak_scan = $leakScan
    unity_version = $unityVersion
    editor = $unity
    steps = @($steps)
}
# a mobile game's build says what it is and what became of its APK; a desktop game's row is as it always was
if ($platform -and $platform.platform -eq 'mobile') {
    $row['platform'] = 'mobile'; $row['orientation'] = $platform.orientation; $row['window'] = @($platform.width, $platform.height); $row['apk'] = $apk
}
Add-JsonLine (Join-Path $info.LogDir 'builds.jsonl') $row
if ($status -eq 'ok') { Write-JsonFile $buildInfoPath $row }   # describes a player that is there
Write-Step ("{0} {1}: {2} in {3}s" -f $Game, $short, $status, $row.duration_s)
$row
if ($status -ne 'ok') { exit 1 }
