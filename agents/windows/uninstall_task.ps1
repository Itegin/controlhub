<#
Removes the "IT-Deck Agent" scheduled task created by install_task.ps1.
Safe to re-run: if the task doesn't exist, this is a no-op, not an error.
#>

$ErrorActionPreference = "Stop"

$TaskName = "IT-Deck Agent"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
} else {
    Write-Host "No '$TaskName' task found -- nothing to remove."
}
