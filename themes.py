"""Colors, shared styles and the app icon (drawn in code, no image files needed)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

ACCENT = "#7C9CFF"

NOTE_COLORS = [
    ("Butter", "#FFF1A8"),
    ("Peach", "#FFD5BC"),
    ("Rose", "#FFCAD8"),
    ("Lavender", "#DDCEFF"),
    ("Sky", "#BFE3FF"),
    ("Mint", "#C5F1D6"),
    ("Sage", "#D9E6B8"),
    ("Cloud", "#ECEFF4"),
    ("Slate", "#353A45"),
    ("Midnight", "#1C2030"),
]


def luminance(hex_color: str) -> float:
    c = QColor(hex_color)
    return (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0


def is_dark(hex_color: str) -> bool:
    return luminance(hex_color) < 0.5


def auto_text(bg: str) -> str:
    return "#F1F3F7" if is_dark(bg) else "#23262B"


def rgba(hex_color: str, alpha: float) -> str:
    """QSS-safe rgba() string (alpha 0..1 converted to 0..255)."""
    c = QColor(hex_color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{int(max(0.0, min(1.0, alpha)) * 255)})"


MENU_QSS = """
QMenu { background: #1B1E25; color: #E7E9EE; border: 1px solid #2E323C;
        border-radius: 10px; padding: 6px; font-size: 13px; }
QMenu::item { padding: 8px 24px 8px 14px; border-radius: 6px; margin: 1px 0; }
QMenu::item:selected { background: #2B3040; }
QMenu::item:disabled { color: #6C7282; }
QMenu::separator { height: 1px; background: #2A2E38; margin: 6px 8px; }
QMenu::indicator { width: 14px; height: 14px; left: 4px; }
"""


def draw_icon(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)
    body = QRectF(s * 0.13, s * 0.13, s * 0.74, s * 0.74)
    clip = QPainterPath()
    clip.addRoundedRect(body, s * 0.16, s * 0.16)
    p.setClipPath(clip)
    p.fillRect(body, QColor("#FFD84D"))
    p.fillRect(QRectF(body.left(), body.top(), body.width(), s * 0.17), QColor("#F2B705"))
    p.setPen(QPen(QColor("#5B4A00"), s * 0.045, Qt.SolidLine, Qt.RoundCap))
    for i, frac in enumerate((0.48, 0.62, 0.76)):
        y = s * frac
        x2 = body.right() - s * 0.12 - (s * 0.22 if i == 2 else 0)
        p.drawLine(QPointF(body.left() + s * 0.12, y), QPointF(x2, y))
    fold = QPainterPath()
    fold.moveTo(body.right(), body.bottom() - s * 0.2)
    fold.lineTo(body.right() - s * 0.2, body.bottom())
    fold.lineTo(body.right(), body.bottom())
    fold.closeSubpath()
    p.setPen(Qt.NoPen)
    p.fillPath(fold, QColor("#E0A400"))
    p.end()
    return pm


def app_icon() -> QIcon:
    return QIcon(draw_icon(256))
