@echo off
chcp 65001 >nul
rem Drag a search-result Excel file onto this bat file.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if "%~1"=="" (
  echo Drag a search-result Excel file onto this bat file.
  pause
  exit /b 1
)
python -m scrapdraft recommend "%~1"
pause
