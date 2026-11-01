@echo off
chcp 65001 >nul
rem 관리자 권한이 아니면 관리자 권한으로 다시 실행(스크랩마스터가 관리자 권한으로 실행되기 때문)
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo [3단계] 새벽 자동 실행(03:45, 04:03, 04:12)을 등록합니다.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_schedule.ps1"
pause
