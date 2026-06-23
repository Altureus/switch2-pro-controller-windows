@echo off
title Switch 2 Pro -- WIRELESS full-chain rumble test
echo Simulates a Dolphin rumble and forwards it to the controller over Bluetooth.
echo HOLD THE CONTROLLER. Turn it on / tap a button first (hold sync if never bonded).
echo.
python -c "import bleak" 1>nul 2>nul || python -m pip install bleak
python "%~dp0procon2\test_ble_rumble.py"
echo.
pause
