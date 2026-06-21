@echo off
title Switch 2 Pro -- setup check
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on your PATH.
  echo Install it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^),
  echo then run this again.
  echo.
  pause
  exit /b 1
)
python "%~dp0procon2\setup_check.py"
echo.
pause
