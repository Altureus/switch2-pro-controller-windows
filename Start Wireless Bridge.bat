@echo off
title Switch 2 Pro -^> Xbox 360 bridge (WIRELESS / Bluetooth)
echo ============================================================
echo   Switch 2 Pro Controller -^> virtual Xbox 360 pad (WIRELESS)
echo ============================================================
echo This connects over Bluetooth LE -- no USB cable needed.
echo.
echo FIRST TIME: hold the small recessed sync button until the
echo player LEDs run, so it bonds to this PC. After that, just
echo turn the controller on / tap a button and it reconnects.
echo.
echo When it says which XInput slot it is, click REFRESH in
echo Dolphin's controller config so Dolphin re-acquires it.
echo Press Ctrl+C (or just close this window) to stop.
echo ============================================================
echo.
REM The wireless path needs the 'bleak' package; install it once if missing.
python -c "import bleak" 1>nul 2>nul || (
  echo Installing the Bluetooth library ^(bleak^) -- one time only...
  python -m pip install bleak
  echo.
)
python "%~dp0procon2\ble_bridge.py"
echo.
echo Wireless bridge stopped. Press any key to close.
pause >nul
