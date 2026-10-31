@echo off
chcp 65001 >nul
rem 사용법: 검색결과 엑셀 파일을 이 파일 위에 끌어다 놓으세요.
cd /d "%~dp0"
if "%~1"=="" (
  echo 검색결과 엑셀 파일을 이 bat 파일 위로 끌어다 놓으세요.
  pause
  exit /b 1
)
python -m scrapdraft recommend "%~1"
pause
