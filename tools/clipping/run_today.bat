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
echo 오늘 자 검토 그룹(자동검토_MMDD_…)에 바로 실행합니다.
python sm5_run.py --source all
pause
