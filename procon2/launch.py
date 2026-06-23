#!/usr/bin/env python3
r"""
launch.py -- one entry point that auto-picks USB or Bluetooth AND hot-switches.

  python procon2/launch.py              # auto: USB while the cable is plugged in, else Bluetooth
  python procon2/launch.py --usb        # force the wired USB bridge (no switching)
  python procon2/launch.py --bluetooth  # force the wireless (BLE) bridge (no switching)
  python procon2/launch.py --debug      # pass --debug through to the USB bridge

Auto mode runs the wired bridge whenever the USB cable is connected and the
wireless bridge otherwise -- and it SWITCHES LIVE when you plug or unplug the
cable, no restart needed. (Switching tears down and recreates the virtual pad, so
Dolphin may need a quick Refresh on the changeover.) Stop with Ctrl+C.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _usb_present():
    """True if the Switch 2 Pro is on USB right now (HID or WinUSB interface)."""
    try:
        import hid
        if hid.find_device():
            return True
    except Exception:
        pass
    try:
        import winusb
        return bool(winusb._find_path(winusb.WINUSB_IFACE_GUID))
    except Exception:
        return False


# Throttled view of _usb_present() so the bridges can poll it every loop cheaply
# (enumerating HID devices on every read would be wasteful).
_usb_cache = {"t": -999.0, "v": False}


def _usb_present_cached():
    now = time.monotonic()
    if now - _usb_cache["t"] >= 0.75:
        _usb_cache["t"] = now
        _usb_cache["v"] = _usb_present()
    return _usb_cache["v"]


def _run_usb(debug, stop_when=None):
    import bridge
    return bridge.run(debug=debug, stop_when=stop_when)


def _run_ble(stop_when=None):
    try:
        import ble_bridge
    except ImportError as e:
        if "bleak" in str(e).lower():
            print("[launch] The wireless path needs the 'bleak' package. Install it with:")
            print("[launch]     python -m pip install bleak")
            return "quit"
        raise
    import asyncio
    return asyncio.run(ble_bridge.run(stop_when=stop_when))


def _supervise(debug):
    print("[launch] AUTO mode: USB while the cable is plugged in, else Bluetooth.")
    print("[launch] Plug or unplug the cable to switch live. Ctrl+C to quit.\n")
    while True:
        if _usb_present():
            print("[launch] === USB cable present -> WIRED bridge (unplug to go wireless). ===")
            status = _run_usb(debug, stop_when=lambda: not _usb_present_cached())
            if status == "quit":
                break
            print("[launch] USB cable removed -> switching to WIRELESS...\n")
        else:
            print("[launch] === No USB cable -> WIRELESS bridge (plug in to go wired). ===")
            status = _run_ble(stop_when=_usb_present_cached)
            if status == "quit":
                break
            print("[launch] USB cable detected -> switching to WIRED...\n")
        time.sleep(0.4)   # small debounce between transports


def main():
    ap = argparse.ArgumentParser(
        description="Switch 2 Pro -> Xbox 360 pad (auto USB/Bluetooth, live hot-switch)")
    ap.add_argument("--usb", action="store_true", help="force the wired USB bridge")
    ap.add_argument("--bluetooth", "--ble", dest="bluetooth", action="store_true",
                    help="force the wireless Bluetooth bridge")
    ap.add_argument("--debug", action="store_true",
                    help="pass --debug to the USB bridge (print parsed state)")
    args = ap.parse_args()

    if args.usb and args.bluetooth:
        print("[launch] pick one of --usb / --bluetooth, not both.")
        return
    try:
        if args.usb:
            _run_usb(args.debug)
        elif args.bluetooth:
            _run_ble()
        else:
            _supervise(args.debug)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
