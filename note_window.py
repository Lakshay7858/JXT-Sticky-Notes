"""A single sticky note: frameless, draggable, resizable, fully themeable."""
from __future__ import annotations

import re
import uuid

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QActionGroup,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QShortcut,
    QTextCharFormat,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizeGrip,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from config import APP_NAME
from themes import MENU_QSS, auto_text, is_dark, rgba
from widgets import IconButton, SwatchRow

M = 12  # transparent margin around the card (room for the shadow)
HEADER_H = 36
MIN_W, MIN_H = 220, 150


def new_note_data(settings, x=None, y=None, text: str = "") -> dict:
    return {
        "id": uuid.uuid4().hex,
        "text": text,
        "x": x,
        "y": y,
        "w": int(settings["note_width"]) + 2 * M,
        "h": int(settings["note_height"]) + 2 * M,
        "color": None,  # None = follow the default color from Settings
        "on_top": bool(settings["always_on_top"]),
        "opacity": None,  # None = follow Settings
        "font_size": None,  # None = follow Settings
        "collapsed": False,
    }


class Card(QFrame):
    """The note surface. Painted by hand so color/opacity changes always repaint fully."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bg = QColor("#FFF1A8")
        self.border = QColor(0, 0, 0, 22)
        self.radius = 14

    def set_look(self, bg: QColor, border: QColor, radius: int) -> None:
        self.bg, self.border, self.radius = bg, border, radius
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(self.border, 1))
        p.setBrush(self.bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self.radius, self.radius)


class HeaderBar(QWidget):
    """Top bar: drag to move, double-click to collapse."""

    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag: QPoint | None = None
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit()


class Grip(QSizeGrip):
    """Subtle resize handle in the bottom-right corner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = QColor("#000000")
        self.shown = True
        self.setFixedSize(18, 18)

    def paintEvent(self, _):
        if not self.shown:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self.color)
        c.setAlpha(110)
        p.setPen(QPen(c, 1.4, Qt.SolidLine, Qt.RoundCap))
        w, h = self.width(), self.height()
        for i in (5, 9, 13):
            p.drawLine(QPointF(w - i, h - 2.5), QPointF(w - 2.5, h - i))


