@echo off
rem ============================================================
rem  Rebuild WinTop.exe (after editing win_topmost.py CONFIG)
rem  Requires: the bundled python + _pyi folder (PyInstaller)
rem ============================================================
setlocal
set "PY=python"
where python >nul 2>nul || set "PY=py"
set "DIR=%~dp0"
if not exist "%DIR%_pyi\PyInstaller" (
  "%PY%" -m pip install --disable-pip-version-check --target "%DIR%_pyi" pyinstaller || (pause & exit /b 1)
)
set "PYTHONPATH=%DIR%_pyi"
"%PY%" -m PyInstaller --noconfirm --onefile --noconsole --name WinTop --icon "%DIR%win.ico" --distpath "%DIR%" --workpath "%DIR%_build" --specpath "%DIR%" "%DIR%win_topmost.py"
if %errorlevel%==0 (
  echo.
  echo [WinTop] Done: %DIR%WinTop.exe
) else (
  echo [WinTop] Build failed, see output above.
)
pause
