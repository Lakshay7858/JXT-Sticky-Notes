"""Regenerates icon.png and icon.ico (needs PySide6 + Pillow)."""
from pathlib import Path

from PySide6.QtWidgets import QApplication

from themes import draw_icon

ROOT = Path(__file__).resolve().parent
app = QApplication([])
png = ROOT / "icon.png"
draw_icon(512).save(str(png), "PNG")

from PIL import Image

Image.open(png).save(
    ROOT / "icon.ico",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("Wrote icon.png and icon.ico")
