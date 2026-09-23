"""The customization window: General / Appearance / About."""
from __future__ import annotations

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFontComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, AUTHOR, REPO_URL, VERSION, data_dir
from themes import ACCENT, app_icon
from widgets import ColorChip, SwatchRow, ToggleSwitch

DIALOG_QSS = """
QDialog { background: #15171C; }
QLabel { color: #E7E9EE; font-size: 13px; background: transparent; }
QFrame#sidebar { background: #101216; border-right: 1px solid #23262E; }
QLabel#brand { font-size: 22px; font-weight: 800; letter-spacing: 2px; color: #FFFFFF; }
QLabel#brandSub { color: #8A90A0; font-size: 12px; }
QListWidget#nav { background: transparent; border: none; outline: none; font-size: 14px; }
QListWidget#nav::item { color: #A9AFBD; padding: 11px 14px; border-radius: 10px; margin: 2px 0; }
QListWidget#nav::item:hover { background: #1A1D24; color: #FFFFFF; }
QListWidget#nav::item:selected { background: #232838; color: #FFFFFF; }
QLabel#pageTitle { font-size: 24px; font-weight: 700; color: #FFFFFF; }
QLabel#pageSub { color: #8A90A0; font-size: 13px; }
QLabel#groupTitle { color: #8A90A0; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; }
QFrame#group { background: #1B1E25; border: 1px solid #262A33; border-radius: 14px; }
QLabel#rowTitle { font-weight: 600; color: #EDEFF4; font-size: 13px; }
QLabel#rowSub { color: #8A90A0; font-size: 12px; }
QLabel#value { color: #B8BECC; font-size: 12px; }
QFrame#sep { background: #262A33; border: none; min-height: 1px; max-height: 1px; }
QSlider::groove:horizontal { height: 4px; background: #2C303A; border-radius: 2px; }
QSlider::sub-page:horizontal { background: ACCENT; border-radius: 2px; }
QSlider::handle:horizontal { background: #FFFFFF; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
QSpinBox, QFontComboBox { background: #23262E; border: 1px solid #2E323C; border-radius: 8px;
                          padding: 5px 10px; color: #E7E9EE; min-height: 22px; min-width: 90px; }
QSpinBox:focus, QFontComboBox:focus { border: 1px solid ACCENT; }
QFontComboBox { min-width: 190px; }
QComboBox QAbstractItemView { background: #1B1E25; color: #E7E9EE; border: 1px solid #2E323C;
                              selection-background-color: #2B3040; outline: none; }
QPushButton { background: #23262E; color: #E7E9EE; border: 1px solid #2E323C; border-radius: 9px;
              padding: 9px 18px; font-weight: 600; font-size: 13px; }
QPushButton:hover { background: #2A2E38; }
QPushButton#primary { background: ACCENT; color: #0E1016; border: none; }
QPushButton#primary:hover { background: #93AEFF; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2E323C; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #3A3F4B; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
""".replace("ACCENT", ACCENT)


