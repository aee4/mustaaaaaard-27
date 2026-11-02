"""Generate circular icons with transparent corners; preserve the supplied source."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

public = Path(__file__).resolve().parents[1] / "public"
source = public / "favicon.png"
if source.exists():
    with Image.open(source) as original:
        artwork = ImageOps.exif_transpose(original).convert("RGBA")
else:
    if (public / "favicon.svg").exists():
        raise SystemExit("SVG exists: use it directly; install an SVG renderer for PNG derivatives")
    artwork = Image.new("RGBA", (512, 512), "#e9b52e")
    ImageDraw.Draw(artwork).text((256, 256), "M", fill="#25251f", anchor="mm", font_size=340)
    artwork.save(source)

tile = Image.new("RGBA", (512, 512), "#e9b52e")
fitted = ImageOps.contain(artwork, tile.size, Image.Resampling.LANCZOS)
tile.alpha_composite(fitted, ((512 - fitted.width) // 2, (512 - fitted.height) // 2))

# Draw the circle at higher resolution so its edge stays smooth at favicon sizes.
mask = Image.new("L", (2048, 2048), 0)
ImageDraw.Draw(mask).ellipse((0, 0, 2047, 2047), fill=255)
tile.putalpha(mask.resize(tile.size, Image.Resampling.LANCZOS))
for size, name in [(16, "favicon-16.png"), (32, "favicon-32.png"), (180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")]:
    tile.resize((size, size), Image.Resampling.LANCZOS).save(public / name)
tile.save(public / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
print("Circular icon derivatives generated with transparent corners; original preserved.")
