"""Generate synthetic 30s H264/AAC files at the actual 50 MiB input boundary."""

import os
import struct
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
directory = root / ".tools" / "free-tier"
directory.mkdir(parents=True, exist_ok=True)
for name, dimensions, preset in [
    ("720p", "1280x720", "ultrafast"),
    ("portrait720p", "720x1280", "ultrafast"),
    ("720p-high", "1280x720", "medium"),
]:
    path = directory / f"{name}-50mib.mp4"
    if path.exists() and path.stat().st_size == 50 * 1024 * 1024:
        continue
    print(f"Generating synthetic {name}, 30s, motion/noise and audio", flush=True)
    subprocess.run(
        [
            os.environ.get("FFMPEG", "ffmpeg"),
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={dimensions}:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-vf",
            "noise=alls=8:allf=t",
            "-t",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-b:v",
            "12M",
            "-maxrate",
            "12M",
            "-bufsize",
            "24M",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "1",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            "-y",
            str(path),
        ],
        check=True,
        timeout=600,
    )
    remaining = 50 * 1024 * 1024 - path.stat().st_size
    if remaining < 8:
        raise RuntimeError("Fixture exceeded the size budget")
    # A valid MP4 free box pads to the byte boundary; decoded content remains 30s.
    with path.open("ab") as body:
        body.write(struct.pack(">I4s", remaining, b"free"))
        body.write(b"\0" * (remaining - 8))
    print(f"Prepared {name}: exactly {path.stat().st_size} bytes", flush=True)
