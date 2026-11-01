import hashlib
import json
import subprocess
import warnings
from fractions import Fraction
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import Settings
from app.core.errors import Problem, require


def copy_bounded(source: BinaryIO, target: Path, limit: int) -> str:
    total = 0
    digest = hashlib.sha256()
    with target.open("wb") as output:
        while chunk := source.read(1024 * 1024):
            total += len(chunk)
            require(total <= limit, 413, "media_too_large", "Media exceeds the upload limit")
            digest.update(chunk)
            output.write(chunk)
    require(total > 0, 422, "invalid_media", "Empty media")
    return digest.hexdigest()


def command(args: list[str], timeout: int) -> bytes:
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=True)
        return result.stdout
    except FileNotFoundError as exc:
        raise Problem(503, "media_tools_unavailable", "Media tools are unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise Problem(
            503,
            "media_processing_timeout",
            "Media processing exceeded its time budget; retry later",
        ) from exc
    except subprocess.CalledProcessError as exc:
        if exc.returncode in {
            -9,
            137,
            0xC0000017,
            0xC000012D,
            0xC0000142,
            -1073741801,
            -1073741523,
            -1073741502,
        } or any(
            term in (exc.stderr or b"").lower()
            for term in (
                b"cannot allocate memory",
                b"out of memory",
                b"resource temporarily unavailable",
                b"malloc of size",
                b"failed to allocate",
                b"allocation failed",
            )
        ):
            raise Problem(
                503,
                "media_resources_exhausted",
                "Media processing exceeded available resources; retry later",
            ) from exc
        raise Problem(422, "invalid_media", "Media could not be safely processed") from exc


def sanitize(source: Path, directory: Path, kind: str, config: Settings) -> tuple[Path, str]:
    if kind == "photo":
        return sanitize_image(source, directory, config)
    return sanitize_video(source, directory, config)


