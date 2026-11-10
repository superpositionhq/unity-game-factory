# __TITLE__: headless Unity runs through the machine-wide job limiter (<root>\tools\unity-heavy.ps1).
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 setup                       (first open: packages, URP, settings)
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 compile                     (open, import, compile, quit)
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 step -Method <Ns.Class.Method> -Reason "..." [-Render] [-NoQuit]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 test [-Platform EditMode|PlayMode] [-Filter <name>]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 build [-Development] [-Backend mono|il2cpp]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 play [-Scenario <n>] [-Render] [-Seconds 60] [-Extra "..."]
# `step` runs one editor step (a static method under Assets/Editor/Steps/) with -batchmode -executeMethod. Keep this call
# shape: the creation replay recognises "unity.ps1 step -Method <Ns.Class.Method>" in the recorded command. The step
# logs its own workflow.jsonl rows; -Reason reaches it as $env:UNITY_RUN_REASON. -Render drops -nographics (the job then
# holds a GPU slot): only for steps that need the GPU (lightmap bakes, screenshots, shader warm-up).
# Editor: $env:UNITY_EDITOR, else the version in ProjectSettings/ProjectVersion.txt (<root>\tools\ugf-root.ps1
# Get-UGFUnity, else C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe). Limiter: $env:UGF_ROOT\tools, else
# two folders up (<root>). Unity locks the project: close any editor that has it open first.
param(
  [Parameter(Position = 0)][ValidateSet('setup', 'compile', 'step', 'test', 'build', 'play')][string]$Mode,
  [string]$Method = '',
  [string]$Reason = '',
  [switch]$Render,
  [switch]$NoQuit,
  [ValidateSet('EditMode', 'PlayMode')][string]$Platform = 'EditMode',
  [string]$Filter = '',
  [switch]$Development,
  [ValidateSet('', 'mono', 'il2cpp')][string]$Backend = '',
  [int]$Scenario = 0,
  [int]$Seconds = 60,
  [string]$Extra = '',
  [string]$Tag = 'test'
)
$ErrorActionPreference = 'Continue'
$Proj = Split-Path $PSScriptRoot -Parent
$Root = if ($env:UGF_ROOT) { $env:UGF_ROOT } else { Split-Path (Split-Path $Proj -Parent) -Parent }
$Heavy = Join-Path $Root 'tools\unity-heavy.ps1'
if (-not (Test-Path $Heavy)) { Write-Error "job limiter not found: $Heavy (run machine\bootstrap.ps1)"; exit 2 }
$VersionFile = Join-Path $Proj 'ProjectSettings\ProjectVersion.txt'
$Version = if ((Get-Content $VersionFile -Raw) -match 'm_EditorVersion:\s*(\S+)') { $Matches[1] } else { '' }
$Unity = $env:UNITY_EDITOR
if (-not $Unity -and (Test-Path (Join-Path $Root 'tools\ugf-root.ps1'))) {
  . (Join-Path $Root 'tools\ugf-root.ps1')
  if (Get-Command Get-UGFUnity -ErrorAction SilentlyContinue) { $Unity = Get-UGFUnity $Proj }
}
if (-not $Unity) { $Unity = "C:\Program Files\Unity\Hub\Editor\$Version\Editor\Unity.exe" }
if (-not (Test-Path $Unity)) { Write-Error "Unity $Version not found at ${Unity}: install it through Unity Hub (or set UNITY_EDITOR)"; exit 2 }
$Logs = Join-Path $Proj 'Logs\unity-ps1'
New-Item -ItemType Directory -Force $Logs | Out-Null
$t0 = Get-Date

function Invoke-Unity([string]$Label, [string]$Log, [string[]]$More, [switch]$Graphics, [switch]$Quit) {
  $a = @('-batchmode', '-projectPath', $Proj, '-logFile', $Log)
  if (-not $Graphics) { $a += '-nographics' }
  if ($Quit) { $a += '-quit' }
  $a += $More
  & $Heavy -Label "__SLUG__ $Label" -- $Unity @a *> $null
  return $LASTEXITCODE
}
function Show-Errors([string]$Log) {
  if (-not (Test-Path $Log)) { Write-Host "no log: $Log"; return }
  Select-String -Path $Log -Pattern 'error CS\d+|Exception|Aborting batchmode|Scripts have compiler errors|executeMethod .* could not be found|another Unity instance|[Ll]icens(e|ing) .*(error|fail)|\[workflow\]' |
    Select-Object -Last 40 | ForEach-Object { $_.Line.Trim() }
}
function Done([int]$Code) { Write-Host "exit code $Code ($([int]((Get-Date) - $t0).TotalSeconds) s)"; exit $Code }

