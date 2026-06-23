@echo off
title Switch 2 Pro -- install autostart
echo This makes the bridge start automatically (and silently) every time you log in,
echo so you never have to open "Start (Auto-detect).bat".
echo.
python "%~dp0procon2\autostart.py" install
echo.
pause
