#!/usr/bin/env python3
r"""
test_ble_rumble.py -- full-chain WIRELESS rumble test (~3s).

The Bluetooth twin of test_rumble_e2e.py. Connects to the controller over BLE,
creates the virtual Xbox pad, vibrates its OWN pad via XInput (exactly what
Dolphin does), and forwards the resulting rumble to the controller over Bluetooth
using the same vibration packet the wireless bridge uses. You should feel the real
controller buzz -- proving Dolphin -> pad -> controller, cordless.

Run:  python procon2/test_ble_rumble.py   (needs: pip install bleak)
Turn the controller on / tap a button first (hold sync if it's never been bonded).
HOLD THE CONTROLLER so you feel it.
"""
import asyncio
import ctypes as C
import os
import sys
import time
from ctypes import wintypes as W

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xinput              # noqa: E402
import ble_connect as blec  # noqa: E402  (scan/connect)
import ble_bridge as bleb   # noqa: E402  (_vib_packet, VIBRATION_UUID)
from vigem import X360Pad   # noqa: E402

from bleak import BleakClient  # noqa: E402


class VIB(C.Structure):
    _fields_ = [("l", W.WORD), ("r", W.WORD)]


async def main():
    dev, _pairing = await blec.find_controller()
    if not dev:
        print("[ble-rumble] controller not found -- turn it on / tap a button "
              "(hold sync if never bonded).")
        return 1

    xi = xinput.load()
    dll = xi[1]
    dll.XInputSetState.argtypes = [W.DWORD, C.POINTER(VIB)]
    dll.XInputSetState.restype = W.DWORD

    before = xinput.connected_slots(xi)
    pad = X360Pad()
    pad.update()
    pad.enable_rumble()
    slot = None
    for _ in range(40):
        new = xinput.connected_slots(xi) - before
        if new:
            slot = sorted(new)[0]
            break
        time.sleep(0.05)
    if slot is None:
        print("[ble-rumble] couldn't find our pad's XInput slot.")
        pad.close()
        return 1

    try:
        async with BleakClient(dev, timeout=20.0) as client:
            print(f"[ble-rumble] connected to {dev.address}; pad on slot {slot}.")
            print("[ble-rumble] Sending Dolphin-style vibration for 3s -- "
                  "HOLD THE CONTROLLER and feel it buzz...")
            dll.XInputSetState(slot, C.byref(VIB(0xC000, 0xC000)))  # ~75% both motors

            pid = 0
            sent = 0
            t_end = time.time() + 3.0
            while time.time() < t_end:
                large, small = pad.rumble
                if large or small:
                    try:
                        await client.write_gatt_char(
                            bleb.VIBRATION_UUID, bleb._vib_packet(large, small, pid),
                            response=False)
                        sent += 1
                    except Exception:
                        pass
                    pid = (pid + 1) & 0x0F
                await asyncio.sleep(0.04)

            dll.XInputSetState(slot, C.byref(VIB(0, 0)))            # stop
            try:
                await client.write_gatt_char(
                    bleb.VIBRATION_UUID, bleb._vib_packet(0, 0, pid), response=False)
            except Exception:
                pass
    finally:
        pad.reset()
        pad.update()
        pad.close()

    print(f"[ble-rumble] done. pad.rumble last seen = {pad.rumble}, "
          f"BLE vibration packets forwarded = {sent}.")
    print("[ble-rumble] >>> Did the controller buzz for ~3 seconds? <<<")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
