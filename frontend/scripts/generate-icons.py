"""Deterministic icon resizing/format conversion; preserve the supplied source."""
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
for size, name in [(16, "favicon-16.png"), (32, "favicon-32.png"), (180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")]:
    tile.resize((size, size), Image.Resampling.LANCZOS).convert("RGB").save(public / name)
tile.save(public / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
print("Icon derivatives generated; original preserved. No manifest or service worker added.")
