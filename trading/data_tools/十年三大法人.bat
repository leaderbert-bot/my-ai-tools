@echo off
setlocal
chcp 65001 >nul
title TW Radar - backfill 10 years of institutional investors (TWSE/TPEx)
cd /d "%~dp0"
echo.
echo   Backfill daily institutional-investor net buy/sell (foreign, trust, dealer; lots)
echo   from TWSE T86 and TPEx, 2016-01-01 to yesterday, into data\inst10\inst10_YYYY.json.gz.
echo   Does not touch the radar's own inst_hist.json. About 2,400 days at 1.5 s each: 2-3 hours.
echo   Saves every 20 days; safe to stop and rerun. Run it on ONE computer only.
echo   For 2012-2015 as well:  inst10_dl.py --since 2012-05-02
echo.
set "PY="
py -3 -V >nul 2>&1 && set "PY=py -3"
if not defined PY (python -V >nul 2>&1 && set "PY=python")
if not defined PY (python3 -V >nul 2>&1 && set "PY=python3")
if not defined PY (
  echo   Python not found. Install from https://www.python.org/downloads/
  echo   and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
%PY% "%~dp0inst10_dl.py" %*
echo.
pause
