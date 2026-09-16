@echo off
rem ============================================================
rem  Run WinTop with a console window so errors are visible.
rem  (Use this when the tool does not start and you want to see why.)
rem ============================================================
setlocal
set "PY="
for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [WinTop] python.exe not found. Please install Python 3.8+ first.
  pause
  exit /b 1
)
"%PY%" "%~dp0win_topmost.py"
echo.
echo [WinTop] exited. Detail log: %TEMP%\wintop.log
pause
