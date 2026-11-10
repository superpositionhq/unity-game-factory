# __TITLE__: heavy Unity jobs through the machine-wide limiter (<root>\tools\unity-heavy.ps1).
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 setup                       (first open: packages, URP, settings)
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 compile                     (open, import, compile, quit)
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 step -Method <Ns.Class.Method> -Reason "..." [-Render] [-NoQuit]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 test [-Platform EditMode|PlayMode] [-Filter <name>]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 build [-Development] [-Backend mono|il2cpp] [-Reason "..."]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 play [-Scenario <n>] [-Render] [-Seconds 60] [-Extra "..."]
#   powershell -ExecutionPolicy Bypass -File Scripts/unity.ps1 autoplay [-Scenario <n>] [-MaxSeconds 120] [-Seed 0] [-Skill 1] [-Audible] [-Extra "..."]
# `autoplay` runs the built player as a recording does (the AutoPlay drop-in, Assets/AutoPlay): the bot plays scenario n
# for at most -MaxSeconds, starting at once (no recorder's go file), on a Windows desktop of its own (nothing on the
# screen, the keyboard and cursor left alone, the sound muted unless -Audible); the run's files go to
# Logs/autoplay/<time>_s<n>/, and a summary of them is printed.
# `step` runs one editor step (a static method under Assets/Editor/Steps/) with -batchmode -executeMethod. Keep this call
# shape: the creation replay recognises "unity.ps1 step -Method <Ns.Class.Method>" in the recorded command. The step
# logs its own workflow.jsonl rows; -Reason reaches it as $env:UNITY_RUN_REASON. -Render
# drops -nographics (the job then holds a GPU slot): only for steps that need the GPU (lightmap bakes, screenshots,
# shader warm-up).
# Editor: $env:UNITY_EDITOR, else the version in ProjectSettings/ProjectVersion.txt (<root>\tools\ugf-root.ps1
# Get-UGFUnity, else C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe). Limiter: $env:UGF_ROOT\tools, else
# two folders up (<root>). Unity locks the project: close any editor that has it open first.
param(
  [Parameter(Position = 0)][ValidateSet('setup', 'compile', 'step', 'test', 'build', 'play', 'autoplay')][string]$Mode,
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
  [string]$Tag = 'test',
  [int]$MaxSeconds = 120,
  [int]$Seed = 0,
  [double]$Skill = 1,
  [switch]$Audible
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
  Remove-Item -LiteralPath $Log -ErrorAction SilentlyContinue   # an editor that never starts must not show an old log
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

# `autoplay`: the player on a desktop of its own (WinSta0\AutoPlay), in a job object that ends it, and whatever it
# started, when the wrapper ends; stopped after $limit s (exit code 124). Written into the run's wrapper script.
$DeskRun = @'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class AutoPlayDesk
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct StartupInfo
    {
        public int cb; public string reserved; public string desktop; public string title;
        public int x, y, width, height, xChars, yChars, fill, flags;
        public short show, reserved2; public IntPtr reserved3, stdIn, stdOut, stdErr;
    }
    [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { public IntPtr process, thread; public int pid, tid; }
    [StructLayout(LayoutKind.Sequential)] struct Basic
    {
        public long perProcessTime, perJobTime; public int flags; public UIntPtr minWs, maxWs; public int processes;
        public UIntPtr affinity; public int priority, scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct Extended
    {
        public Basic basic; public ulong r1, r2, w1, w2, o1, o2; public UIntPtr processMemory, jobMemory, peakProcess, peakJob;
    }
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateDesktopW(string name, IntPtr device, IntPtr mode, int flags, uint access, IntPtr attributes);
    [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr CreateJobObjectW(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref Extended info, int size);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateProcessW(string app, StringBuilder commandLine, IntPtr pa, IntPtr ta, bool inherit, int flags, IntPtr env, string cwd, ref StartupInfo si, out ProcessInfo pi);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")] static extern int ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr handle, uint ms);
    [DllImport("kernel32.dll")] static extern bool GetExitCodeProcess(IntPtr process, out uint code);
    [DllImport("kernel32.dll")] static extern bool TerminateProcess(IntPtr process, uint code);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);

    public static int Run(string exe, string args, string cwd, string name, int seconds)
    {
        IntPtr desktop = CreateDesktopW(name, IntPtr.Zero, IntPtr.Zero, 0, 0x10000000, IntPtr.Zero);
        if (desktop == IntPtr.Zero) throw new Exception("CreateDesktop failed, error " + Marshal.GetLastWin32Error());
        IntPtr job = CreateJobObjectW(IntPtr.Zero, null);
        try
        {
            Extended limits = new Extended();
            limits.basic.flags = 0x2000;
            if (!SetInformationJobObject(job, 9, ref limits, Marshal.SizeOf(typeof(Extended))))
                throw new Exception("SetInformationJobObject failed, error " + Marshal.GetLastWin32Error());
            StartupInfo si = new StartupInfo();
            si.cb = Marshal.SizeOf(typeof(StartupInfo));
            si.desktop = "WinSta0\\" + name;
            ProcessInfo pi;
            StringBuilder line = new StringBuilder("\"" + exe + "\" " + args);
            if (!CreateProcessW(null, line, IntPtr.Zero, IntPtr.Zero, false, 4, IntPtr.Zero, cwd, ref si, out pi))
                throw new Exception("CreateProcess failed, error " + Marshal.GetLastWin32Error());
            try
            {
                if (!AssignProcessToJobObject(job, pi.process)) { TerminateProcess(pi.process, 1); throw new Exception("AssignProcessToJobObject failed"); }
                ResumeThread(pi.thread);
                if (WaitForSingleObject(pi.process, (uint)seconds * 1000) != 0)
                {
                    TerminateProcess(pi.process, 124);
                    WaitForSingleObject(pi.process, 10000);
                    return 124;
                }
                uint code;
                GetExitCodeProcess(pi.process, out code);
                return unchecked((int)code);
            }
            finally { CloseHandle(pi.thread); CloseHandle(pi.process); }
        }
        finally { CloseHandle(job); CloseDesktop(desktop); }
    }
}
"@
exit ([AutoPlayDesk]::Run($exe, $argLine, (Split-Path $exe), 'AutoPlay', $limit))
'@

# `autoplay`: what the run wrote (docs: the AutoPlay drop-in's files), in a few lines.
function Show-Run([string]$Dir, [int]$Code) {
  Write-Host "run files: $Dir"
  $missing = @('ready.json', 'inputs.jsonl', 'telemetry.jsonl', 'outcome.json', 'clock.json', 'audio.wav', 'audio_clock.jsonl') |
    Where-Object { -not (Test-Path (Join-Path $Dir $_)) }
  if ($missing) { Write-Host "missing: $($missing -join ', ')" }
  $o = $null
  try { $o = Get-Content -Raw (Join-Path $Dir 'outcome.json') -ErrorAction Stop | ConvertFrom-Json } catch { }
  if ($o) {
    $fps = if ($o.duration_s -gt 0) { $o.frames / $o.duration_s } else { 0 }
    $rate = 48000
    try {
      $f = [IO.File]::OpenRead((Join-Path $Dir 'audio.wav')); $h = New-Object byte[] 28; [void]$f.Read($h, 0, 28); $f.Close()
      if ([BitConverter]::ToInt32($h, 24) -gt 0) { $rate = [BitConverter]::ToInt32($h, 24) }
    } catch { }
    Write-Host ("outcome: {0}, score {1}; {2:N1} s of scenario at {3:N1} fps; {4} inputs injected; {5:N1} s of sound ({6} gaps filled){7}" -f
      $o.result, $o.score, $o.duration_s, $fps, $o.inputs_injected, ($o.audio_frames / $rate), $o.audio_gaps,
      $(if ($o.go_timed_out) { '; started without a go file' } else { '' }))
    if ($o.extra -and @($o.extra.PSObject.Properties).Count) { Write-Host "extra: $($o.extra | ConvertTo-Json -Compress -Depth 4)" }
  }
  foreach ($file in 'inputs.jsonl', 'telemetry.jsonl') {
    $p = Join-Path $Dir $file
    if (-not (Test-Path $p)) { continue }
    $kinds = @{}; $errors = @()
    foreach ($l in [IO.File]::ReadLines($p)) {
      if ($l -match '"(?:type|event)":"([^"]+)"') { $kinds[$Matches[1]] = 1 + [int]$kinds[$Matches[1]] }
      if ($l -match '"event":"error".*"message":"((?:[^"\\]|\\.)*)"') { $errors += $Matches[1] }
    }
    Write-Host "${file}: $(($kinds.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')"
    $errors | Select-Object -First 8 | ForEach-Object { Write-Host "  error: $_" }
  }
  $w = Join-Path $Dir 'watchdog.json'
  if (Test-Path $w) { Write-Host "watchdog: $((Get-Content -Raw $w).Trim())" }
  $log = Join-Path $Dir 'game.log'
  if (Test-Path $log) { Select-String -Path $log -Pattern 'AutoPlay: |Exception' | Select-Object -Last 25 | ForEach-Object { $_.Line.Trim() } }
  if ($Code -eq 0) { Write-Host 'the run ended and the player quit' }
  elseif ($Code -eq 124 -and (Test-Path $w)) { Write-Host 'the player hung: its watchdog ended it (watchdog.json)' }
  elseif ($Code -eq 124) { Write-Host "the player was stopped after its time limit (-MaxSeconds + 180 s)" }
  else { Write-Host "the player ended with exit code ${Code}: a crash, or it was killed (read game.log)" }
}

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
  'autoplay' {
    $exe = Join-Path $Proj 'Build\Windows\__PROJECT__.exe'
    if (-not (Test-Path $exe)) { Write-Error "no player build at $exe (run: unity.ps1 build)"; exit 2 }
    if ($MaxSeconds -lt 1) { Write-Error 'pass -MaxSeconds 1 or more'; exit 2 }
    $n = if ($Scenario -gt 0) { $Scenario } else { 1 }
    $out = Join-Path $Proj ('Logs\autoplay\{0}_s{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $n)
    New-Item -ItemType Directory -Force $out | Out-Null
    $a = @('-autoplay', '-scenario', "$n", '-seed', "$Seed", '-skill', $Skill.ToString([Globalization.CultureInfo]::InvariantCulture),
      '-maxSeconds', "$MaxSeconds", '-goTimeout', '0', '-outputDir', $out, '-screen-fullscreen', '0', '-screen-width', '1920',
      '-screen-height', '1080', '-logFile', (Join-Path $out 'game.log'))
    if (-not $Audible) { $a += '-autoplayMute' }
    $a += ($Extra -split ' ' | Where-Object { $_ })
    $argLine = ($a | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    # the player stops itself (the run's end, or its watchdog 120 s after -MaxSeconds); the wrapper's limit is a backstop
    $wrap = Join-Path $Logs "autoplay_$Tag.ps1"
    # with a BOM: Windows PowerShell reads a script without one as ANSI, and the paths may hold any letter
    [IO.File]::WriteAllText($wrap, "`$exe = '$($exe -replace "'", "''")'`n`$argLine = '$($argLine -replace "'", "''")'`n`$limit = $($MaxSeconds + 180)`n" + $DeskRun, (New-Object Text.UTF8Encoding($true)))
    & $Heavy -Label "__SLUG__ autoplay $Tag" -Gpu -- powershell -NoProfile -ExecutionPolicy Bypass -File $wrap *> $null
    $code = $LASTEXITCODE
    Show-Run $out $code
    Done $code
  }
}
