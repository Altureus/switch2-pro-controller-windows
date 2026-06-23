#!/usr/bin/env python3
r"""
gui.py -- a simple control panel for the Switch 2 Pro Controller bridge.

One window with everything: pick Auto / USB / Bluetooth, Start & Stop the bridge,
toggle autostart-at-login, install ViGEmBus, and watch the live log. Pure tkinter
(ships with Python -- no extra packages).

The bridge runs as a child process (launch.py); Stop ends it and the virtual pad
is removed automatically when that process exits.

Run:  pythonw gui.py     (or double-click "Switch 2 Pro.bat")
"""
import ctypes
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import autostart  # noqa: E402

LAUNCH = os.path.join(HERE, "launch.py")
_CREATE_NO_WINDOW = 0x08000000


def _python():
    """Prefer python.exe (so child stdout streams) even if we're under pythonw."""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.isfile(cand):
            return cand
    return exe


def _vigembus_installer():
    d = os.path.join(ROOT, "drivers")
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().startswith("vigembus") and f.lower().endswith(".exe"):
                return os.path.join(d, f)
    return None


def _icon_path():
    """The window/app icon (.ico), in the repo root or a frozen (PyInstaller) bundle."""
    for base in (getattr(sys, "_MEIPASS", None), ROOT, HERE):
        if base:
            p = os.path.join(base, "Switch2ProController.ico")
            if os.path.isfile(p):
                return p
    return None


# ---- remember window size + position --------------------------------------
def _state_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Switch2ProBridge", "window.txt")


def _on_screen(w, h, x, y):
    """True if the window's title bar would be visible on the (multi-monitor) desktop."""
    try:
        u = ctypes.windll.user32
        vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)   # X/Y of virtual screen
        vw, vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)   # width/height of virtual screen
    except Exception:
        return True
    return (x + w > vx + 80 and x < vx + vw - 80
            and y + 30 > vy and y < vy + vh - 40)


def _restore_geometry(root):
    try:
        with open(_state_path(), encoding="utf-8") as f:
            geo = f.read().strip()
    except Exception:
        return
    m = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", geo)
    if not m:
        return
    w, h, x, y = (int(m.group(i)) for i in range(1, 5))
    try:
        root.geometry(geo if _on_screen(w, h, x, y) else f"{w}x{h}")
    except Exception:
        pass


