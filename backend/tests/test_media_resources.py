import subprocess

import pytest

from app.core.errors import Problem
from app.services.media import command


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.TimeoutExpired(["ffmpeg"], 120),
        subprocess.CalledProcessError(-9, ["ffmpeg"], stderr=b""),
        subprocess.CalledProcessError(1, ["ffmpeg"], stderr=b"malloc of size 10000 failed"),
    ],
)
def test_resource_failures_are_retryable_not_invalid_media(monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(Problem) as result:
        command(["ffmpeg"], 120)
    assert result.value.status == 503


def test_corrupt_media_remains_validation_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["ffmpeg"], stderr=b"invalid data found")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(Problem) as result:
        command(["ffmpeg"], 120)
    assert result.value.status == 422
