---
name: restart-windows-agent
description: Restart the IT-Deck Windows agent after changing code in agents/windows/, and verify it's running again. Use whenever agent code changed and the running process needs to pick it up.
---

# Restart Windows Agent

The agent runs as the "IT-Deck Agent" Scheduled Task (registered by
`agents/windows/install_task.ps1`, Stage 9), not a foreground console
process — CLAUDE.md's "Commands" section still describes the older
Ctrl+C/manual-rerun flow, which predates this and is stale. Restarting it
here means stopping and starting that task, not killing a terminal.

Restarting drops the agent's live WebSocket connection, so any in-flight
command from the phone will fail until it reconnects — that's expected
and is the point of invoking this skill, not something to double-confirm.

## Steps

1. Check current state:
   ```powershell
   Get-ScheduledTask -TaskName "IT-Deck Agent" | Select-Object TaskName, State
   ```
   If the task doesn't exist, tell the user to run
   `powershell -File agents/windows/install_task.ps1` first and stop.

2. Restart it:
   ```powershell
   Stop-ScheduledTask -TaskName "IT-Deck Agent"
   Start-Sleep -Seconds 2
   Start-ScheduledTask -TaskName "IT-Deck Agent"
   ```

3. Verify it came back up — poll state for a few seconds (Task Scheduler
   reports "Running" almost immediately, but give it a moment):
   ```powershell
   Start-Sleep -Seconds 2
   Get-ScheduledTask -TaskName "IT-Deck Agent" | Select-Object TaskName, State
   ```
   `State` should read `Running`. If it reads `Ready` (not running) after
   a couple retries, the process likely crashed on startup — check
   `agents/windows/.env` is present and valid, then try
   `Get-ScheduledTaskInfo -TaskName "IT-Deck Agent"` for `LastTaskResult`
   (0 = success; anything else is an error code worth looking up).

4. Report the before/after state to the user in one line — don't narrate
   each PowerShell call.
