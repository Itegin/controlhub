@echo off
cd /d "%~dp0"

if not exist "icon.ico" (
    python tools\make_icon.py
)

if not exist "%USERPROFILE%\Desktop\IT-Deck Agent.lnk" (
    powershell -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\IT-Deck Agent.lnk'); $s.TargetPath = '%~f0'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0icon.ico'; $s.Save()"
)

python agent.py
if %ERRORLEVEL% EQU 0 (
    exit
) else (
    pause
)
