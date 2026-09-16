@echo off
rem ============================================================
rem  Remove the WinTop scheduled-task autostart (UAC will prompt)
rem ============================================================
echo [WinTop] Removing scheduled task "WinTop" ...
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-Command','Unregister-ScheduledTask -TaskName WinTop -Confirm:$false'"
echo [WinTop] Done. If you saw and accepted the UAC prompt, the task is gone.
pause
