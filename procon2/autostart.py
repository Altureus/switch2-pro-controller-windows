#!/usr/bin/env python3
r"""
autostart.py -- run the bridge automatically at login (Windows).

Creates a shortcut in your user **Startup** folder that launches the bridge
*silently* (via `pythonw.exe`, no console window) every time you log in -- so the
controller just works without opening a .bat. Per-user, no admin required.

  python autostart.py install     # start the bridge at login (silent)
  python autostart.py uninstall   # stop starting it at login
  python autostart.py status      # is it installed / running right now?
  python autostart.py stop        # stop a currently-running (hidden) bridge

Or use the root launchers: "Install Autostart.bat", "Uninstall Autostart.bat",
"Stop Bridge.bat".
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(HERE, "bridge.py")
LNK_NAME = "Switch 2 Pro Bridge.lnk"


def _pythonw():
    """The windowless interpreter next to the current Python (fallback: python)."""
    cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return cand if os.path.isfile(cand) else sys.executable


def _startup_dir():
    return os.path.join(os.environ["APPDATA"], "Microsoft", "Windows",
                        "Start Menu", "Programs", "Startup")


def _lnk_path():
    return os.path.join(_startup_dir(), LNK_NAME)


def _q(s):
    """Escape a value for a single-quoted PowerShell string literal."""
    return s.replace("'", "''")


def _powershell(command):
    return subprocess.run(["powershell", "-NoProfile", "-Command", command],
                          capture_output=True, text=True)


def install():
    pyw, lnk = _pythonw(), _lnk_path()
    ps = (
        "$w = New-Object -ComObject WScript.Shell; "
        f"$s = $w.CreateShortcut('{_q(lnk)}'); "
        f"$s.TargetPath = '{_q(pyw)}'; "
        f"$s.Arguments = '\"{_q(BRIDGE)}\"'; "
        f"$s.WorkingDirectory = '{_q(HERE)}'; "
        "$s.Description = 'Switch 2 Pro Controller bridge (autostart)'; "
        "$s.Save()"
    )
    r = _powershell(ps)
    if r.returncode != 0:
        print("[autostart] failed to create the shortcut:")
        print(r.stderr.strip())
        return
    print(f"[autostart] installed -> {lnk}")
    print("[autostart] the bridge will now start SILENTLY at every login (no window).")
    print("[autostart] stop it now:  python autostart.py stop   |  remove:  uninstall")


def uninstall():
    try:
        os.remove(_lnk_path())
        print(f"[autostart] removed the login entry ({_lnk_path()}).")
    except FileNotFoundError:
        print("[autostart] not installed (nothing to remove).")


def _running_pids():
    r = _powershell(
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or Name='python.exe'\""
        " | Where-Object { $_.CommandLine -like '*bridge.py*' }"
        " | ForEach-Object { $_.ProcessId }")
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def stop():
    pids = _running_pids()
    if not pids:
        print("[autostart] no running bridge found.")
        return
    for pid in pids:
        _powershell(f"Stop-Process -Id {pid} -Force")
    print(f"[autostart] stopped bridge (pid {', '.join(map(str, pids))}).")


def status():
    pids = _running_pids()
    print(f"[autostart] runs at login : {os.path.isfile(_lnk_path())}")
    print(f"[autostart] running now   : {bool(pids)}"
          + (f"  (pid {', '.join(map(str, pids))})" if pids else ""))


if __name__ == "__main__":
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "install"
    {"install": install, "uninstall": uninstall,
     "stop": stop, "status": status}.get(cmd, install)()
