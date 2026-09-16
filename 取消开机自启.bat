@echo off
rem ============================================================
rem  Remove the WinTop startup shortcut.
rem ============================================================
setlocal
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WinTop.lnk" 2>nul
echo [WinTop] Startup shortcut removed (if it existed).
pause
