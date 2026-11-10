<#
.SYNOPSIS
  Exclude recorded bundles from the dataset without deleting them (e.g. recorded from a broken build).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File mark-invalid.ps1 harbor-run -Commit 52a6f2a1 -Reason 'the scene lost its lighting'
  powershell -ExecutionPolicy Bypass -File mark-invalid.ps1 <game> -RunId <run id> -Reason '...'

  Writes INVALID (the reason) into each bundle, sets validation.json status to "invalid" (previous status kept in
  status_before_invalid) and appends an "invalidated" row to .recording\<game>\runs.jsonl. Files are kept.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [string]$Commit,
    [string[]]$RunId,
    [Parameter(Mandatory = $true)][string]$Reason
)
. (Join-Path $PSScriptRoot 'common.ps1')
$info = Get-GameInfo $Game
if (-not $Commit -and -not $RunId) { throw 'give -Commit or -RunId' }
$RunId = @($RunId | ForEach-Object { $_ -split ',' } | Where-Object { $_ })   # "a,b" from powershell -File arrives as one string
$root = Join-Path $RecordingsRoot $Game
$dirs = @(Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '_*' } | Where-Object {
    if ($RunId) { return $_.Name -in $RunId }
    $m = $null; try { $m = Read-JsonFile (Join-Path $_.FullName 'metadata.json') } catch { }
    $b = Get-Prop $m 'build'
    $b -and ("$(Get-Prop $b 'commit')".StartsWith($Commit) -or "$(Get-Prop $b 'short_sha')".StartsWith($Commit))
})
if (-not $dirs.Count) { throw "no bundles of $Game match" }
foreach ($d in $dirs) {
    $time = (Get-Date).ToString('o')
    [IO.File]::WriteAllText((Join-Path $d.FullName 'INVALID'), "$time $Reason`n", $Utf8NoBom)
    $vPath = Join-Path $d.FullName 'validation.json'
    $v = Read-JsonFile $vPath
    $before = $null
    if ($v) {
        $before = $v.status
        if ($v.status -ne 'invalid') { $v | Add-Member -Force NoteProperty status_before_invalid $v.status }
        $v.status = 'invalid'
        $v | Add-Member -Force NoteProperty invalid_reason $Reason
        $v | Add-Member -Force NoteProperty invalidated_at $time
        Write-JsonFile $vPath $v
    }
    Add-JsonLine (Join-Path $info.LogDir 'runs.jsonl') ([ordered]@{ event = 'invalidated'; run_id = $d.Name; time = $time; reason = $Reason; status_before = $before; bundle = $d.FullName })
    Write-Step "$($d.Name): invalid ($Reason), was $before"
}