def _save_geometry(root):
    try:
        geo = root.geometry()
        m = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", geo)
        if not m or int(m.group(1)) < 200 or int(m.group(2)) < 200:
            return  # don't persist a degenerate/minimized size
        p = _state_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(geo)
    except Exception:
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.proc = None
        root.title("Switch 2 Pro Controller")
        _ico = _icon_path()
        if _ico:
            try:
                root.iconbitmap(default=_ico)
            except Exception:
                pass
        root.minsize(480, 440)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        frm = ttk.Frame(root, padding=12)
        frm.grid(sticky="nsew")
        frm.columnconfigure(0, weight=1)   # content column stretches horizontally
        frm.rowconfigure(10, weight=1)     # the log row stretches vertically

        ttk.Label(frm, text="Switch 2 Pro Controller  →  Xbox 360 pad",
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=4, sticky="w")

        # Start + live status, side by side at the top (above Connection)
        top = ttk.Frame(frm)
        top.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.btn = ttk.Button(top, text="Start", command=self.toggle, width=12)
        self.btn.grid(row=0, column=0)
        self.status = ttk.Label(top, text="● Stopped", foreground="gray")
        self.status.grid(row=0, column=1, padx=(12, 0))

        ttk.Label(frm, text="Connection:").grid(row=2, column=0, sticky="w", pady=(12, 0))

        # transport choices (under Connection)
        self.mode = tk.StringVar(value="auto")
        modes = ttk.Frame(frm)
        modes.grid(row=3, column=0, columnspan=4, sticky="w", padx=(20, 0), pady=(2, 0))
        for i, (val, lbl) in enumerate(
                [("auto", "Auto (USB or Bluetooth)"), ("usb", "USB only"), ("bluetooth", "Bluetooth only")]):
            ttk.Radiobutton(modes, text=lbl, value=val, variable=self.mode).grid(row=0, column=i, padx=(0, 12))

        self.debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Debug output (show parsed controller state)",
                        variable=self.debug).grid(row=4, column=0, columnspan=4, sticky="w", pady=(6, 0))

        self.autostart_var = tk.BooleanVar(value=os.path.isfile(autostart._lnk_path()))
        ttk.Checkbutton(frm, text="Start automatically at login (runs silently in the background)",
                        variable=self.autostart_var, command=self.toggle_autostart).grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(2, 0))

        self.device = ttk.Label(frm, text="Dolphin device:  —", foreground="#555")
        self.device.grid(row=6, column=0, columnspan=4, sticky="w", pady=(6, 0))

        ttk.Separator(frm, orient="horizontal").grid(
            row=7, column=0, columnspan=4, sticky="ew", pady=10)

        util = ttk.Frame(frm)
        util.grid(row=8, column=0, columnspan=4, sticky="w")
        self.vigem_btn = ttk.Button(util, text="Install ViGEmBus driver", command=self.install_vigembus)
        self.vigem_btn.grid(row=0, column=0, padx=(0, 6))
        if not _vigembus_installer():
            self.vigem_btn.state(["disabled"])

        ttk.Label(frm, text="Log:").grid(row=9, column=0, sticky="w", pady=(10, 2))
        self.log = tk.Text(frm, width=74, height=14, wrap="word", state="disabled",
                           font=("Consolas", 9), background="#101418",
                           foreground="#d6e2ee", relief="flat")
        self.log.grid(row=10, column=0, columnspan=3, sticky="nsew")
        sb = ttk.Scrollbar(frm, command=self.log.yview)
        sb.grid(row=10, column=3, sticky="ns")
        self.log["yscrollcommand"] = sb.set

        root.protocol("WM_DELETE_WINDOW", self.on_close)

        try:
            if autostart._running_pids():
                self._append("[gui] Note: a bridge already appears to be running (autostart?). "
                             "Starting one here too would create a second pad.\n")
        except Exception:
            pass

        _restore_geometry(root)

    # ---- bridge process ----------------------------------------------------
    def toggle(self):
        if self.proc and self.proc.poll() is None:
            self.stop()
        else:
            self.start()

    def start(self):
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--run-bridge"]   # frozen exe relaunches itself as the bridge
        else:
            cmd = [_python(), "-u", LAUNCH]
        m = self.mode.get()
        if m == "usb":
            cmd.append("--usb")
        elif m == "bluetooth":
            cmd.append("--bluetooth")
        if self.debug.get():
            cmd.append("--debug")
        flags = _CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=HERE, creationflags=flags)
        except Exception as e:
            self._append(f"[gui] failed to start: {e}\n")
            return
        self.btn.config(text="Stop")
        self.status.config(text=f"● Running ({m})", foreground="#1a7f37")
        self.device.config(text="Dolphin device:  —")
        self._append(f"[gui] started: launch.py {' '.join(cmd[3:])}\n")
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def stop(self):
        p = self.proc
        if p and p.poll() is None:
            self._append("[gui] stopping...\n")
            try:
                p.terminate()
            except Exception:
                pass

    def _reader(self, proc):
        try:
            for line in proc.stdout:
                self.root.after(0, self._on_line, line.rstrip("\n"))
        except Exception:
            pass
        self.root.after(0, self._on_exit)

    def _on_line(self, line):
        self._append(line + "\n")
        if "XInput/" in line:
            frag = line[line.find("XInput/"):].split()[0].rstrip(".<>)")
            self.device.config(
                text=f"Dolphin device:  {frag}   (pick this, then click Refresh in Dolphin)")

    def _on_exit(self):
        self.btn.config(text="Start")
        self.status.config(text="● Stopped", foreground="gray")
        self._append("[gui] bridge stopped.\n")

    # ---- autostart ---------------------------------------------------------
    def toggle_autostart(self):
        try:
            if self.autostart_var.get():
                autostart.install()
                self._append("[gui] autostart enabled (runs the bridge silently at login).\n")
            else:
                autostart.uninstall()
                self._append("[gui] autostart disabled.\n")
        except Exception as e:
            self._append(f"[gui] autostart error: {e}\n")
        self.autostart_var.set(os.path.isfile(autostart._lnk_path()))

    # ---- utilities ---------------------------------------------------------
    def install_vigembus(self):
        inst = _vigembus_installer()
        if inst:
            self._open(inst)

    def _open(self, path):
        try:
            os.startfile(path)  # noqa: S606 (Windows: opens .bat/.exe in its own window)
        except Exception as e:
            self._append(f"[gui] could not open {os.path.basename(path)}: {e}\n")

    # ---- helpers -----------------------------------------------------------
    def _append(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")

    def on_close(self):
        _save_geometry(self.root)
        self.stop()
        self.root.after(200, self.root.destroy)


def main():
    # multi-call binary: when relaunched as the bridge runner (from the GUI's Start),
    # run the bridge instead of building the window. A frozen --windowed build has no
    # console, so reattach stdout to the inherited pipe first.
    if "--run-bridge" in sys.argv:
        if getattr(sys, "frozen", False):
            try:
                sys.stdout = os.fdopen(1, "w", buffering=1, encoding="utf-8", errors="replace")
                sys.stderr = sys.stdout
            except Exception:
                pass
        sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--run-bridge"]
        import launch
        launch.main()
        return

    root = tk.Tk()
    selftest = "--selftest" in sys.argv
    if selftest:
        root.withdraw()
    App(root)
    if selftest:
        root.update()
        root.destroy()
        print("gui selftest OK")
        return
    root.mainloop()


if __name__ == "__main__":
    main()
