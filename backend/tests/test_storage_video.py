import json
import os
import uuid
from pathlib import Path

import httpx
import pytest

from app.core.errors import Problem
from app.integrations.storage import S3Storage
from app.services.media import command, sanitize_video
from tests.conftest import photo, upload


def make_video(config, path: Path, seconds: float, metadata: bool = False) -> bytes:
    command(
        [
            config.ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=yellow:s=64x64:r=10",
            "-t",
            str(seconds),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-metadata",
            "location=+05.6037-000.1870/" if metadata else "title=test",
            "-y",
            str(path),
        ],
        30,
    )
    return path.read_bytes()


@pytest.mark.video
@pytest.mark.parametrize("seconds,valid", [(4.9, False), (5, True), (30, True), (30.1, False)])
def test_actual_video_duration_boundaries_and_metadata(video_config, tmp_path, seconds, valid):
    source = tmp_path / "input.mp4"
    make_video(video_config, source, seconds, metadata=True)
    if not valid:
        with pytest.raises(Problem) as exc:
            sanitize_video(source, tmp_path, video_config)
        assert exc.value.code == "invalid_duration"
        return
    output, mime = sanitize_video(source, tmp_path, video_config)
    data = json.loads(
        command(
            [
                video_config.ffprobe,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(output),
            ],
            10,
        )
    )
    assert mime == "video/mp4"
    assert not any("location" in key.lower() for key in data["format"].get("tags", {}))
    assert data["streams"][0]["codec_name"] == "h264"


@pytest.mark.video
@pytest.mark.parametrize("seconds,valid", [(5, True), (31, False)])
def test_browser_webm_without_duration_header(video_config, tmp_path, seconds, valid, monkeypatch):
    raw = command(
        [
            video_config.ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:r=10",
            "-t",
            str(seconds),
            "-c:v",
            "libvpx",
            "-live",
            "1",
            "-f",
            "webm",
            "pipe:1",
        ],
        30,
    )
    source = tmp_path / "browser.webm"
    source.write_bytes(raw)
    probed = json.loads(
        command(
            [video_config.ffprobe, "-v", "error", "-show_format", "-of", "json", str(source)], 10
        )
    )
    assert "webm" in probed["format"]["format_name"]
    # FFprobe may infer duration from packets even when the EBML Duration element
    # is absent. The streaming file itself must not contain that element.
    assert b"\x44\x89\x88" not in raw

    # Some FFprobe versions infer duration, others don't. Exercise the latter with
    # the real streaming WebM and real decoder; remove only inferred probe timing.
    def no_inferred_duration(args, timeout):
        result = command(args, timeout)
        if "-show_streams" in args:
            metadata = json.loads(result)
            metadata["format"].pop("duration", None)
            return json.dumps(metadata).encode()
        return result

    monkeypatch.setattr("app.services.media.command", no_inferred_duration)
    if valid:
        output, mime = sanitize_video(source, tmp_path, video_config)
        assert output.exists() and mime == "video/webm"
    else:
        with pytest.raises(Problem) as exc:
            sanitize_video(source, tmp_path, video_config)
        assert exc.value.code == "invalid_duration"


@pytest.mark.video
def test_actual_unsupported_codec(video_config, tmp_path):
    source = tmp_path / "unsupported.mp4"
    command(
        [
            video_config.ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=s=64x64:r=10",
            "-t",
            "5",
            "-c:v",
            "mpeg4",
            "-y",
            str(source),
        ],
        30,
    )
    with pytest.raises(Problem) as exc:
        sanitize_video(source, tmp_path, video_config)
    assert exc.value.code == "invalid_media"


@pytest.mark.storage
def test_actual_minio_private_roundtrip_and_signed_expiry(config, tmp_path):
    if not os.getenv("TEST_S3_ENDPOINT"):
        pytest.skip("TEST_S3_ENDPOINT required for real MinIO")
    config.s3_endpoint = os.environ["TEST_S3_ENDPOINT"]
    storage = S3Storage(config)
    storage.ready()
    key = f"integration/{uuid.uuid4().hex}"
    path = tmp_path / "image"
    path.write_bytes(photo())
    try:
        storage.put(key, path, "image/jpeg")
        with httpx.Client(timeout=10, trust_env=False) as client:
            assert client.get(f"{config.s3_endpoint}/{config.s3_bucket}/{key}").status_code == 403
            signed = client.get(storage.sign(key, 120))
            assert signed.status_code == 200 and signed.content == path.read_bytes()
            from datetime import UTC, datetime, timedelta

            from botocore.auth import S3SigV4QueryAuth

            # Generate an already expired signature without waiting for wall time.
            from botocore.awsrequest import AWSRequest
            from botocore.credentials import Credentials

            class ExpiredAuth(S3SigV4QueryAuth):
                def _modify_request_before_signing(self, request):
                    request.context["timestamp"] = (
                        datetime.now(UTC) - timedelta(minutes=10)
                    ).strftime("%Y%m%dT%H%M%SZ")
                    super()._modify_request_before_signing(request)

            request = AWSRequest(method="GET", url=f"{config.s3_endpoint}/{config.s3_bucket}/{key}")
            ExpiredAuth(
                Credentials(config.s3_access_key, config.s3_secret_key),
                "s3",
                config.s3_region,
                expires=1,
            ).add_auth(request)
            assert client.get(request.url).status_code == 403
    finally:
        storage.delete(key)
        storage.delete(key)


@pytest.mark.integration
@pytest.mark.storage
@pytest.mark.video
def test_two_user_smoke_actual_minio_photo_video_gallery(
    client, admin, application, config, video_config, tmp_path
):
    from fastapi.testclient import TestClient

    from tests.conftest import login

    if not os.getenv("TEST_S3_ENDPOINT"):
        pytest.skip("TEST_S3_ENDPOINT required for real MinIO smoke")
    config.s3_endpoint = os.environ["TEST_S3_ENDPOINT"]
    config.ffmpeg, config.ffprobe = video_config.ffmpeg, video_config.ffprobe
    application.state.storage = S3Storage(config)
    _, group = admin
    token = client.post(f"/groups/{group}/invites", json={}).json()["token"]
    posts = []
    try:
        capture = upload(client, group, photo("yellow"))
        assert capture.status_code == 200
        posts.append(capture.json()["id"])
        with TestClient(application) as friend:
            login(friend, "friend")
            assert friend.post("/groups/join", json={"token": token}).status_code == 200
            video = make_video(video_config, tmp_path / "smoke.mp4", 5)
            accepted = upload(friend, group, video, kind="video")
            assert accepted.status_code == 200, accepted.text
            posts.append(accepted.json()["id"])
            gallery = upload(friend, group, photo("blue"), gallery=True)
            assert gallery.status_code == 200 and gallery.json()["points"] == 0
            posts.append(gallery.json()["id"])
        feed = client.get(f"/groups/{group}/feed").json()
        assert len(feed["items"]) == 3
        ranks = client.get(f"/groups/{group}/leaderboard").json()["items"]
        assert [r["points"] for r in ranks] == [3, 1]
        assert ranks[0]["capture_videos"] == ranks[0]["gallery_photos"] == 1
        media = client.get(f"/groups/{group}/posts/{posts[0]}/media").json()
        assert httpx.get(media["url"], timeout=10, trust_env=False).status_code == 200
    finally:
        for post in posts:
            client.delete(f"/groups/{group}/posts/{post}")
        from app.services.uploads import UploadService

        UploadService(
            application.state.factory, application.state.storage, application.state.clock, config
        ).cleanup()
