@echo off
rem ============================================================
rem  Create a shortcut in the Startup folder so WinTop runs at logon.
rem ============================================================
setlocal
set "PYW="
for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do if not defined PYW set "PYW=%%P"
if not defined PYW (
  echo [WinTop] pythonw.exe not found. Please install Python 3.8+ first.
  pause
  exit /b 1
)
set "SCRIPT=%~dp0win_topmost.py"
set "DIR=%~dp0"
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Startup') + '\WinTop.lnk'); $s.TargetPath = $env:PYW; $s.Arguments = '\"' + $env:SCRIPT + '\"'; $s.WorkingDirectory = $env:DIR; $s.Description = 'WinTop - window always-on-top tool'; $s.Save()"
if %errorlevel%==0 (
  echo [WinTop] Startup shortcut created. It will run at next logon.
) else (
  echo [WinTop] Failed to create the shortcut.
)
pause
