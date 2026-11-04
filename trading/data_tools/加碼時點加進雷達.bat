@echo off
setlocal
chcp 65001 >nul
title TW Radar - add the margin-ratio add-timing card to tw_radar.py (run once)
cd /d "%~dp0"
echo.
echo   Patches tw_radar.py: adds the "add timing after ratio breaks 150%%" card to the credit page.
echo   A backup is saved as tw_radar.py.bak_cr150. Close the radar before running; restart it after.
echo.
set "PY="
py -3 -V >nul 2>&1 && set "PY=py -3"
if not defined PY (python -V >nul 2>&1 && set "PY=python")
if not defined PY (python3 -V >nul 2>&1 && set "PY=python3")
if not defined PY (
  echo   Python not found. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)
%PY% "%~dp0patch_cr150.py" %*
echo.
pause
