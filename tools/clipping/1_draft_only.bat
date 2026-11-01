@echo off
chcp 65001 >nul
rem Re-run as administrator (ScrapMaster runs elevated)
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo [Step 1] Build the draft Excel only (nothing is scrapped).
python sm5_run.py --source all --no-refresh --until export
echo.
echo Result: %~dp0output\runs (latest folder)
pause
