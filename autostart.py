"""Start-with-Windows support (per-user registry Run key, no admin rights needed)."""
from __future__ import annotations

import sys
from pathlib import Path

try:  # only available on Windows
    import winreg
except ImportError:  # pragma: no cover
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "JXTStickyNotes"


def _command() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller exe
        return f'"{sys.executable}" --minimized'
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")  # no console window
    exe = pyw if pyw.exists() else py
    script = Path(sys.argv[0]).resolve()
    return f'"{exe}" "{script}" --minimized'


def is_supported() -> bool:
    return winreg is not None


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Add or remove the startup entry. Returns True on success."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
