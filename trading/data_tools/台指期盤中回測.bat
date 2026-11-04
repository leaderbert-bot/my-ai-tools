@echo off
setlocal
chcp 65001 >nul
title TW Radar - TAIEX futures intraday strategies (Mark Yang ORB / 400-lot breakout)
cd /d "%~dp0"
echo.
echo   Backtest two intraday TXF strategies on data\txf_1m.json.gz. Writes 台指期盤中回測.md
echo   Options:  orb_txf.py --cost 3 --orb-width 80 --vol 300
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
%PY% "%~dp0orb_txf.py" %*
echo.
pause
