from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageOps

from app.core.config import Settings
from app.core.errors import Problem
from app.services.media import sanitize_image


@pytest.mark.parametrize("format_name", ["JPEG", "PNG", "WEBP"])
@pytest.mark.parametrize("orientation", [1, 6])
def test_high_resolution_photo_pixels_and_orientation_survive_sanitization(
    tmp_path: Path, format_name: str, orientation: int
):
    image = Image.linear_gradient("L").resize((1920, 1080)).convert("RGB")
    draw = ImageDraw.Draw(image)
    for x in range(0, image.width, 7):
        draw.line((x, 0, x, image.height), fill=(230, 25, 70))
    exif = Image.Exif()
    exif[274] = orientation
    exif[270] = "Private description, strip this"
    source = tmp_path / "original"
    image.save(source, format=format_name, exif=exif, quality=95)
    with Image.open(source) as decoded:
        expected = ImageOps.exif_transpose(decoded).convert("RGB")
    output, content_type = sanitize_image(source, tmp_path, Settings())
    with Image.open(output) as clean:
        assert content_type == "image/png"
        assert clean.size == ((1080, 1920) if orientation == 6 else (1920, 1080))
        assert ImageChops.difference(expected, clean.convert("RGB")).getbbox() is None
        assert not clean.getexif() and not clean.info


def test_high_resolution_photo_still_obeys_dimension_and_pixel_limits(tmp_path: Path):
    source = tmp_path / "original"
    Image.new("RGB", (1920, 1080)).save(source, format="JPEG")
    for settings in [Settings(image_max_pixels=2_000_000), Settings(image_max_dimension=1919)]:
        with pytest.raises(Problem, match="dimensions"):
            sanitize_image(source, tmp_path, settings)