def sanitize_image(source: Path, directory: Path, config: Settings) -> tuple[Path, str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as image:
                require(
                    image.format in {"JPEG", "PNG", "WEBP"},
                    422,
                    "invalid_media",
                    "Unsupported image format",
                )
                width, height = image.size
                require(
                    width * height <= config.image_max_pixels
                    and max(width, height) <= config.image_max_dimension,
                    422,
                    "invalid_media",
                    "Image dimensions exceed limits",
                )
                require(
                    getattr(image, "n_frames", 1) == 1,
                    422,
                    "invalid_media",
                    "Animated images are unsupported",
                )
                image.load()
                ImageOps.exif_transpose(image, in_place=True)
                mode = "RGBA" if "A" in image.getbands() else "RGB"
                clean = Image.new(mode, image.size)
                clean.paste(image if image.mode == mode else image.convert(mode))
                output = directory / "sanitized.png"
                clean.save(output, format="PNG")
                return output, "image/png"
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise Problem(422, "invalid_media", "Invalid or unsafe image") from exc


def video_demuxer(source: Path) -> str:
    """Restrict probing to MP4/WebM, before any demuxer can follow a playlist."""
    with source.open("rb") as body:
        header = body.read(4096)
    if len(header) >= 16 and header[4:8] == b"ftyp":
        size = int.from_bytes(header[:4], "big")
        brands = {
            b"isom",
            b"iso2",
            b"iso3",
            b"iso4",
            b"iso5",
            b"iso6",
            b"mp41",
            b"mp42",
            b"avc1",
            b"M4V ",
            b"dash",
            b"cmfc",
            b"cmfs",
        }
        require(
            16 <= size <= len(header) and header[8:12] in brands,
            422,
            "invalid_media",
            "Unsupported MP4 brand",
        )
        return "mov"
    if header.startswith(b"\x1a\x45\xdf\xa3"):

        def vint(position: int, *, identifier: bool = False) -> tuple[int, int]:
            require(position < len(header), 422, "invalid_media", "Invalid WebM header")
            first = header[position]
            width = next((w for w in range(1, 9) if first & (1 << (8 - w))), 0)
            require(
                width > 0 and position + width <= len(header),
                422,
                "invalid_media",
                "Invalid WebM header",
            )
            value = int.from_bytes(header[position : position + width], "big")
            if not identifier:
                value &= (1 << (7 * width)) - 1
            return value, position + width

        size, position = vint(4)
        end = position + size
        require(end <= len(header), 422, "invalid_media", "WebM header exceeds safe limit")
        while position < end:
            element, position = vint(position, identifier=True)
            length, position = vint(position)
            require(position + length <= end, 422, "invalid_media", "Invalid WebM header")
            if element == 0x4282:
                require(
                    header[position : position + length] == b"webm",
                    422,
                    "invalid_media",
                    "Only WebM supported",
                )
                return "matroska"
            position += length
    raise Problem(422, "invalid_media", "Only MP4/WebM video supported")


def validate_decoded_timing(decoded: bytes) -> None:
    """Frame CRC records include the last frame's duration, unlike old progress PTS."""
    try:
        time_base = None
        first = end = None
        for line in decoded.decode("ascii").splitlines():
            if line.startswith("#tb 0:"):
                time_base = Fraction(line.split(":", 1)[1].strip())
            elif line and not line.startswith("#"):
                fields = line.split(",")
                if int(fields[0]) != 0:
                    continue  # audio is decoded too; container checks bound its duration
                pts, duration = int(fields[2]), int(fields[3])
                require(duration > 0, 422, "invalid_media", "Decoded frame duration is invalid")
                first = pts if first is None else min(first, pts)
                end = pts + duration if end is None else max(end, pts + duration)
        require(
            time_base is not None and time_base > 0 and first is not None and end is not None,
            422,
            "invalid_media",
            "Video has no decoded timing",
        )
        assert time_base is not None and first is not None and end is not None
        require(
            5 <= (end - first) * time_base <= 30,
            422,
            "invalid_duration",
            "Decoded video must be 5–30 seconds",
        )
    except (IndexError, ValueError, ZeroDivisionError, UnicodeError) as exc:
        raise Problem(422, "invalid_media", "Video decoding could not be validated") from exc


def sanitize_video(source: Path, directory: Path, config: Settings) -> tuple[Path, str]:
    demuxer = video_demuxer(source)
    raw = command(
        [
            config.ffprobe,
            "-threads",
            str(config.ffmpeg_threads),
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-f",
            demuxer,
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(source),
        ],
        20,
    )
    try:
        data = json.loads(raw)
        streams = data["streams"]
        formats = set(data["format"]["format_name"].split(","))
        require(
            bool(formats & {"mp4", "webm"}), 422, "invalid_media", "Only MP4/WebM video supported"
        )
        # Browser MediaRecorder WebM often has no seekable duration header. In that
        # case bounded decoding and the sanitized output probe establish duration.
        if "duration" in data["format"]:
            duration = float(data["format"]["duration"])
            require(5 <= duration <= 30, 422, "invalid_duration", "Video must be 5–30 seconds")
        videos = [s for s in streams if s["codec_type"] == "video"]
        audios = [s for s in streams if s["codec_type"] == "audio"]
        require(
            len(videos) == 1 and len(audios) <= 1 and len(streams) == len(videos) + len(audios),
            422,
            "invalid_media",
            "Unsupported stream layout",
        )
        video = videos[0]
        video_time_base = Fraction(video["time_base"])
        require(video_time_base > 0, 422, "invalid_media", "Invalid video time base")
        mp4 = demuxer == "mov"
        require(
            video["codec_name"] in ({"h264"} if mp4 else {"vp8", "vp9"})
            and video.get("pix_fmt") == "yuv420p"
            and video.get("color_transfer") not in {"smpte2084", "arib-std-b67"}
            and (
                not mp4
                or video.get("profile") in {"Baseline", "Constrained Baseline", "Main", "High"}
            )
            and all(s["codec_name"] in ({"aac"} if mp4 else {"opus", "vorbis"}) for s in audios),
            422,
            "invalid_media",
            "Use 8-bit H.264 (Baseline/Main/High) MP4 or VP8/VP9 WebM with compatible audio. "
            "HEVC/HDR is unsupported. Record with this app or export a compatible 720p video.",
        )
        require(
            not mp4 or all(s.get("profile") == "LC" for s in audios),
            422,
            "invalid_media",
            "MP4 audio must be AAC-LC. Record with this app or export a compatible 720p MP4.",
        )
        require(
            0 < min(video["width"], video["height"]) <= 720
            and max(video["width"], video["height"]) <= 1280,
            422,
            "invalid_media",
            "Video must be at most 720p (1280 x 720 landscape or 720 x 1280 portrait). "
            "Record with this app or export at 720p; the server does not resize videos.",
        )
    except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
        raise Problem(422, "invalid_media", "Invalid video metadata") from exc
    # Decode every selected stream: remuxing alone does not validate compressed
    # frames. Stop at 31s for untrusted/missing duration headers, then separately
    # check remuxed timing. There is deliberately no encoder or scaling fallback.
    decoded = command(
        [
            config.ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-err_detect",
            "explode",
            "-protocol_whitelist",
            "file,pipe",
            "-threads",
            str(config.ffmpeg_threads),
            "-noautorotate",
            "-f",
            demuxer,
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-threads",
            str(config.ffmpeg_threads),
            "-filter_threads",
            "1",
            "-filter_complex_threads",
            "1",
            "-t",
            "31",
            "-nostats",
            "-fps_mode",
            "passthrough",
            "-enc_time_base:v",
            str(video_time_base),
            "-f",
            "framecrc",
            "-",
        ],
        120,
    )
    validate_decoded_timing(decoded)
    output = directory / ("sanitized.mp4" if mp4 else "sanitized.webm")
    command(
        [
            config.ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-protocol_whitelist",
            "file,pipe",
            "-threads",
            str(config.ffmpeg_threads),
            "-filter_threads",
            "1",
            "-filter_complex_threads",
            "1",
            "-f",
            demuxer,
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-map_metadata",
            "-1",
            "-map_metadata:s",
            "-1",
            "-map_chapters",
            "-1",
            "-c",
            "copy",
            "-fs",
            str(config.video_max_bytes + 1024 * 1024),
            # H.264 SEI can contain user data, not just container tags. Strip it
            # without altering picture samples. Keep technical rotation matrices.
            *(["-bsf:v", "filter_units=remove_types=6", "-movflags", "+faststart"] if mp4 else []),
            "-y",
            str(output),
        ],
        30,
    )
    require(
        output.stat().st_size < config.video_max_bytes + 1024 * 1024,
        422,
        "invalid_media",
        "Sanitized video exceeds safe storage limit",
    )
    checked = json.loads(
        command(
            [
                config.ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(output),
            ],
            10,
        )
    )
    try:
        require(
            5 <= float(checked["format"]["duration"]) <= 30,
            422,
            "invalid_duration",
            "Decoded video must be 5–30 seconds",
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise Problem(422, "invalid_media", "Invalid sanitized video") from exc
    return output, "video/mp4" if mp4 else "video/webm"
