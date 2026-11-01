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
echo Run now into today's review groups.
python sm5_run.py --source all
pause
