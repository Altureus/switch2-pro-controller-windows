@echo off
title Switch 2 Pro -^> Xbox 360 bridge (Auto: USB or Bluetooth)
echo ============================================================
echo   Switch 2 Pro Controller -^> virtual Xbox 360 pad
echo   AUTO: USB while the cable is plugged in, else Bluetooth.
echo   Plug or UNPLUG the cable to switch live (no restart).
echo ============================================================
echo Keep this window open while you play.
echo TIP: HOLD the controller when you plug in USB (its mouse
echo sensor moves the cursor if it's lying on a desk).
echo When it says which XInput slot it is, click REFRESH in
echo Dolphin's controller config so Dolphin re-acquires it.
echo Press Ctrl+C (or just close this window) to stop.
echo ============================================================
echo.
python "%~dp0procon2\launch.py"
echo.
echo Bridge stopped. Press any key to close.
pause >nul
