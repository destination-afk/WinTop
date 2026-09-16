@echo off
rem ============================================================
rem  WinTop launcher - run the tool with pythonw (no console)
rem ============================================================
setlocal
set "PYW="
for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do if not defined PYW set "PYW=%%P"
if defined PYW (
  start "" "%PYW%" "%~dp0win_topmost.py"
  exit /b 0
)
where py.exe >nul 2>nul && (
  start "" py.exe -w "%~dp0win_topmost.py"
  exit /b 0
)
echo [WinTop] pythonw.exe not found. Please install Python 3.8+ first
echo          and check "Add python.exe to PATH" during setup.
pause
exit /b 1
