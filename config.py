"""Constants, paths and persistent settings for JXT Sticky Notes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

APP_NAME = "JXT Sticky Notes"
APP_ID = "JXTStickyNotes"
VERSION = "1.0.0"
AUTHOR = "Jxt Sidhu"
REPO_URL = "https://github.com/jxtsidhu/JXT-Sticky-Notes"

DEFAULTS: dict = {
    # General
    "start_with_windows": True,
    "start_in_tray": True,
    "always_on_top": False,
    "hover_controls": True,
    "confirm_delete": True,
    # Appearance
    "default_color": "#FFF1A8",
    "auto_text": True,
    "text_color": "#23262B",
    "font_family": "Segoe UI",
    "font_size": 12,
    "opacity": 100,
    "corner_radius": 14,
    "shadow": True,
    "note_width": 300,
    "note_height": 320,
}


def data_dir() -> Path:
    """Folder where settings and notes are stored (%APPDATA%\\JXTStickyNotes on Windows)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    folder = base / APP_ID
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def write_json_atomic(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class Settings(QObject):
    """Dict-like settings object that saves itself and notifies listeners."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._path = data_dir() / "settings.json"
        self.first_run = not self._path.exists()
        self._data = dict(DEFAULTS)
        saved = read_json(self._path, {})
        if isinstance(saved, dict):
            self._data.update({k: v for k, v in saved.items() if k in DEFAULTS})
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.flush)

    def __getitem__(self, key: str):
        return self._data[key]

    def update(self, **values) -> None:
        self._data.update(values)
        self._timer.start()
        self.changed.emit()

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self._timer.start()
        self.changed.emit()

    def flush(self) -> None:
        try:
            write_json_atomic(self._path, self._data)
        except OSError:
            pass
