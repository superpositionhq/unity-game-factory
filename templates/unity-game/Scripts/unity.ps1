# __TITLE__: heavy Unity jobs through the machine-wide limiter (<root>\tools\unity-heavy.ps1).
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 setup                       (first open: packages, URP, settings)
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 compile                     (open, import, compile, quit)
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 step -Method <Ns.Class.Method> -Reason "..." [-Render] [-NoQuit]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 test [-Platform EditMode|PlayMode] [-Filter <name>]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 build [-Development] [-Backend mono|il2cpp] [-Reason "..."]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 play [-Scenario <n>] [-Render] [-Seconds 60] [-Extra "..."]
# `step` runs one editor step (a static method under Assets/Editor/Steps/) with -batchmode -executeMethod. Keep this call
# shape: the creation replay (not available yet) will recognise "unity.ps1 step -Method <Ns.Class.Method>" in the
# recorded command. The step logs its own workflow.jsonl rows; -Reason reaches it as $env:UNITY_RUN_REASON. -Render
# drops -nographics (the job then holds a GPU slot): only for steps that need the GPU (lightmap bakes, screenshots,
# shader warm-up).
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
if (-not (Test-Path $Heavy)) { Write-Error "job limiter not found: $Heavy (run machine/bootstrap.ps1)"; exit 2 }
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
  Select-String -Path $Log -Pattern 'error CS\d+|\w+Exception: |Aborting batchmode|Scripts have compiler errors|executeMethod .* could not be found|another Unity instance|No valid Unity Editor license|\[workflow\]' |
    Select-Object -Last 40 | ForEach-Object { $_.Line.Trim() }
  # Unity exits 198 without a licence: say so plainly, it is the person's to fix, not the game's
  if (Select-String -Path $Log -Pattern 'No valid Unity Editor license' -Quiet) {
    Write-Host 'LICENCE: no activated Unity licence. Unity Hub > sign in > Settings > Licenses > Add (Unity Personal where its terms allow, otherwise the seat your org gives you), then run this again.'
  }
}
function Done([int]$Code) { Write-Host "exit code $Code ($([int]((Get-Date) - $t0).TotalSeconds) s)"; exit $Code }

switch ($Mode) {
  'setup' {
    # four runs: each needs what the run before it installed (Assets/Editor/Tools/ProjectSetup.cs)
    $env:UNITY_RUN_REASON = if ($Reason) { $Reason } else { 'First open: add the start packages, make URP the pipeline, import the text essentials, set the shared player settings' }
    $steps = @(
      @('packages', @('-executeMethod', '__PROJECT__.EditorTools.ProjectSetup.AddPackages'), $false),
      @('urp', @('-executeMethod', '__PROJECT__.EditorTools.Urp.UrpSetup.Apply'), $true),
      @('text', @('-executeMethod', '__PROJECT__.EditorTools.ProjectSetup.ImportTextEssentials'), $false),
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
    Remove-Item -LiteralPath $xml -ErrorAction SilentlyContinue   # an earlier run's results would pass for this run's
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
    $env:UNITY_RUN_REASON = $Reason   # the build's workflow row carries it
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
    Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue   # a player that never starts must not show an old log
    $a = @('-logFile', $log)
    if ($Render) { $a += @('-screen-fullscreen', '0', '-screen-width', '1280', '-screen-height', '720') } else { $a += @('-batchmode', '-nographics') }
    if ($Scenario -gt 0) { $a += @('-scenario', "$Scenario") }
    $a += ($Extra -split ' ' | Where-Object { $_ })
    # a player runs until the game quits: a small wrapper stops it after -Seconds, so the slot is always released.
    # -Seconds counts from the player's start: on a busy PC a headless player was still loading after 20 s.
    # Process.Start, not Start-Process: Start-Process splits an argument holding a space (the log path under
    # C:\Users\First Last\...) and loses the exit code of a player that ends before the wait starts.
    $wrap = Join-Path $Logs "play_$Tag.ps1"
    $argLine = ($a | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    [IO.File]::WriteAllText($wrap, @"
`$psi = New-Object Diagnostics.ProcessStartInfo '$($exe -replace "'", "''")', '$($argLine -replace "'", "''")'
`$psi.UseShellExecute = `$false
`$psi.WorkingDirectory = '$((Split-Path $exe) -replace "'", "''")'
`$psi.RedirectStandardOutput = `$true; `$psi.RedirectStandardError = `$true
`$p = [Diagnostics.Process]::Start(`$psi)
`$p.BeginOutputReadLine(); `$p.BeginErrorReadLine()   # the player's console lines are read and dropped: its log is the file
if (-not `$p.WaitForExit($Seconds * 1000)) { Stop-Process -Id `$p.Id -Force; exit 124 }
exit `$p.ExitCode
"@)
    # the limiter sees powershell, not the player: -Gpu claims the GPU slot for a rendered run
    if ($Render) { & $Heavy -Label "__SLUG__ play $Tag" -Gpu -- powershell -NoProfile -ExecutionPolicy Bypass -File $wrap *> $null }
    else { & $Heavy -Label "__SLUG__ play $Tag" -- powershell -NoProfile -ExecutionPolicy Bypass -File $wrap *> $null }
    $code = $LASTEXITCODE
    if (Test-Path $log) { Select-String -Path $log -Pattern 'Exception|Error' | Select-Object -Last 20 | ForEach-Object { $_.Line.Trim() } }
    if ($code -eq 124) { Write-Host "stopped after $Seconds s (the game did not quit by itself: the timeout, not a crash)" }
    Done $code
  }
}
