# Install four one-date Windows Task Scheduler backup triggers for approved Charnock slots.
# Requires logged-on Fedor account. No token copies or Telegram operations.
[CmdletBinding()]
param([switch]$Install, [switch]$Verify)
if ($Install -and $Verify) { throw 'Choose either -Install or -Verify' }
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$timeZoneId = (Get-TimeZone).Id
if ($timeZoneId -cne 'Russian Standard Time') {
    throw 'Windows Task Scheduler must use Europe/Moscow local clock'
}
$dispatcher = Join-Path $PSScriptRoot 'lordchrist_charnock_external_dispatch.ps1'
if (-not (Test-Path -LiteralPath $dispatcher -PathType Leaf)) {
    throw 'Reviewed Charnock dispatcher not found next to installer'
}
$taskTimes = [ordered]@{
    '09' = '2026-11-20T12:05:00'
    '10' = '2026-11-24T12:05:00'
    '11' = '2026-11-27T12:05:00'
    '12' = '2026-12-01T12:05:00'
}
$prefix = 'Lordchrist-Charnock-Reissue-'
$targetDirectory = Join-Path $env:LOCALAPPDATA 'LordchristCharnockScheduler'
$target = Join-Path $targetDirectory 'lordchrist_charnock_external_dispatch.ps1'
$pwsh = 'C:\Program Files\PowerShell\7\pwsh.exe'
if (-not (Test-Path -LiteralPath $pwsh -PathType Leaf)) {
    throw 'PowerShell 7 executable not installed at reviewed path'
}
$principalId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
if ($principalId -notmatch '(?i)\\fedor$') {
    throw 'This task must be created under the approved local Fedor account'
}
# Existing backups must not be silently replaced with a different script.
$existing = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
    $_.TaskName -like "$prefix*"
})
$sourceHash = (Get-FileHash -LiteralPath $dispatcher -Algorithm SHA256).Hash

function Confirm-CharnockTasks {
    if ($existing.Count -ne $taskTimes.Count) {
        throw 'Charnock backup task count mismatch'
    }
    if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or
        (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -cne $sourceHash) {
        throw 'Installed source SHA-256 is not the approved one'
    }
    foreach ($num in $taskTimes.Keys) {
        $taskName = "$prefix$num"
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
        $ownerName = [string]$task.Principal.UserId
        # The Windows Scheduler normalizes DOMAIN\Fedor to just Fedor.
        $correctOwner = ($ownerName -ieq $principalId -or $ownerName -ieq $env:USERNAME)
        $start = "$($taskTimes[$num])+03:00"
        if ($task.State -eq 'Disabled' -or $task.Actions[0].Execute -cne $pwsh -or
            $task.Actions[0].Arguments -notlike "*-File `"$target`" -Dispatch*" -or
            $task.Settings.WakeToRun -ne $true -or
            $task.Principal.LogonType -ne 'Interactive' -or -not $correctOwner -or
            $task.Triggers.Count -ne 1 -or $task.Triggers[0].StartBoundary -cne $start -or
            $task.Triggers[0].Repetition.Interval -cne 'PT30M' -or
            $task.Triggers[0].Repetition.Duration -cne 'PT1H35M') {
            throw "Installed task $num failed readback; examine Windows Task Scheduler"
        }
        Write-Output "VERIFIED $taskName state=$($task.State) owner=$ownerName start=$start"
    }
    Write-Output "VERIFIED_SOURCE_SHA256 $sourceHash"
}
if ($Verify) {
    Confirm-CharnockTasks
    exit 0
}
if ($existing.Count -gt 0) {
    throw 'Pre-existing Charnock backup task(s) require explicit reconciliation; no overwrite'
}
foreach ($num in $taskTimes.Keys) {
    Write-Output "PLAN $prefix$num at $($taskTimes[$num]) Moscow, 12:05/12:35/13:05/13:35"
}
if (-not $Install) {
    Write-Output 'READ_ONLY_PLAN: supply -Install to create owner-login-only future tasks'
    exit 0
}
# Verify all future due slots without allowing a fake clock in dispatch mode.
foreach ($num in $taskTimes.Keys) {
    $probe = "$($taskTimes[$num])+03:00"
    $stdout = & $pwsh -NoProfile -NonInteractive -File $dispatcher -ProbeAt $probe
    if ($LASTEXITCODE -ne 0 -or
        (@($stdout) -join "`n") -notmatch "WOULD_DISPATCH lordchrist-telegraph-charnock-$num ") {
        throw "Remote review preflight for Charnock $num failed; no tasks installed"
    }
}
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
Copy-Item -LiteralPath $dispatcher -Destination $target -Force
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -cne $sourceHash) {
    throw 'Installed dispatch script differs from reviewed source'
}
$arguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File `"$target`" -Dispatch"
$action = New-ScheduledTaskAction -Execute $pwsh -Argument $arguments -WorkingDirectory $targetDirectory
$principal = New-ScheduledTaskPrincipal -UserId $principalId -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
foreach ($num in $taskTimes.Keys) {
    $taskName = "$prefix$num"
    $at = [datetime]::ParseExact($taskTimes[$num], 'yyyy-MM-ddTHH:mm:ss',
        [Globalization.CultureInfo]::InvariantCulture)
    $trigger = New-ScheduledTaskTrigger -Once -At $at -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Minutes 95)
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Trigger $trigger -Description "Charnock ${num}: due-day only; shared guarded GitHub publisher; no backfill" -ErrorAction Stop | Out-Null
}
Confirm-CharnockTasks
Write-Output "INSTALLED_SOURCE_SHA256 $sourceHash; logged-on user required; PC availability not guaranteed"
