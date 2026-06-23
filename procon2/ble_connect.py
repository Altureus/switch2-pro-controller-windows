#!/usr/bin/env python3
r"""
ble_connect.py -- connect to the Switch 2 Pro Controller over Bluetooth LE and
dump its input. PROOF OF CONCEPT for the wireless path.

The BLE protocol (GATT characteristic UUIDs, the command framing, the pairing
handshake, and the input-report layout) is adapted from:
    CareyScott/switch2controllerpc  (MIT License)
    https://github.com/CareyScott/switch2controllerpc
See THIRD_PARTY_NOTICES.md. Used and redistributed under the MIT License.

Run:  python ble_connect.py   (needs: pip install bleak)
Put the controller in PAIRING MODE first (hold the small recessed sync button
until the player LEDs run), then press buttons / move sticks while it streams.
"""
import asyncio

from bleak import BleakClient, BleakScanner

NINTENDO_MFR = 0x0553
NINTENDO_VID = 0x057E
PRO_CONTROLLER2_PID = 0x2069

# GATT characteristic UUIDs (from CareyScott/switch2controllerpc, MIT)
INPUT_REPORT_UUID = "ab7de9be-89fe-49ad-828f-118f09df7fd2"
COMMAND_WRITE_UUID = "649d4ac9-8eb7-4e6c-af44-1ea54fe5f005"
COMMAND_RESP_UUID = "c765a961-d9d8-4d36-a20a-5315b111836a"

COMMAND_PAIR = 0x15
SUB_SET_MAC, SUB_LTK1, SUB_LTK2, SUB_FINISH = 0x01, 0x04, 0x02, 0x03
COMMAND_FEATURE = 0x0C
SUB_FEATURE_INIT, SUB_FEATURE_ENABLE = 0x02, 0x04
FEATURE_MOTION = 0x04

# 32-bit button bitfield in the BLE input report (data[4:8]) -- CareyScott/MIT
SWITCH_BUTTONS = {
    "Y": 0x01, "X": 0x02, "B": 0x04, "A": 0x08, "R": 0x40, "ZR": 0x80,
    "MINUS": 0x100, "PLUS": 0x200, "R3": 0x400, "L3": 0x800,
    "HOME": 0x1000, "CAPTURE": 0x2000, "C": 0x4000,
    "DOWN": 0x10000, "UP": 0x20000, "RIGHT": 0x40000, "LEFT": 0x80000,
    "L": 0x400000, "ZL": 0x800000, "GR": 0x1000000, "GL": 0x2000000,
}


def _u(b):
    return int.from_bytes(b, "little")


def _stick(b):
    v = _u(b)
    return v & 0xFFF, v >> 12


async def _host_mac():
    from winrt.windows.devices.bluetooth import BluetoothAdapter
    a = await BluetoothAdapter.get_default_async()
    return a.bluetooth_address


class _Cmd:
    """Send a vendor command and await its response (CareyScott framing, MIT)."""
    def __init__(self, client):
        self.client = client
        self.fut = None

    def on_response(self, _sender, data):
        if self.fut and not self.fut.done():
            self.fut.set_result(bytes(data))

    async def write(self, cmd, sub, data=b""):
        buf = bytes([cmd, 0x91, 0x01, sub, 0x00, len(data), 0x00, 0x00]) + data
        self.fut = asyncio.get_running_loop().create_future()
        await self.client.write_gatt_char(COMMAND_WRITE_UUID, buf)
        resp = await asyncio.wait_for(self.fut, timeout=3.0)
        return resp[8:]


