"""Generate a public monogram; private photos stay in group storage."""
from pathlib import Path

from PIL import Image, ImageDraw

public = Path(__file__).resolve().parents[1] / "public"
source = public / "favicon.png"
tile = Image.new("RGBA", (512, 512), "#e9b52e")
ImageDraw.Draw(tile).line([(135,355),(135,158),(256,285),(377,158),(377,355)], fill="#25251f", width=48, joint="curve")

# Draw the circle at higher resolution so its edge stays smooth at favicon sizes.
mask = Image.new("L", (2048, 2048), 0)
ImageDraw.Draw(mask).ellipse((0, 0, 2047, 2047), fill=255)
tile.putalpha(mask.resize(tile.size, Image.Resampling.LANCZOS))
tile.save(source)
for size, name in [(16, "favicon-16.png"), (32, "favicon-32.png"), (180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")]:
    tile.resize((size, size), Image.Resampling.LANCZOS).save(public / name)
tile.save(public / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
print("Circular public brand monogram generated.")
