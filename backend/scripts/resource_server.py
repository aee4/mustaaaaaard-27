"""Test-only diagnostics: tool exit classification without media, URLs or secrets."""

import json
import runpy
import time
from pathlib import Path

from app.services import media

original = media.command


def measured(args: list[str], timeout: int) -> bytes:
    started = time.monotonic()
    try:
        return original(args, timeout)
    except Exception as exc:
        cause = exc.__cause__
        print(
            json.dumps(
                {
                    "tool": Path(args[0]).stem,
                    "seconds": round(time.monotonic() - started, 2),
                    "failure": type(exc).__name__,
                    "code": getattr(exc, "code", None),
                    "exit": getattr(cause, "returncode", None),
                    "allocation_error": b"memory" in (getattr(cause, "stderr", b"") or b"").lower(),
                }
            ),
            flush=True,
        )
        raise


if __name__ == "__main__":
    media.command = measured
    runpy.run_module("scripts.serve_web", run_name="__main__")
