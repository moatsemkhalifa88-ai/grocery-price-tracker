# Registers a Windows scheduled task that runs the pipeline every day at 09:00.
# Run once from PowerShell:   powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\run_daily.ps1"

$action  = New-ScheduledTaskAction -Execute "powershell.exe" `
           -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At 9:00am
# StartWhenAvailable: if the PC was off at 09:00, run as soon as it is back on
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
            -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName "GroceryPriceTracker" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Daily supermarket price ingestion" -Force | Out-Null
Write-Host "Scheduled task 'GroceryPriceTracker' registered (daily 09:00)."
Write-Host "Run it now with:  Start-ScheduledTask -TaskName GroceryPriceTracker"