class NoteWindow(QWidget):
    changed = Signal()
    new_requested = Signal()
    delete_requested = Signal(object)
    duplicate_requested = Signal(object)

    def __init__(self, data: dict, settings):
        super().__init__()
        self.data = data
        self.s = settings
        self._hover = False
        self._title_text = ""
        self._expanded_h = int(data["h"])

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(MIN_W, MIN_H)
        flags = Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint
        if data["on_top"]:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        self._build()
        self.resize(int(data["w"]), int(data["h"]))
        if data["x"] is not None and data["y"] is not None:
            self.move(int(data["x"]), int(data["y"]))
            self.ensure_on_screen()

        self.editor.blockSignals(True)
        if data.get("text"):
            self.editor.setHtml(data["text"])
        self.editor.blockSignals(False)
        self._refresh_title()
        self.set_collapsed(bool(data["collapsed"]), init=True)
        self.apply_style()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        self.card = Card(self)
        self.card.setObjectName("card")
        self.shadow = QGraphicsDropShadowEffect(self.card)
        self.shadow.setBlurRadius(26)
        self.shadow.setOffset(0, 5)
        self.shadow.setColor(QColor(0, 0, 0, 90))
        self.card.setGraphicsEffect(self.shadow)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(M, M, M, M)
        outer.addWidget(self.card)

        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.header = HeaderBar()
        self.header.setFixedHeight(HEADER_H)
        self.header.double_clicked.connect(lambda: self.set_collapsed(not self.data["collapsed"]))
        h = QHBoxLayout(self.header)
        h.setContentsMargins(8, 6, 8, 0)
        h.setSpacing(2)
        self.btn_new = IconButton("plus", "New note (Ctrl+N)")
        self.btn_pin = IconButton("pin", "Keep on top")
        self.btn_menu = IconButton("menu", "More options")
        self.btn_close = IconButton("close", "Delete note")
        self.title = QLabel("")
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.title.setAttribute(Qt.WA_TransparentForMouseEvents)
        h.addWidget(self.btn_new)
        h.addWidget(self.title, 1)
        h.addWidget(self.btn_pin)
        h.addWidget(self.btn_menu)
        h.addWidget(self.btn_close)
        lay.addWidget(self.header)

        self.editor = QTextEdit()
        self.editor.setFrameShape(QFrame.NoFrame)
        self.editor.setAcceptRichText(False)
        self.editor.setPlaceholderText("Write something…")
        self.editor.document().setDocumentMargin(14)
        self.editor.document().setIndentWidth(18)
        self.editor.viewport().setAutoFillBackground(False)
        lay.addWidget(self.editor, 1)

        self.footer = QWidget()
        self.footer.setFixedHeight(18)
        f = QHBoxLayout(self.footer)
        f.setContentsMargins(0, 0, 4, 4)
        f.addStretch(1)
        self.grip = Grip()
        f.addWidget(self.grip, 0, Qt.AlignRight | Qt.AlignBottom)
        lay.addWidget(self.footer)

        self.btn_new.clicked.connect(self.new_requested.emit)
        self.btn_pin.clicked.connect(lambda: self.set_on_top(not self.data["on_top"]))
        self.btn_menu.clicked.connect(self.show_menu)
        self.btn_close.clicked.connect(lambda: self.delete_requested.emit(self))
        self.editor.textChanged.connect(self._on_text)

        # Keyboard shortcuts
        ctx = Qt.WidgetWithChildrenShortcut
        for keys, fn in (
            ("Ctrl+B", self.toggle_bold),
            ("Ctrl+I", self.toggle_italic),
            ("Ctrl+Shift+X", self.toggle_strike),
            ("Ctrl+Shift+L", self.toggle_bullets),
        ):
            sc = QShortcut(QKeySequence(keys), self.editor)
            sc.setContext(ctx)
            sc.activated.connect(fn)
        new_sc = QShortcut(QKeySequence("Ctrl+N"), self)
        new_sc.setContext(Qt.WindowShortcut)
        new_sc.activated.connect(self.new_requested.emit)

    # --------------------------------------------------------------- styling
    def color(self) -> str:
        return self.data.get("color") or self.s["default_color"]

    def font_size(self) -> int:
        return int(self.data.get("font_size") or self.s["font_size"])

    def opacity(self) -> int:
        v = self.data.get("opacity")
        return int(v if v is not None else self.s["opacity"])

    def apply_style(self) -> None:
        s = self.s
        bg = self.color()
        text = auto_text(bg) if s["auto_text"] else s["text_color"]
        border = QColor(255, 255, 255, 26) if is_dark(bg) else QColor(0, 0, 0, 22)
        fill = QColor(bg)
        fill.setAlphaF(max(0.0, min(1.0, self.opacity() / 100)))
        self.card.set_look(fill, border, int(s["corner_radius"]))
        self.card.setStyleSheet(
            f"""
            QTextEdit {{ background: transparent; border: none; color: {text};
                         selection-background-color: {rgba(text, 0.28)}; }}
            QLabel {{ background: transparent; color: {rgba(text, 0.72)}; font-weight: 600; }}
            QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px 2px 2px 0; }}
            QScrollBar::handle:vertical {{ background: {rgba(text, 0.22)}; border-radius: 3px; min-height: 28px; }}
            QScrollBar::handle:vertical:hover {{ background: {rgba(text, 0.4)}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            """
        )
        font = QFont(s["font_family"])
        font.setPointSize(self.font_size())
        self.editor.setFont(font)
        self.editor.document().setDefaultFont(font)
        pal = self.editor.palette()
        ph = QColor(text)
        ph.setAlpha(110)
        pal.setColor(QPalette.PlaceholderText, ph)
        self.editor.setPalette(pal)

        for b in (self.btn_new, self.btn_pin, self.btn_menu, self.btn_close):
            b.set_color(text)
        self.btn_pin.set_active(self.data["on_top"])
        self.grip.color = QColor(text)
        self.grip.update()

        self.shadow.setEnabled(bool(s["shadow"]))
        self.repaint_all()
        self._update_controls()

    def repaint_all(self) -> None:
        """Force a full repaint (also after a popup menu/dialog closed over the note)."""
        self.card.update()
        self.update()
        QTimer.singleShot(0, self._repaint_now)

    def _repaint_now(self) -> None:
        self.card.update()
        self.repaint()

    def _update_controls(self) -> None:
        collapsed = bool(self.data["collapsed"])
        show = (not self.s["hover_controls"]) or self._hover or collapsed
        for b in (self.btn_new, self.btn_pin, self.btn_menu, self.btn_close):
            b.setVisible(show)
        self.title.setText(self._title_text if collapsed else "")
        self.grip.shown = show and not collapsed
        self.grip.update()

    def enterEvent(self, e):
        self._hover = True
        self._update_controls()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._update_controls()
        super().leaveEvent(e)

    # ------------------------------------------------------------ behaviour
    def _refresh_title(self) -> None:
        self._title_text = "Empty note"
        for line in self.editor.toPlainText().splitlines():
            if line.strip():
                self._title_text = line.strip()[:60]
                break
        if self.data.get("collapsed"):
            self.title.setText(self._title_text)

    def _on_text(self) -> None:
        self._refresh_title()
        self.changed.emit()

    def moveEvent(self, e):
        super().moveEvent(e)
        self.changed.emit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.changed.emit()

    def closeEvent(self, e):  # Alt+F4 just hides; "Delete" removes a note
        e.ignore()
        self.hide()

    def ensure_on_screen(self) -> None:
        center = self.frameGeometry().center()
        for sc in QGuiApplication.screens():
            if sc.availableGeometry().contains(center):
                return
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.move(g.center() - QPoint(self.width() // 2, self.height() // 2))

    def focus_editor(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.editor.setFocus()

    def set_collapsed(self, flag: bool, init: bool = False) -> None:
        if flag and not init and not self.data["collapsed"]:
            self._expanded_h = self.height()
        self.data["collapsed"] = flag
        if flag:
            self.editor.hide()
            self.footer.hide()
            self.setMinimumHeight(0)
            self.setFixedHeight(HEADER_H + 2 * M)
        else:
            self.editor.show()
            self.footer.show()
            self.setMinimumHeight(MIN_H)
            self.setMaximumHeight(16777215)
            self.resize(self.width(), self._expanded_h)
        self._update_controls()
        if not init:
            self.changed.emit()

    def set_on_top(self, flag: bool) -> None:
        flag = bool(flag)
        self.data["on_top"] = flag
        self.btn_pin.set_active(flag)
        if bool(self.windowFlags() & Qt.WindowStaysOnTopHint) == flag:
            return
        was_visible = self.isVisible()
        geo = self.geometry()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, flag)
        self.setGeometry(geo)
        if was_visible:
            self.show()
        self.changed.emit()

    def set_color(self, color: str | None) -> None:
        self.data["color"] = color
        self.apply_style()
        self.changed.emit()

    def set_opacity(self, value: int | None) -> None:
        self.data["opacity"] = value
        self.apply_style()
        self.changed.emit()

    def set_font_size(self, value: int | None) -> None:
        self.data["font_size"] = None if value is None else max(8, min(40, int(value)))
        self.apply_style()
        self.changed.emit()

    def clear_overrides(self) -> None:
        self.data["color"] = None
        self.data["opacity"] = None
        self.data["font_size"] = None
        self.apply_style()
        self.changed.emit()

    def pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self.color()), self, "Note color")
        if c.isValid():
            self.set_color(c.name())
        self.repaint_all()

    # ------------------------------------------------------------ formatting
    def toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(400 if self.editor.currentCharFormat().fontWeight() >= 600 else 700)
        self.editor.mergeCurrentCharFormat(fmt)

    def toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.editor.currentCharFormat().fontItalic())
        self.editor.mergeCurrentCharFormat(fmt)

    def toggle_strike(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.editor.currentCharFormat().fontStrikeOut())
        self.editor.mergeCurrentCharFormat(fmt)

    def toggle_bullets(self) -> None:
        cur = self.editor.textCursor()
        lst = cur.currentList()
        if lst:
            block_fmt = cur.blockFormat()
            block_fmt.setIndent(0)
            cur.setBlockFormat(block_fmt)
            lst.remove(cur.block())
        else:
            cur.createList(QTextListFormat.ListDisc)

    # ------------------------------------------------------------------ menu
    def show_menu(self) -> None:
        m = QMenu(self)
        m.setStyleSheet(MENU_QSS)

        swatches = SwatchRow(self.color(), m)
        swatches.picked.connect(lambda c: (m.close(), self.set_color(c)))
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(6, 4, 6, 4)
        hl.addWidget(swatches)
        wa = QWidgetAction(m)
        wa.setDefaultWidget(holder)
        m.addAction(wa)
        m.addAction("Custom color…", self.pick_color)
        m.addSeparator()

        a = m.addAction("Always on top")
        a.setCheckable(True)
        a.setChecked(self.data["on_top"])
        a.triggered.connect(lambda v: self.set_on_top(v))
        m.addAction("Expand" if self.data["collapsed"] else "Collapse to title bar",
                    lambda: self.set_collapsed(not self.data["collapsed"]))

        tm = m.addMenu("Transparency")
        grp = QActionGroup(tm)
        current = self.opacity()
        for v in (100, 90, 80, 70, 60, 50):
            act = tm.addAction(f"{v}%")
            act.setCheckable(True)
            act.setChecked(v == current)
            grp.addAction(act)
            act.triggered.connect(lambda _=False, val=v: self.set_opacity(val))
        tm.addSeparator()
        tm.addAction("Use default", lambda: self.set_opacity(None))

        fm = m.addMenu("Text size")
        fm.addAction("Larger", lambda: self.set_font_size(self.font_size() + 1))
        fm.addAction("Smaller", lambda: self.set_font_size(self.font_size() - 1))
        fm.addAction("Use default", lambda: self.set_font_size(None))

        m.addSeparator()
        m.addAction("Duplicate", lambda: self.duplicate_requested.emit(self))
        m.addAction("Delete note", lambda: self.delete_requested.emit(self))

        m.exec(self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height() + 2)))
        self.repaint_all()
        self._hover = self.rect().contains(self.mapFromGlobal(QCursor.pos()))
        self._update_controls()

    # ----------------------------------------------------------- persistence
    def snapshot(self) -> dict:
        g = self.geometry()
        d = self.data
        d["x"], d["y"], d["w"] = g.x(), g.y(), g.width()
        d["h"] = self._expanded_h if d["collapsed"] else g.height()
        d["text"] = self._html()
        return d

    def _html(self) -> str:
        """Rich text as HTML, minus the body font so Settings can still control the font."""
        if not self.editor.toPlainText():
            return ""
        return re.sub(r'<body style="[^"]*">', "<body>", self.editor.toHtml(), count=1)
