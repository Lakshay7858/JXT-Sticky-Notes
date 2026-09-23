"""Application controller: notes, system tray, single-instance handling."""
from __future__ import annotations

import copy
import ctypes
import datetime
import faulthandler
import sys
import traceback

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

import autostart
from config import APP_NAME, APP_ID, Settings, data_dir, read_json, write_json_atomic
from note_window import NoteWindow, new_note_data
from settings_dialog import SettingsDialog
from themes import MENU_QSS, app_icon

SERVER_NAME = f"{APP_ID}.single-instance"

WELCOME = (
    "<p><b>Welcome to JXT Sticky Notes</b> 👋</p>"
    "<ul>"
    "<li>Drag the top bar to move a note</li>"
    "<li>Hover a note to reveal its controls</li>"
    "<li><b>+</b> adds a note, <b>📌</b> keeps it on top</li>"
    "<li><b>⋯</b> opens colors, transparency &amp; more</li>"
    "<li>Double-click the top bar to collapse</li>"
    "<li>Everything else lives in <i>Settings</i> (tray icon)</li>"
    "</ul>"
    "<p>Delete this note whenever you like.</p>"
)


class Controller(QObject):
    def __init__(self, settings: Settings, start_hidden: bool):
        super().__init__()
        self.s = settings
        self.notes: list[NoteWindow] = []
        self.dialog: SettingsDialog | None = None
        self.visible = not start_hidden
        self._path = data_dir() / "notes.json"
        self._last_top = settings["always_on_top"]
        self._last_auto = settings["start_with_windows"]

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(600)
        self._save_timer.timeout.connect(self.save_now)

        self._build_tray()
        self._load_notes()
        settings.changed.connect(self._on_settings)

    # ---------------------------------------------------------------- tray
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        self.menu = QMenu()
        self.menu.setStyleSheet(MENU_QSS)
        self.menu.addAction("New note", self.new_note)
        self.toggle_act = self.menu.addAction("Hide notes", self.toggle_all)
        self.menu.addAction("Bring all notes to front", self.bring_to_front)
        self.menu.addSeparator()
        self.menu.addAction("Settings…", self.open_settings)
        self.auto_act = QAction("Start with Windows", self.menu)
        self.auto_act.setCheckable(True)
        self.auto_act.setChecked(bool(self.s["start_with_windows"]))
        self.auto_act.triggered.connect(lambda v: self.s.update(start_with_windows=bool(v)))
        self.menu.addAction(self.auto_act)
        self.menu.addSeparator()
        self.menu.addAction("Quit", QApplication.instance().quit)
        self.menu.aboutToShow.connect(
            lambda: self.toggle_act.setText("Hide notes" if self.visible else "Show notes"))
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(
            lambda reason: self.toggle_all() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    # --------------------------------------------------------------- notes
    def _load_notes(self) -> None:
        raw = read_json(self._path, None)
        items = raw.get("notes", []) if isinstance(raw, dict) else []
        for item in items:
            if isinstance(item, dict):
                data = new_note_data(self.s)
                data.update({k: v for k, v in item.items() if k in data})
                self._add(data)
        if not items and not self._path.exists():
            data = new_note_data(self.s, text=WELCOME)
            data["x"], data["y"] = self._next_pos(data["w"], data["h"])
            self._add(data)
            self.save_now()

    def _next_pos(self, w: int, h: int) -> tuple[int, int]:
        g = QGuiApplication.primaryScreen().availableGeometry()
        if self.notes:
            last = self.notes[-1]
            x, y = last.x() + 34, last.y() + 34
        else:
            x, y = g.right() - w - 48, g.top() + 64
        if x + w > g.right() or y + h > g.bottom():
            x, y = g.left() + 64 + (len(self.notes) * 12) % 140, g.top() + 64
        return x, y

    def _add(self, data: dict) -> NoteWindow:
        w = NoteWindow(data, self.s)
        w.changed.connect(self.save_soon)
        w.new_requested.connect(self.new_note)
        w.delete_requested.connect(self.delete_note)
        w.duplicate_requested.connect(self.duplicate_note)
        self.notes.append(w)
        if self.visible:
            w.show()
        return w

    def new_note(self) -> None:
        if not self.visible:
            self.show_all()
        data = new_note_data(self.s)
        data["x"], data["y"] = self._next_pos(data["w"], data["h"])
        self._add(data).focus_editor()
        self.save_soon()

    def duplicate_note(self, src: NoteWindow) -> None:
        data = copy.deepcopy(src.snapshot())
        data["id"] = new_note_data(self.s)["id"]
        data["x"], data["y"] = src.x() + 34, src.y() + 34
        data["collapsed"] = False
        self._add(data).focus_editor()
        self.save_soon()

    def delete_note(self, w: NoteWindow) -> None:
        if self.s["confirm_delete"] and w.editor.toPlainText().strip():
            box = QMessageBox(w)
            box.setIcon(QMessageBox.Question)
            box.setWindowTitle("Delete note")
            box.setText("Delete this note?")
            box.setInformativeText("This can't be undone.")
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            box.setDefaultButton(QMessageBox.Cancel)
            if box.exec() != QMessageBox.Yes:
                return
        if w in self.notes:
            self.notes.remove(w)
        w.hide()
        w.deleteLater()
        self.save_soon()

    def show_all(self) -> None:
        self.visible = True
        for w in self.notes:
            w.show()
            w.raise_()

    def hide_all(self) -> None:
        self.visible = False
        for w in self.notes:
            w.hide()

    def toggle_all(self) -> None:
        if self.visible and any(w.isVisible() for w in self.notes):
            self.hide_all()
        else:
            self.show_all()
            if not self.notes:
                self.new_note()

    def bring_to_front(self) -> None:
        self.show_all()
        for w in self.notes:
            w.raise_()
            w.activateWindow()

    # ----------------------------------------------------------- persistence
    def save_soon(self) -> None:
        self._save_timer.start()

    def save_now(self) -> None:
        try:
            write_json_atomic(self._path, {"version": 1, "notes": [w.snapshot() for w in self.notes]})
        except OSError:
            pass
        self.s.flush()

    # -------------------------------------------------------------- settings
    def open_settings(self) -> None:
        if self.dialog is None:
            self.dialog = SettingsDialog(self.s)
            self.dialog.apply_to_all.connect(self._clear_overrides)
            self.dialog.finished.connect(lambda _: setattr(self, "dialog", None))
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _clear_overrides(self) -> None:
        for w in self.notes:
            w.clear_overrides()

    def _on_settings(self) -> None:
        s = self.s
        if s["start_with_windows"] != self._last_auto:
            self._last_auto = s["start_with_windows"]
            autostart.set_enabled(bool(self._last_auto))
        if s["always_on_top"] != self._last_top:
            self._last_top = s["always_on_top"]
            for w in self.notes:
                w.set_on_top(bool(self._last_top))
        self.auto_act.setChecked(bool(s["start_with_windows"]))
        for w in self.notes:
            w.apply_style()


def _notify_running_instance() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if sock.waitForConnected(400):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(400)
        sock.disconnectFromServer()
        return True
    return False


_LOG = None


def _setup_logging() -> None:
    """Write crashes to %APPDATA%\\JXTStickyNotes\\error.log (windowed exes have no console)."""
    global _LOG
    try:
        _LOG = open(data_dir() / "error.log", "a", buffering=1, encoding="utf-8")
        _LOG.write(f"\n--- start {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
        faulthandler.enable(file=_LOG)
    except OSError:
        return

    def hook(kind, value, tb):
        traceback.print_exception(kind, value, tb, file=_LOG)

    sys.excepthook = hook


def _fatal(message: str) -> None:
    if _LOG:
        _LOG.write(message + "\n")
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(
                0, f"{message}\n\nDetails: %APPDATA%\\{APP_ID}\\error.log", APP_NAME, 0x10)
        except Exception:
            pass


def run(argv: list[str] | None = None) -> int:
    _setup_logging()
    try:
        return _run(argv)
    except Exception:
        _fatal("JXT Sticky Notes crashed on startup:\n" + traceback.format_exc())
        return 1


def _run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JXT.StickyNotes.1")
        except Exception:
            pass
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("JXT")
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)

    if _notify_running_instance():
        return 0
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)

    settings = Settings()
    start_hidden = "--minimized" in argv and bool(settings["start_in_tray"])
    controller = Controller(settings, start_hidden)

    def on_connection() -> None:
        sock = server.nextPendingConnection()
        if sock is not None:
            sock.close()
        controller.show_all()

    server.newConnection.connect(on_connection)
    app.aboutToQuit.connect(controller.save_now)

    # Keep the registry entry pointing at the current exe location.
    if settings.first_run or settings["start_with_windows"]:
        autostart.set_enabled(bool(settings["start_with_windows"]))
    settings.flush()

    return app.exec()
