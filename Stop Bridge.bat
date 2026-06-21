@echo off
title Switch 2 Pro -- stop bridge
echo Stops a running bridge (useful when it was started silently by autostart).
echo.
python "%~dp0procon2\autostart.py" stop
echo.
pause
