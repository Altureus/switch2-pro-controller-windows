#!/usr/bin/env python3
r"""
ble_scan.py -- does your Bluetooth adapter SEE the Switch 2 controller? (proof of concept)

The Switch 2 controllers advertise over Bluetooth LE with Nintendo's manufacturer
ID 0x0553 (they are NOT standard HID-over-GATT, which is why Windows' "Add a
device" can't pair them). This scans for that advertisement so we can confirm
wireless is feasible with YOUR adapter before building anything on top.

Needs bleak:  python -m pip install bleak
Then put the controller in PAIRING MODE (hold the small recessed sync button until
the player LEDs run) and run:  python ble_scan.py
"""
import asyncio

from bleak import BleakScanner

NINTENDO = 0x0553  # Nintendo BLE company identifier


async def main():
    print("Scanning 15s for Bluetooth LE devices...")
    print(">>> Put the controller in PAIRING MODE now: hold the small recessed sync")
    print("    button (near the USB-C port) until the player LEDs run. <<<\n")
    devices = await BleakScanner.discover(timeout=15.0, return_adv=True)

    nintendo = []
    for addr, (dev, adv) in sorted(devices.items()):
        mfr = adv.manufacturer_data or {}
        is_nin = NINTENDO in mfr
        tag = "   <== NINTENDO (0x0553)!" if is_nin else ""
        print(f"  {addr}  rssi={adv.rssi:>4}  name={dev.name!r}  "
              f"mfr={[hex(k) for k in mfr]}{tag}")
        if is_nin:
            nintendo.append((addr, dev, adv))

    print(f"\n{len(devices)} BLE device(s) seen, {len(nintendo)} Nintendo (0x0553).")
    if nintendo:
        print("\n>>> FOUND a Switch 2 controller advertisement -- wireless is feasible "
              "with your adapter! <<<")
        for addr, dev, adv in nintendo:
            data = {hex(k): v.hex() for k, v in adv.manufacturer_data.items()}
            print(f"   address={addr}  name={dev.name!r}  mfr_data={data}")
    else:
        print("\nNo Nintendo (0x0553) advertisement seen. Checklist:")
        print("  - Is the controller in PAIRING MODE? (hold the sync button ~2s, LEDs run)")
        print("  - Is your USB Bluetooth adapter the active radio in Windows?")
        print("  - Re-run while the player LEDs are actively flashing.")


if __name__ == "__main__":
    asyncio.run(main())
