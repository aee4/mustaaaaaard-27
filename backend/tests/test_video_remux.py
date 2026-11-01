"""Synthetic codec fixtures; these are not recordings from physical phones."""

import json

import pytest

from app.core.errors import Problem
from app.services import media


@pytest.mark.video
@pytest.mark.parametrize(
    "dimensions,codec,audio,extension,valid",
    [
        ("1280x720", "libx264", "aac", "mp4", True),
        ("720x1280", "libx264", "aac", "mp4", True),
        ("1282x720", "libx264", "aac", "mp4", False),
        ("722x722", "libx264", "aac", "mp4", False),
        ("64x64", "libvpx", "libopus", "webm", True),
        ("64x64", "libvpx-vp9", "libvorbis", "webm", True),
        ("64x64", "libx265", "aac", "mp4", False),
    ],
)
def test_remux_formats_dimensions_and_privacy(
    video_config, tmp_path, monkeypatch, dimensions, codec, audio, extension, valid
):
    source = tmp_path / f"source.{extension}"
    media.command(
        [
            video_config.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={dimensions}:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "5",
            "-threads",
            "1",
            "-c:v",
            codec,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            audio,
            "-metadata",
            "title=PRIVATE-TITLE",
            "-metadata",
            "artist=PRIVATE-PERSON",
            "-metadata",
            "location=+05.6037-000.1870/",
            "-metadata",
            "creation_time=2020-01-01T00:00:00Z",
            "-metadata:s:v:0",
            "title=PRIVATE-STREAM",
            "-y",
            str(source),
        ],
        60,
    )
    calls = []
    original = media.command

    def track(args, timeout):
        calls.append(args)
        return original(args, timeout)

    monkeypatch.setattr(media, "command", track)
    if not valid:
        with pytest.raises(Problem) as exc:
            media.sanitize_video(source, tmp_path, video_config)
        assert exc.value.code == "invalid_media"
        assert not any(args[0] == video_config.ffmpeg for args in calls)
        return
    output, mime = media.sanitize_video(source, tmp_path, video_config)
    assert mime == f"video/{extension}"
    remux = next(args for args in calls if "copy" in args)
    assert remux[remux.index("-c") + 1] == "copy"
    assert not any("libx264" in args or "libx265" in args for args in calls)
    assert any("null" in args and "-xerror" in args for args in calls)
    probed = json.loads(
        original(
            [
                video_config.ffprobe,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-show_chapters",
                "-of",
                "json",
                str(output),
            ],
            10,
        )
    )
    assert not probed.get("chapters")
    serialized = json.dumps(
        [
            probed["format"].get("tags", {}),
            *[stream.get("tags", {}) for stream in probed["streams"]],
        ]
    ).lower()
    for private in ["private-title", "private-person", "private-stream", "location", "2020-01-01"]:
        assert private not in serialized
    if extension == "mp4":
        # SEI encoder user data is removed too, not just ffprobe-visible tags.
        assert b"x264 - core" in source.read_bytes()
        assert b"x264 - core" not in output.read_bytes()

    def frames(path):
        raw = original(
            [
                video_config.ffmpeg,
                "-v",
                "error",
                "-threads",
                "1",
                "-i",
                str(path),
                "-map",
                "0:v:0",
                "-f",
                "framemd5",
                "-",
            ],
            30,
        )
        return [line.rsplit(b",", 1)[-1] for line in raw.splitlines() if not line.startswith(b"#")]

    assert frames(source) == frames(output)


@pytest.mark.video
@pytest.mark.parametrize(
    "pixel_format,transfer", [("yuv420p10le", "bt709"), ("yuv420p", "smpte2084")]
)
def test_rejects_10bit_or_hdr_without_conversion(video_config, tmp_path, pixel_format, transfer):
    source = tmp_path / "ten-bit.mp4"
    media.command(
        [
            video_config.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=64x64:r=10",
            "-t",
            "5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            pixel_format,
            "-x264-params",
            f"colorprim=bt2020:transfer={transfer}:colormatrix=bt2020nc",
            "-threads",
            "1",
            "-y",
            str(source),
        ],
        30,
    )
    with pytest.raises(Problem, match="8-bit"):
        media.sanitize_video(source, tmp_path, video_config)


@pytest.mark.video
def test_phone_style_rotation_survives_but_user_data_does_not(video_config, tmp_path):
    from tests.test_storage_video import make_video

    original = tmp_path / "original.mp4"
    make_video(video_config, original, 5)
    source = tmp_path / "rotated.mp4"
    media.command(
        [
            video_config.ffmpeg,
            "-v",
            "error",
            "-display_rotation",
            "90",
            "-i",
            str(original),
            "-c",
            "copy",
            "-metadata",
            "location=+05.6037-000.1870/",
            "-bsf:v",
            "h264_metadata=sei_user_data=0123456789abcdef0123456789abcdef+PRIVATE-SEI-GPS",
            "-y",
            str(source),
        ],
        10,
    )
    assert b"PRIVATE-SEI-GPS" in source.read_bytes()
    output, _ = media.sanitize_video(source, tmp_path, video_config)
    assert b"PRIVATE-SEI-GPS" not in output.read_bytes()

    def rotation(path):
        probe = json.loads(
            media.command(
                [
                    video_config.ffprobe,
                    "-v",
                    "error",
                    "-show_streams",
                    "-of",
                    "json",
                    str(path),
                ],
                10,
            )
        )
        return next(
            item["rotation"] for item in probe["streams"][0]["side_data_list"] if "rotation" in item
        )

    assert rotation(source) == rotation(output) == 90


@pytest.mark.video
def test_decoded_timing_cannot_be_replaced_by_container_duration(
    video_config, tmp_path, monkeypatch
):
    from tests.test_storage_video import make_video

    source = tmp_path / "source.mp4"
    make_video(video_config, source, 5)
    original = media.command

    def short_decode(args, timeout):
        if "-progress" in args:
            return b"frame=40\nout_time_us=4000000\nprogress=end\n"
        return original(args, timeout)

    monkeypatch.setattr(media, "command", short_decode)
    with pytest.raises(Problem) as exc:
        media.sanitize_video(source, tmp_path, video_config)
    assert exc.value.code == "invalid_duration"
    assert not (tmp_path / "sanitized.mp4").exists()
