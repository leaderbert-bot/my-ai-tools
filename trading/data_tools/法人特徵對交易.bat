@echo off
setlocal
chcp 65001 >nul
title TW Radar - map institutional flows onto strategy trades (small output file)
cd /d "%~dp0"
echo.
echo   Reads data\inst10 and the strategy trade lists, writes data\inst_feat.json for Claude.
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
%PY% "%~dp0inst_feat.py" %*
echo.
pause
