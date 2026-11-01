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
echo [1단계] 초안 엑셀만 만듭니다(스크랩마스터에 담지 않음).
python sm5_run.py --source all --no-refresh --until export
echo.
echo 결과: %~dp0output\runs 폴더의 최신 검토초안 엑셀
pause
