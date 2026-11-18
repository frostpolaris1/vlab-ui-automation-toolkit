@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -I tools\framework\tools\export_round.py
if errorlevel 1 (
  echo [ERROR] export failed.
  pause
  exit /b 1
)
echo.
echo Exported to the latest round's export\ folder.
start "" explorer "data"
pause
