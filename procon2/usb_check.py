#!/usr/bin/env python3
r"""
usb_check.py -- diagnose how the Switch 2 Pro Controller shows up over USB.

Plug in the USB cable (HOLD the controller off the desk so its mouse sensor
doesn't move your cursor), then run:
    python procon2/usb_check.py

It prints every Nintendo (057E) HID interface, what hid.find_device() returns,
and whether the WinUSB vendor interface (used to wake it) is present -- so we can
see why auto-detect isn't picking up the cable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hid       # noqa: E402
import winusb    # noqa: E402


def _h(v):
    return f"0x{v:04x}" if isinstance(v, int) else str(v)


def main():
    print("=== All Nintendo (VID 0x057E) HID interfaces ===")
    nin = [d for d in hid.enumerate_hid() if d.get("vid") == hid.VENDOR_NINTENDO]
    if not nin:
        print("  (none found -- no 057E HID interface is enumerated right now)")
    for d in nin:
        print(f"  vid={_h(d['vid'])} pid={_h(d['pid'])} "
              f"usage_page={_h(d['usage_page'])} usage={_h(d['usage'])} "
              f"in_len={d['in_len']} out_len={d['out_len']} product={d['product']!r}")

    print("\n=== hid.find_device() (what _usb_present uses) ===")
    dev = hid.find_device()
    if dev:
        print(f"  FOUND: pid={_h(dev['pid'])} usage_page={_h(dev['usage_page'])} "
              f"usage={_h(dev['usage'])} product={dev['product']!r}")
    else:
        print("  None -- this is why auto-detect falls back to Bluetooth.")

    print("\n=== WinUSB vendor interface (MI_01, used to wake) ===")
    try:
        path = winusb._find_path(winusb.WINUSB_IFACE_GUID)
        print(f"  FOUND: {path}" if path else "  None (WinUSB MI_01 interface not present)")
    except Exception as e:
        print(f"  error checking WinUSB: {type(e).__name__}: {e}")

    print("\nDone. Paste this whole output back.")


if __name__ == "__main__":
    main()
