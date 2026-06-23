#!/usr/bin/env python3
r"""
ble_bridge.py -- WIRELESS Switch 2 Pro Controller -> virtual Xbox 360 pad bridge.

The cordless twin of bridge.py: instead of reading the controller over USB-HID,
it connects over Bluetooth LE, parses the BLE input report, and republishes the
state as a real driver-level Xbox 360 pad via ViGEmBus (vigem.py) -- so Dolphin
and any game see a standard XInput pad with no cable attached.

It reuses the USB bridge's proven pieces directly:
  * mapping.STICK_CAL / mapping._norm  -- the calibrated 12-bit stick normalization
    (the BLE sticks report the SAME raw 12-bit values as USB)
  * bridge.BUTTON_TO_XUSB              -- the Nintendo -> Xbox button map
  * bridge._detect_slot / _sync_dolphin_slot, xinput -- Dolphin slot handling
  * ble_connect.*                      -- the BLE protocol (scan/connect/pair)

The BLE protocol it builds on (GATT UUIDs, command framing, pairing handshake,
input layout) is adapted from CareyScott/switch2controllerpc (MIT). See
ble_connect.py and THIRD_PARTY_NOTICES.md.

PERSISTENCE: the virtual pad is created ONCE and held for the whole process life.
A Bluetooth drop just reads neutral, then it rescans and reconnects automatically.
Only you closing the window (Ctrl+C) ends it.

Usage:  python procon2/ble_bridge.py        (needs: pip install bleak)
First run: put the controller in PAIRING MODE (hold sync until the LEDs run) so it
bonds to this PC. After that it auto-reconnects -- just turn it on (tap any button).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge          # noqa: E402  (Nintendo->Xbox map, Dolphin slot helpers)
import mapping         # noqa: E402  (calibrated stick normalization)
import xinput          # noqa: E402
import ble_connect as blec  # noqa: E402  (BLE protocol: scan/connect/pair)
from vigem import X360Pad    # noqa: E402

from bleak import BleakClient  # noqa: E402


# --- BLE rumble (Dolphin/game -> controller HD haptics) --------------------
# Vibration GATT characteristic + 40-bit HD-rumble packet format adapted from
# CareyScott/switch2controllerpc (MIT). The Pro Controller write is
#   b"\x00" + motor + motor      where  motor = [0x50|pid] + vib1 + vib2 + vib3
# and each vib is a 5-byte little-endian field: lf_freq/amp + hf_freq/amp.
VIBRATION_UUID = "cc483f51-9258-427d-a939-630c31f72b05"


def _vd(lf_freq, lf_amp, hf_freq, hf_amp):
    v = (lf_freq & 0x1FF)
    v |= (lf_amp & 0x3FF) << 10
    v |= (hf_freq & 0x1FF) << 20
    v |= (hf_amp & 0x3FF) << 30
    return v.to_bytes(5, "little")


_VD_REST = _vd(0x0E1, 0, 0x1E1, 0)   # neutral/stop field (zero amplitude)


def _vib_packet(large, small, pid):
    """Dolphin motors (0..255) -> one Pro Controller vibration packet.
    large_motor -> low-frequency (strong) amp; small_motor -> high-frequency.
    Amplitude capped at ~0x300 (clearly felt, within the safe observed range)."""
    lf_amp = int(large / 255.0 * 0x300) if large else 0
    hf_amp = int(small / 255.0 * 0x300) if small else 0
    vib1 = _vd(0x060, lf_amp, 0x0C0, hf_amp)
    motor = bytes([0x50 | (pid & 0x0F)]) + vib1 + _VD_REST + _VD_REST
    return b"\x00" + motor + motor


async def _rumble_pump(client, pad):
    """Stream the latest rumble Dolphin sends the pad to the controller over BLE
    while active; send one 'stop' when it ends, then go quiet. ~25 Hz."""
    pid = 0
    was_active = False
    try:
        while True:
            large, small = pad.rumble
            active = bool(large or small)
            if active or was_active:
                try:
                    await client.write_gatt_char(
                        VIBRATION_UUID, _vib_packet(large, small, pid), response=False)
                except Exception:
                    pass
                pid = (pid + 1) & 0x0F
            was_active = active
            await asyncio.sleep(0.04)
    except asyncio.CancelledError:
        try:
            await client.write_gatt_char(
                VIBRATION_UUID, _vib_packet(0, 0, pid), response=False)
        except Exception:
            pass
        raise


def make_feeder(pad, counter):
    """Build the BLE input-notification handler that drives the virtual pad."""
    SB = blec.SWITCH_BUTTONS
    B2X = bridge.BUTTON_TO_XUSB
    cal = mapping.STICK_CAL
    norm = mapping._norm
    zl, zr = SB["ZL"], SB["ZR"]

    def on_input(_sender, data):
        if len(data) < 16:
            return
        buttons = int.from_bytes(data[4:8], "little")
        try:
            pad.reset()
            for name, bit in SB.items():
                if buttons & bit:
                    x = B2X.get(name)
                    if x:
                        pad.set_button(x, True)
            if buttons & zl:
                pad.set_trigger_left(1.0)
            if buttons & zr:
                pad.set_trigger_right(1.0)
            lx, ly = blec._stick(data[10:13])
            rx, ry = blec._stick(data[13:16])
            pad.set_stick_left(norm(lx, cal["LX"]), norm(ly, cal["LY"]))
            pad.set_stick_right(norm(rx, cal["RX"]), norm(ry, cal["RY"]))
            pad.update()
            counter["n"] += 1
        except Exception:
            pass

    return on_input


async def _pair(cmd):
    """Bond the controller to this PC (fixed sequence, CareyScott/MIT). Best-effort."""
    mac = await blec._host_mac()
    await cmd.write(blec.COMMAND_PAIR, blec.SUB_SET_MAC,
                    b"\x00\x02" + mac.to_bytes(6, "little") + mac.to_bytes(6, "little"))
    await cmd.write(blec.COMMAND_PAIR, blec.SUB_LTK1, bytes(
        [0x00, 0xea, 0xbd, 0x47, 0x13, 0x89, 0x35, 0x42, 0xc6, 0x79,
         0xee, 0x07, 0xf2, 0x53, 0x2c, 0x6c, 0x31]))
    await cmd.write(blec.COMMAND_PAIR, blec.SUB_LTK2, bytes(
        [0x00, 0x40, 0xb0, 0x8a, 0x5f, 0xcd, 0x1f, 0x9b, 0x41, 0x12,
         0x5c, 0xac, 0xc6, 0x3f, 0x38, 0xa0, 0x73]))
    await cmd.write(blec.COMMAND_PAIR, blec.SUB_FINISH, b"\0")


async def _heartbeat(counter):
    """Print a periodic alive/throughput line, like the USB bridge does."""
    last = 0
    while True:
        await asyncio.sleep(5.0)
        n = counter["n"]
        print(f"[ble-bridge] live: {(n - last) / 5.0:5.0f} reports/s ({n} total)")
        last = n


async def _wait_disconnect_or_stop(disconnected, stop_when):
    """Return when the controller disconnects, or (auto mode) when USB appears."""
    while not disconnected.is_set():
        if stop_when and stop_when():
            return
        try:
            await asyncio.wait_for(disconnected.wait(), timeout=0.5)
        except asyncio.TimeoutError:
            pass


async def run(stop_when=None):
    print("[ble-bridge] creating virtual Xbox 360 pad via ViGEmBus...")
    xi = xinput.load()
    before = xinput.connected_slots(xi)
    pad = X360Pad()
    pad.update()
    pad.enable_rumble()   # capture rumble Dolphin sends; _rumble_pump forwards it over BLE
    slot = bridge._detect_slot(xi, before)
    bridge._sync_dolphin_slot(slot)
    print("[ble-bridge] virtual Xbox 360 pad is LIVE and stays up until you close this.")
    if slot is not None:
        print(f"[ble-bridge] >>> In Dolphin, choose device  XInput/{slot}/Gamepad  <<<")
        if before:
            print(f"[ble-bridge]     (slots {sorted(before)} were already taken -- don't pick those.)")
        print("[ble-bridge]     If it's not in Dolphin's list, click REFRESH there first.")
    print("[ble-bridge] Wireless. Auto-reconnects when the controller is on. Ctrl+C to stop.\n")

    counter = {"n": 0}
    feeder = make_feeder(pad, counter)
    loop = asyncio.get_running_loop()

    def neutral():
        try:
            pad.reset()
            pad.update()
        except Exception:
            pass

    result = "quit"
    try:
        while True:
            if stop_when and stop_when():
                result = "switch"
                break
            dev, pairing = await blec.find_controller(should_stop=stop_when)
            if not dev:
                if stop_when and stop_when():
                    result = "switch"
                    break
                print("[ble-bridge] controller not seen -- still looking "
                      "(turn it on / tap a button; first time, hold sync)...")
                continue

            disconnected = asyncio.Event()
            hb = None
            rt = None
            try:
                async with BleakClient(
                    dev, timeout=20.0,
                    winrt={"use_cached_services": False},  # force fresh GATT discovery
                    disconnected_callback=lambda _c: loop.call_soon_threadsafe(disconnected.set),
                ) as client:
                    print(f"[ble-bridge] connected to {dev.address}.")
                    cmd = blec._Cmd(client)
                    await client.start_notify(blec.COMMAND_RESP_UUID, cmd.on_response)
                    if pairing:
                        try:
                            await _pair(cmd)
                            print("[ble-bridge] bonded to this PC (auto-reconnects next time).")
                        except Exception as e:
                            print(f"[ble-bridge] (pairing skipped: {type(e).__name__})")
                    await client.start_notify(blec.INPUT_REPORT_UUID, feeder)
                    print("[ble-bridge] >>> WIRELESS INPUT LIVE -- translating to Xbox 360 pad. <<<")
                    hb = asyncio.create_task(_heartbeat(counter))
                    rt = asyncio.create_task(_rumble_pump(client, pad))
                    await _wait_disconnect_or_stop(disconnected, stop_when)
                if stop_when and stop_when():
                    result = "switch"
                    break
                print("[ble-bridge] controller disconnected -- holding the pad, reconnecting...")
            except Exception as e:
                print(f"[ble-bridge] connection error ({type(e).__name__}: {e}) -- retrying...")
                if "Characteristic" in str(e) or "CharacteristicNotFound" in type(e).__name__:
                    print("[ble-bridge]   TIP: Steam (which now detects the Switch 2 Pro) is "
                          "probably holding the controller's Bluetooth. CLOSE STEAM and retry.")
            finally:
                for t in (hb, rt):
                    if t:
                        t.cancel()
                neutral()
            await asyncio.sleep(0.5)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[ble-bridge] stopping (Ctrl+C).")
        result = "quit"
    finally:
        neutral()
        try:
            pad.close()
        except Exception:
            pass
        print("[ble-bridge] virtual pad removed.")
    return result


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
