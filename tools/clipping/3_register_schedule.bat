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
echo [Step 3] Register the early-morning runs (03:45, 04:03, 04:12).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_schedule.ps1"
pause
