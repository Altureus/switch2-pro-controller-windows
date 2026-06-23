@echo off
REM ===========================================================================
REM Build Switch2ProBridge.exe -- the GUI control panel as a single, no-Python
REM executable. The exe relaunches itself (--run-bridge) to run the USB/Bluetooth
REM bridge. Output: dist\Switch2ProBridge.exe
REM Requires Python 3 + this repo. Installs the build tooling if missing.
REM ===========================================================================
echo Installing build tooling (pyinstaller, bleak)...
python -m pip install --quiet --upgrade pyinstaller bleak
echo.
echo Building Switch2ProBridge.exe ...
python -m PyInstaller --onefile --windowed --noconfirm --clean ^
  --name Switch2ProBridge ^
  --icon Switch2ProController.ico ^
  --paths procon2 ^
  --add-data "procon2/vendor/ViGEmClient.dll;vendor" ^
  --add-data "Switch2ProController.ico;." ^
  --collect-all bleak ^
  --collect-all winrt ^
  --hidden-import launch --hidden-import bridge --hidden-import ble_bridge ^
  --hidden-import ble_connect --hidden-import mapping --hidden-import mapping_data ^
  --hidden-import hid --hidden-import winusb --hidden-import haptics ^
  --hidden-import vigem --hidden-import xinput --hidden-import autostart ^
  procon2\gui.py
echo.
echo Done.  ->  dist\Switch2ProBridge.exe
pause
