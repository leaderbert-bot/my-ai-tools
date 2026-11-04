@echo off
setlocal
chcp 65001 >nul
title TW Radar - download stock 1-min bars for event days (SinoPac, read-only)
cd /d "%~dp0"
echo.
echo   Download 1-minute bars (SinoPac Shioaji) ONLY for the event days the day-trade
echo   backtests need: limit-up close (D and D+1), panic spikes, disposition periods.
echo   Events come from data\k10y daily bars. Output: data\stk1m\stk1m_YYYY-MM.json.gz
echo   Read-only login, never places orders. Saves every 50 fetches; safe to stop and rerun.
echo   SinoPac has a daily data quota: when it stops, run again tomorrow to continue.
echo   Run it on ONE computer only.
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
%PY% "%~dp0stk1m_dl.py" %*
echo.
pause