switch ($Mode) {
  'setup' {
    # three runs: each needs what the run before it installed (Assets/Editor/Tools/ProjectSetup.cs)
    $env:UNITY_RUN_REASON = if ($Reason) { $Reason } else { 'First open: add the start packages, make URP the pipeline, set the shared player settings' }
    $steps = @(
      @('packages', @('-executeMethod', '__PROJECT__.EditorTools.ProjectSetup.AddPackages'), $false),
      @('urp', @('-executeMethod', '__PROJECT__.EditorTools.Urp.UrpSetup.Apply'), $true),
      @('configure', @('-executeMethod', '__PROJECT__.EditorTools.ProjectSetup.Configure'), $true)
    )
    foreach ($s in $steps) {
      $log = Join-Path $Logs "setup_$($s[0]).log"
      $code = Invoke-Unity "setup $($s[0])" $log $s[1] -Quit:$s[2]
      Show-Errors $log
      Write-Host "setup $($s[0]): exit code $code"
      if ($code -ne 0) { Done $code }
    }
    Done 0
  }
  'compile' {
    $log = Join-Path $Logs 'compile.log'
    $code = Invoke-Unity 'compile' $log @() -Quit
    Show-Errors $log
    Done $code
  }
  'step' {
    if ($Method -notmatch '^[A-Za-z_][A-Za-z0-9_.]*\.[A-Za-z_][A-Za-z0-9_]*$') { Write-Error 'pass -Method <Namespace.Class.Method> (a static method of an editor step)'; exit 2 }
    $env:UNITY_RUN_REASON = $Reason
    $name = ($Method -split '\.')[-2..-1] -join '.'
    $log = Join-Path $Logs "step_$name.log"
    $code = Invoke-Unity "step $name" $log @('-executeMethod', $Method) -Graphics:$Render -Quit:(-not $NoQuit)
    Show-Errors $log
    Done $code
  }
  'test' {
    # -runTests quits by itself: never with -quit
    $xml = Join-Path $Logs "tests_$Platform.xml"
    $log = Join-Path $Logs "tests_$Platform.log"
    $more = @('-runTests', '-testPlatform', $Platform, '-testResults', $xml)
    if ($Filter) { $more += @('-testFilter', $Filter) }
    $code = Invoke-Unity "test $Platform" $log $more
    if (Test-Path $xml) {
      $run = ([xml](Get-Content $xml -Raw)).'test-run'
      Write-Host "tests: $($run.total) total, $($run.passed) passed, $($run.failed) failed, $($run.skipped) skipped"
      ([xml](Get-Content $xml -Raw)).SelectNodes("//test-case[@result='Failed']") | Select-Object -First 15 |
        ForEach-Object { Write-Host "  FAILED $($_.fullname): $($_.failure.message.'#cdata-section')" }
    } else { Show-Errors $log }
    Done $code
  }
  'build' {
    $log = Join-Path $Logs 'build.log'
    $more = @('-executeMethod', '__PROJECT__.EditorTools.BuildPlayer.BuildWindows', '-buildOut', (Join-Path $Proj 'Build\Windows'))
    if ($Development) { $more += '-development' }
    if ($Backend) { $more += @('-backend', $Backend) }
    $code = Invoke-Unity 'build' $log $more -Quit
    Show-Errors $log
    Done $code
  }
  'play' {
    $exe = Join-Path $Proj 'Build\Windows\__PROJECT__.exe'
    if (-not (Test-Path $exe)) { Write-Error "no player build at $exe (run: unity.ps1 build)"; exit 2 }
    $log = Join-Path $Logs "play_$Tag.log"
    $a = @('-logFile', $log)
    if ($Render) { $a += @('-screen-fullscreen', '0', '-screen-width', '1280', '-screen-height', '720') } else { $a += @('-batchmode', '-nographics') }
    if ($Scenario -gt 0) { $a += @('-scenario', "$Scenario") }
    $a += ($Extra -split ' ' | Where-Object { $_ })
    # a player runs until the game quits: a small wrapper stops it after -Seconds, so the slot is always released
    $wrap = Join-Path $Logs "play_$Tag.ps1"
    $argText = ($a | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ', '
    [IO.File]::WriteAllText($wrap, @"
`$p = Start-Process -FilePath '$($exe -replace "'", "''")' -ArgumentList @($argText) -WorkingDirectory '$((Split-Path $exe) -replace "'", "''")' -PassThru
if (-not `$p.WaitForExit($Seconds * 1000)) { Stop-Process -Id `$p.Id -Force; exit 124 }
exit `$p.ExitCode
"@)
    # the limiter sees powershell, not the player: -Gpu claims the GPU slot for a rendered run
    if ($Render) { & $Heavy -Label "__SLUG__ play $Tag" -Gpu -- powershell -NoProfile -ExecutionPolicy Bypass -File $wrap *> $null }
    else { & $Heavy -Label "__SLUG__ play $Tag" -- powershell -NoProfile -ExecutionPolicy Bypass -File $wrap *> $null }
    $code = $LASTEXITCODE
    if (Test-Path $log) { Select-String -Path $log -Pattern 'Exception|Error' | Select-Object -Last 20 | ForEach-Object { $_.Line.Trim() } }
    if ($code -eq 124) { Write-Host "stopped after $Seconds s (the game did not quit by itself)" }
    Done $code
  }
}