class SettingsDialog(QDialog):
    apply_to_all = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.s = settings
        self._setters: dict = {}
        self._text_chip: ColorChip | None = None
        self.setWindowTitle(f"{APP_NAME} — Settings")
        self.setWindowIcon(app_icon())
        self.resize(800, 640)
        self.setMinimumSize(720, 540)
        self.setStyleSheet(DIALOG_QSS)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- sidebar
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(210)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(20, 26, 14, 18)
        brand = QLabel("JXT")
        brand.setObjectName("brand")
        sub = QLabel("Sticky Notes")
        sub.setObjectName("brandSub")
        sl.addWidget(brand)
        sl.addWidget(sub)
        sl.addSpacing(22)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for name in ("General", "Appearance", "About"):
            self.nav.addItem(name)
        sl.addWidget(self.nav, 1)
        ver = QLabel(f"v{VERSION}")
        ver.setObjectName("brandSub")
        sl.addWidget(ver)
        root.addWidget(side)

        # ---- content
        right = QVBoxLayout()
        right.setContentsMargins(30, 26, 30, 20)
        right.setSpacing(14)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._general_page())
        self.stack.addWidget(self._appearance_page())
        self.stack.addWidget(self._about_page())
        right.addWidget(self.stack, 1)

        foot = QHBoxLayout()
        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._reset)
        self.apply_btn = QPushButton("Apply style to all notes")
        self.apply_btn.setToolTip("Clear per-note colors, transparency and text size so every note follows these defaults.")
        self.apply_btn.clicked.connect(self._apply_all)
        done = QPushButton("Done")
        done.setObjectName("primary")
        done.clicked.connect(self.accept)
        foot.addWidget(reset)
        foot.addStretch(1)
        foot.addWidget(self.apply_btn)
        foot.addWidget(done)
        right.addLayout(foot)
        root.addLayout(right, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self._sync_enabled()

    # ------------------------------------------------------------ builders
    def _page(self, title: str, subtitle: str):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(10)
        t = QLabel(title)
        t.setObjectName("pageTitle")
        st = QLabel(subtitle)
        st.setObjectName("pageSub")
        lay.addWidget(t)
        lay.addWidget(st)
        lay.addSpacing(8)
        scroll.setWidget(body)
        return scroll, lay

    def _group(self, parent_lay: QVBoxLayout, title: str) -> QVBoxLayout:
        lbl = QLabel(title.upper())
        lbl.setObjectName("groupTitle")
        parent_lay.addSpacing(6)
        parent_lay.addWidget(lbl)
        frame = QFrame()
        frame.setObjectName("group")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        parent_lay.addWidget(frame)
        return lay

    def _row(self, lay: QVBoxLayout, title: str, sub: str, control: QWidget | None = None) -> None:
        if lay.count():
            sep = QFrame()
            sep.setObjectName("sep")
            lay.addWidget(sep)
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(18, 13, 18, 13)
        l.setSpacing(16)
        col = QVBoxLayout()
        col.setSpacing(2)
        a = QLabel(title)
        a.setObjectName("rowTitle")
        col.addWidget(a)
        if sub:
            b = QLabel(sub)
            b.setObjectName("rowSub")
            b.setWordWrap(True)
            col.addWidget(b)
        l.addLayout(col, 1)
        if control is not None:
            l.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(w)

    def _toggle(self, lay, key, title, sub, after=None) -> None:
        t = ToggleSwitch(bool(self.s[key]))

        def changed(v):
            self.s.update(**{key: v})
            if after:
                after()

        t.toggled.connect(changed)
        self._setters[key] = t.set_silent
        self._row(lay, title, sub, t)

    def _slider(self, lay, key, title, sub, lo, hi, suffix="") -> None:
        box = QWidget()
        bl = QHBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(10)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setValue(int(self.s[key]))
        sl.setFixedWidth(190)
        val = QLabel(f"{sl.value()}{suffix}")
        val.setObjectName("value")
        val.setFixedWidth(56)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        def changed(v):
            val.setText(f"{v}{suffix}")
            self.s.update(**{key: v})

        def setter(v):
            sl.blockSignals(True)
            sl.setValue(int(v))
            sl.blockSignals(False)
            val.setText(f"{int(v)}{suffix}")

        sl.valueChanged.connect(changed)
        self._setters[key] = setter
        bl.addWidget(sl)
        bl.addWidget(val)
        self._row(lay, title, sub, box)

    def _spin(self, lay, key, title, sub, lo, hi, suffix=" px") -> None:
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setSuffix(suffix)
        sp.setValue(int(self.s[key]))
        sp.valueChanged.connect(lambda v: self.s.update(**{key: v}))

        def setter(v):
            sp.blockSignals(True)
            sp.setValue(int(v))
            sp.blockSignals(False)

        self._setters[key] = setter
        self._row(lay, title, sub, sp)

    # --------------------------------------------------------------- pages
    def _general_page(self) -> QWidget:
        page, lay = self._page("General", "Startup and everyday behavior.")
        g = self._group(lay, "Startup")
        self._toggle(g, "start_with_windows", "Start with Windows",
                     "Launch JXT Sticky Notes automatically when you sign in.")
        self._toggle(g, "start_in_tray", "Start minimized to tray",
                     "When launched by Windows, stay in the system tray until you open your notes.")
        g = self._group(lay, "Behavior")
        self._toggle(g, "always_on_top", "Keep notes on top of other windows",
                     "Applies to all notes right now. You can still pin or unpin any single note.")
        self._toggle(g, "hover_controls", "Show note controls only on hover",
                     "Keeps notes clean and minimal until your mouse is over them.")
        self._toggle(g, "confirm_delete", "Confirm before deleting a note",
                     "Empty notes are always deleted instantly.")
        lay.addStretch(1)
        return page

    def _appearance_page(self) -> QWidget:
        page, lay = self._page("Appearance", "Changes apply live to every note.")

        g = self._group(lay, "Colors")
        # default color row (swatches + custom chip)
        self._swatches = SwatchRow(self.s["default_color"])
        chip = ColorChip(self.s["default_color"])

        def set_default(c: str) -> None:
            self.s.update(default_color=c)
            self._swatches.set_current(c)
            chip.set_color(c)

        self._swatches.picked.connect(set_default)
        chip.picked.connect(set_default)
        self._row(g, "Default note color", "Used by every note that hasn't been given its own color.")
        g.itemAt(g.count() - 1).widget().layout().addWidget(chip, 0, Qt.AlignRight | Qt.AlignVCenter)
        # swatches on their own line
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(14, 0, 14, 12)
        wl.addWidget(self._swatches)
        wl.addStretch(1)
        g.addWidget(wrap)

        def sync_default(_=None):
            c = self.s["default_color"]
            self._swatches.set_current(c)
            chip.set_color(c)

        self._setters["default_color"] = sync_default

        self._toggle(g, "auto_text", "Auto text contrast",
                     "Automatically choose light or dark text for readability.", after=self._sync_enabled)
        self._text_chip = ColorChip(self.s["text_color"])
        self._text_chip.picked.connect(lambda c: self.s.update(text_color=c))
        self._setters["text_color"] = self._text_chip.set_color
        self._row(g, "Custom text color", "Only used when auto contrast is off.", self._text_chip)

        g = self._group(lay, "Typography")
        combo = QFontComboBox()
        combo.setCurrentFont(QFont(self.s["font_family"]))
        combo.currentFontChanged.connect(lambda f: self.s.update(font_family=f.family()))

        def set_font(v):
            combo.blockSignals(True)
            combo.setCurrentFont(QFont(v))
            combo.blockSignals(False)

        self._setters["font_family"] = set_font
        self._row(g, "Font", "Any font installed on your PC.", combo)
        self._slider(g, "font_size", "Text size", "Default size for new and existing notes.", 8, 32, " pt")

        g = self._group(lay, "Surface")
        self._slider(g, "opacity", "Note opacity", "Lower values give a frosted, see-through look.", 30, 100, "%")
        self._slider(g, "corner_radius", "Corner roundness", "From sharp paper edges to soft pill shapes.", 0, 32, " px")
        self._toggle(g, "shadow", "Drop shadow", "A soft shadow that lifts notes off the desktop.")

        g = self._group(lay, "New notes")
        self._spin(g, "note_width", "Default width", "Size of newly created notes.", 180, 900)
        self._spin(g, "note_height", "Default height", "", 120, 900)
        lay.addStretch(1)
        return page

    def _about_page(self) -> QWidget:
        page, lay = self._page("About", f"{APP_NAME} · a clean, customizable sticky notes app for Windows.")
        g = self._group(lay, "Info")
        self._row(g, "Version", VERSION)
        self._row(g, "Author", AUTHOR)
        self._row(g, "License", "MIT License — free to use, modify and share.")
        link = QLabel(f'<a style="color:{ACCENT}" href="{REPO_URL}">{REPO_URL}</a>')
        link.setOpenExternalLinks(True)
        self._row(g, "Source code", "", link)
        folder = QPushButton("Open data folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        self._row(g, "Your notes are stored locally", str(data_dir()), folder)

        g = self._group(lay, "Shortcuts")
        for keys, what in (
            ("Ctrl + N", "New note"),
            ("Ctrl + B / I", "Bold / italic"),
            ("Ctrl + Shift + X", "Strikethrough"),
            ("Ctrl + Shift + L", "Bulleted list"),
            ("Double-click title bar", "Collapse / expand a note"),
        ):
            self._row(g, what, "", QLabel(keys))
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------- actions
    def _sync_enabled(self) -> None:
        if self._text_chip is not None:
            self._text_chip.setEnabled(not self.s["auto_text"])

    def _reset(self) -> None:
        self.s.reset()
        for key, setter in self._setters.items():
            setter(self.s[key])
        self._sync_enabled()

    def _apply_all(self) -> None:
        self.apply_to_all.emit()
        self.apply_btn.setText("Applied ✓")
        QTimer.singleShot(1600, lambda: self.apply_btn.setText("Apply style to all notes"))
