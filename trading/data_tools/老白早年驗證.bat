@echo off
setlocal
chcp 65001 >nul
title TW Radar - Laobai "mean reversion, weak market only" backtest on 2003-2015 data
cd /d "%~dp0"
echo.
echo   Re-run the Laobai "correct deviation" setup on the early data (data\k00y, 2003-2015).
echo   Needs numpy (pip install numpy). Takes about 5-15 minutes. Writes 老白弱勢盤_早年驗證.md
echo   To cross-check against the 2016-2026 report instead:  laobai_early.py --k10y
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
%PY% "%~dp0laobai_early.py" %*
echo.
pause