async def find_controller(should_stop=None):
    print("Scanning... put the controller in PAIRING MODE now (hold the small sync "
          "button until the LEDs run).")
    for attempt in range(4):
        if should_stop and should_stop():
            return None, False
        devices = await BleakScanner.discover(timeout=8.0, return_adv=True)
        for addr, (dev, adv) in devices.items():
            md = adv.manufacturer_data.get(NINTENDO_MFR)
            if md and len(md) >= 16 and _u(md[3:5]) == NINTENDO_VID:
                pid = _u(md[5:7])
                pairing = _u(md[10:16]) == 0
                print(f"  found {addr}  pid={pid:#06x}  "
                      f"{'PAIRING MODE' if pairing else 'reconnecting'}")
                return dev, pairing
        print(f"  not seen yet (attempt {attempt + 1}/4) -- re-tap sync if needed...")
    return None, False


async def main():
    dev, pairing = await find_controller()
    if not dev:
        print("\nController not found. Make sure it's in pairing mode (LEDs running) "
              "and your USB Bluetooth adapter is the active radio.")
        return 1

    print(f"\nConnecting to {dev.address} ...")
    async with BleakClient(dev, timeout=20.0, winrt={"use_cached_services": False}) as client:
        print("Connected. Configuring...")
        cmd = _Cmd(client)
        await client.start_notify(COMMAND_RESP_UUID, cmd.on_response)

        # subscribe to input first so we catch everything
        count = {"n": 0}
        last = {"s": None}

        def on_input(_sender, data):
            count["n"] += 1
            if len(data) < 16:
                return
            buttons = _u(data[4:8])
            lx, ly = _stick(data[10:13])
            rx, ry = _stick(data[13:16])
            pressed = "+".join(n for n, b in SWITCH_BUTTONS.items() if buttons & b) or "-"
            line = f"btns={pressed:32s} L=({lx:>4},{ly:>4}) R=({rx:>4},{ry:>4})"
            if line != last["s"]:
                print(f"  {line}")
                last["s"] = line

        await client.start_notify(INPUT_REPORT_UUID, on_input)

        # enable motion feature so the controller streams (best-effort)
        try:
            f = FEATURE_MOTION.to_bytes(1, "little").ljust(4, b"\0")
            await cmd.write(COMMAND_FEATURE, SUB_FEATURE_INIT, f)
            await cmd.write(COMMAND_FEATURE, SUB_FEATURE_ENABLE, f)
            print("Features enabled.")
        except Exception as e:
            print(f"(feature enable skipped: {type(e).__name__})")

        # pair / bond to this PC so it auto-reconnects next time (best-effort)
        if pairing:
            try:
                mac = await _host_mac()
                await cmd.write(COMMAND_PAIR, SUB_SET_MAC,
                                b"\x00\x02" + mac.to_bytes(6, "little") + mac.to_bytes(6, "little"))
                await cmd.write(COMMAND_PAIR, SUB_LTK1, bytes(
                    [0x00, 0xea, 0xbd, 0x47, 0x13, 0x89, 0x35, 0x42, 0xc6, 0x79,
                     0xee, 0x07, 0xf2, 0x53, 0x2c, 0x6c, 0x31]))
                await cmd.write(COMMAND_PAIR, SUB_LTK2, bytes(
                    [0x00, 0x40, 0xb0, 0x8a, 0x5f, 0xcd, 0x1f, 0x9b, 0x41, 0x12,
                     0x5c, 0xac, 0xc6, 0x3f, 0x38, 0xa0, 0x73]))
                await cmd.write(COMMAND_PAIR, SUB_FINISH, b"\0")
                print("Paired/bonded to this PC (should auto-reconnect next time).")
            except Exception as e:
                print(f"(pairing skipped: {type(e).__name__})")

        print("\n>>> Streaming input for 15 seconds -- PRESS BUTTONS / MOVE STICKS! <<<\n")
        await asyncio.sleep(15.0)

    print(f"\nReceived {count['n']} input reports over Bluetooth.")
    if count["n"]:
        print(">>> WIRELESS INPUT WORKS! The controller streams over BLE. <<<")
    else:
        print("Connected but no input reports arrived -- we may need a different "
              "feature-enable or the pairing step. Paste this output back.")
    return 0


if __name__ == "__main__":
    asyncio.run(main())
