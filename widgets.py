"""Small custom-painted widgets shared by the notes and the settings window."""
from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QColorDialog, QHBoxLayout, QPushButton, QWidget

from themes import ACCENT, NOTE_COLORS, luminance


class IconButton(QAbstractButton):
    """Flat vector icon button (plus / close / menu / pin), tinted to match the note."""

    def __init__(self, kind: str, tip: str = "", parent=None):
        super().__init__(parent)
        self.kind = kind
        self._color = QColor("#000000")
        self._active = False
        self._hover = False
        self.setFixedSize(26, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self.setFocusPolicy(Qt.NoFocus)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._hover:
            bg = QColor(self._color)
            bg.setAlpha(36)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 7, 7)
        col = QColor(self._color)
        col.setAlpha(255 if (self._hover or self._active) else 165)
        p.setPen(QPen(col, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        if self.kind == "plus":
            p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
            p.drawLine(QPointF(cx, cy - 5), QPointF(cx, cy + 5))
        elif self.kind == "close":
            d = 4.5
            p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
            p.drawLine(QPointF(cx - d, cy + d), QPointF(cx + d, cy - d))
        elif self.kind == "menu":
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            for dx in (-5, 0, 5):
                p.drawEllipse(QPointF(cx + dx, cy), 1.7, 1.7)
        elif self.kind == "pin":
            p.translate(cx, cy)
            p.rotate(35)
            if self._active:
                p.setBrush(col)
            p.drawRoundedRect(QRectF(-3.2, -7, 6.4, 8.5), 1.6, 1.6)
            p.drawLine(QPointF(-5, 1.5), QPointF(5, 1.5))
            p.drawLine(QPointF(0, 1.5), QPointF(0, 7))


class ToggleSwitch(QAbstractButton):
    """Animated on/off switch."""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def set_silent(self, on: bool) -> None:
        self.blockSignals(True)
        self.setChecked(bool(on))
        self.blockSignals(False)
        self._pos = 1.0 if on else 0.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off, on = QColor("#3A3F4B"), QColor(ACCENT)
        t = self._pos
        bg = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()), 12, 12)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(3 + t * (self.width() - 24), 3, 18, 18))


class Swatch(QAbstractButton):
    def __init__(self, color: str, name: str, d: int = 22, parent=None):
        super().__init__(parent)
        self.color = color
        self.selected = False
        self.setFixedSize(d + 8, d + 8)
        self.setToolTip(name)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        p.setPen(QPen(QColor(0, 0, 0, 70), 1))
        p.setBrush(QColor(self.color))
        p.drawEllipse(r)
        if self.selected:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(ACCENT), 2))
            p.drawEllipse(r.adjusted(-3, -3, 3, 3))


class SwatchRow(QWidget):
    """Row of preset note colors."""

    picked = Signal(str)

    def __init__(self, current: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._sw: list[Swatch] = []
        for name, hex_ in NOTE_COLORS:
            sw = Swatch(hex_, name)
            sw.clicked.connect(lambda _=False, h=hex_: self.picked.emit(h))
            lay.addWidget(sw)
            self._sw.append(sw)
        self.set_current(current)

    def set_current(self, color: str) -> None:
        for sw in self._sw:
            sw.selected = sw.color.lower() == (color or "").lower()
            sw.update()


class ColorChip(QPushButton):
    """Button showing a color; opens the system color picker on click."""

    picked = Signal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._c = color
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self.setMinimumWidth(112)
        self.clicked.connect(self._choose)
        self._refresh()

    def set_color(self, color: str) -> None:
        self._c = color
        self._refresh()

    def _refresh(self) -> None:
        fg = "#111111" if luminance(self._c) > 0.55 else "#FFFFFF"
        self.setText(self._c.upper())
        self.setStyleSheet(
            f"QPushButton{{background:{self._c};color:{fg};border:1px solid rgba(255,255,255,50);"
            f"border-radius:9px;padding:0 14px;font-weight:600;}}"
            f"QPushButton:disabled{{background:#2A2E38;color:#6C7282;border:1px solid #2E323C;}}"
        )

    def _choose(self) -> None:
        c = QColorDialog.getColor(QColor(self._c), self.window(), "Choose a color")
        if c.isValid():
            self.set_color(c.name())
            self.picked.emit(c.name())
