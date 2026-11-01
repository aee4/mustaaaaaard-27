import io
from datetime import UTC, date, datetime

import pytest
from PIL import Image
from pydantic import ValidationError

from app.core.clock import activity_date, week_bounds
from app.core.config import Settings
from app.core.errors import Problem
from app.main import create_app
from app.services.media import copy_bounded, sanitize_image
from app.services.streaks import replay
from tests.conftest import photo


def test_calendar_midnight_and_monday():
    sunday = datetime(2026, 11, 1, 23, 59, 59, tzinfo=UTC)
    monday = datetime(2026, 11, 2, tzinfo=UTC)
    assert activity_date(sunday) == date(2026, 11, 1)
    assert week_bounds(sunday)[1] == monday
    assert week_bounds(monday)[0] == monday


def test_grace_one_then_two_misses_and_no_today_miss():
    monday = date(2026, 11, 2)
    result, history = replay({monday}, date(2026, 11, 3), {})
    assert result.current == 1 and history == {}
    result, history = replay({monday, date(2026, 11, 4)}, date(2026, 11, 5), {})
    assert (result.current, result.longest) == (2, 2)
    assert history == {monday: date(2026, 11, 3)}
    result, _ = replay({monday, date(2026, 11, 4)}, date(2026, 11, 6), history)
    assert (result.current, result.longest) == (0, 2)


def test_sunday_monday_misses_have_separate_grace():
    result, history = replay({date(2026, 10, 31), date(2026, 11, 3)}, date(2026, 11, 3), {})
    assert result.current == result.longest == 2
    assert history == {date(2026, 10, 26): date(2026, 11, 1), date(2026, 11, 2): date(2026, 11, 2)}


def test_grace_cannot_start_resurrect_or_move_after_deletion():
    history = {date(2026, 11, 2): date(2026, 11, 3)}
    result, preserved = replay({date(2026, 11, 4)}, date(2026, 11, 5), history)
    assert result.current == 1 and preserved == history
    result, preserved = replay(set(), date(2026, 11, 6), history)
    assert result.current == result.longest == 0 and preserved == history


@pytest.mark.parametrize(
    "override",
    [
        {"dev_auth": True},
        {"cookie_secure": False},
        {"secret_key": "short"},
        {"google_client_id": ""},
        {"google_client_secret": ""},
        {"allowed_origins": ["http://localhost"]},
        {"base_url": "http://localhost"},
        {"s3_secret_key": "mustard-local-password"},
    ],
)
def test_production_rejects_unsafe_settings(override):
    values = dict(
        environment="production",
        dev_auth=False,
        cookie_secure=True,
        secret_key="a" * 48,
        google_client_id="google-client",
        google_client_secret="secret",
        allowed_origins=["https://mustard.example"],
        base_url="https://mustard.example",
        s3_access_key="service-identity",
        s3_secret_key="secure-key",
        s3_public_endpoint="https://storage.example",
        database_url="postgresql+psycopg://service:secret@db/app",
    )
    values.update(override)
    with pytest.raises(ValidationError):
        Settings(**values)


def test_upload_stream_enforces_limit_before_entire_read(tmp_path):
    body = io.BytesIO(b"x" * 2_000_000)
    with pytest.raises(Problem) as failure:
        copy_bounded(body, tmp_path / "upload", 100)
    assert failure.value.status == 413
    assert body.tell() < len(body.getvalue())


def test_decoder_and_metadata_sanitization(tmp_path):
    original = tmp_path / "original"
    original.write_bytes(photo(exif=True))
    output, content_type = sanitize_image(original, tmp_path, Settings())
    with Image.open(output) as image:
        assert not image.getexif() and not image.info
        assert image.size == (16, 16)
    assert content_type == "image/png"
    original.write_bytes(b"pretend JPEG")
    with pytest.raises(Problem):
        sanitize_image(original, tmp_path, Settings())


def test_image_dimension_and_animation_limits(tmp_path):
    original = tmp_path / "original"
    original.write_bytes(photo())
    with pytest.raises(Problem):
        sanitize_image(original, tmp_path, Settings(image_max_pixels=10))
    Image.new("RGB", (2, 2)).save(original, format="GIF")
    with pytest.raises(Problem):
        sanitize_image(original, tmp_path, Settings())


def test_openapi_has_explicit_contracts_and_no_frontend():
    schema = create_app(Settings()).openapi()
    assert "/groups/{group_id}/gallery" in schema["paths"]
    assert "PostOut" in schema["components"]["schemas"]
    assert all("comments" not in path for path in schema["paths"])
