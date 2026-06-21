@echo off
title Switch 2 Pro -- remove autostart
echo Stops the bridge from starting at login (does not delete anything else).
echo.
python "%~dp0procon2\autostart.py" uninstall
echo.
pause
