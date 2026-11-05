@echo off
cd /d "%~dp0"
set PY=python
where py >nul 2>&1 && set PY=py -3
%PY% "%~dp0xlev_pool_recheck.py" %*
pause
