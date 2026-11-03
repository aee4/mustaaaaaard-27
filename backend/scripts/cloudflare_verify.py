"""Isolated operator acceptance; credential input and media never enter logs.

Run with a short-lived Neon connection supplied through hidden stdin. Reuses only
the existing Google owner and dedicated Deployment verification group. Keeps all
original sessions/posts intact; removes only this run's synthetic objects/posts.
"""

import getpass
import io
import json
import secrets
import struct
import subprocess
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import boto3
import httpx
from botocore.config import Config
from dotenv import dotenv_values
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.entities import Group, LoginSession, Membership, Post, Upload, User
from app.services.identity import digest, login

ORIGIN = "https://mustaaaaaard-27.eeyramagbetor.workers.dev"
RENDER = "https://mustaaaaaard-27.onrender.com"
INITIAL = uuid.UUID("bad0f3b9-c9ff-4c6f-a563-56575993e367")


def run() -> None:
    raw = json.loads(getpass.getpass("Verification connection JSON (hidden): "))
    url = raw["database_url"].replace("postgresql://", "postgresql+psycopg://", 1)
    factory = sessionmaker(create_engine(url, pool_pre_ping=True), expire_on_commit=False)
    local = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    storage = boto3.client(
        "s3",
        endpoint_url="https://8b158add944122fbd78f9d7ff7dbed01.r2.cloudflarestorage.com",
        aws_access_key_id=local["S3_ACCESS_KEY"],
        aws_secret_access_key=local["S3_SECRET_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    bucket = "mustaaaaaard-production"
    storage.head_bucket(Bucket=bucket)
    with factory() as db:
        user = db.scalar(
            select(User)
            .join(Membership)
            .where(
                Membership.group_id == INITIAL,
                Membership.role == "admin",
                Membership.removed_at.is_(None),
                User.subject.startswith("google:"),
            )
        )
        assert user is not None
        group = db.scalar(select(Group).where(Group.name.startswith("Deployment verification")))
        assert group is not None
        assert db.get(Membership, (group.id, user.id)).removed_at is None
        originals = set(
            db.scalars(select(Post.id).where(Post.group_id == INITIAL, Post.removed_at.is_(None)))
        )
        sessions = set(
            db.scalars(
                select(LoginSession.token_hash).where(
                    LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None)
                )
            )
        )
    if raw.get("preflight"):
        print(
            "preflight=existing_Google_owner,verification_group,Neon_TLS,R2_credentials_verified",
            flush=True,
        )
        return
    _, temporary, cookie = login(factory, user.subject, user.display_name, datetime.now(UTC), 2400)
    client = httpx.Client(base_url=ORIGIN, timeout=240, follow_redirects=False)
    client.cookies.set(
        "mustard_session", cookie, domain="mustaaaaaard-27.eeyramagbetor.workers.dev", path="/"
    )
    headers = {"Origin": ORIGIN, "X-CSRF-Token": temporary.csrf}
    created = []
    invite_id = None

    def request(method: str, path: str, **kwargs):
        response = client.request(method, "/api" + path, headers=headers, **kwargs)
        assert response.status_code < 400, f"API status {response.status_code}"
        assert "no-store" in response.headers["cache-control"]
        return response.json()

    g = f"/groups/{group.id}"
    try:
        assert request("GET", "/auth/session")["user"]["id"] == str(user.id)
        assert client.post("/api/me", json={"display_name": "must not change"}).status_code in {
            403,
            405,
        }
        assert (
            client.patch(
                "/api/me", headers={"Origin": ORIGIN}, json={"display_name": "must not change"}
            ).status_code
            == 403
        )
        assert httpx.get(ORIGIN + "/api/auth/session").status_code == 401
        assert (
            client.post(
                "/api/auth/dev",
                headers={"Origin": ORIGIN},
                json={"subject": "forbidden", "display_name": "forbidden"},
            ).status_code
            == 404
        )
        baseline = request("GET", g + "/leaderboard?period=all")["items"]
        invite = request("POST", g + "/invites", json={"max_uses": 1, "expires_in_hours": 1})
        invite_id = invite["id"]
        assert request("POST", "/groups/join", json={"token": invite["token"]})["id"] == str(
            group.id
        )
        image = Image.frombytes("RGB", (64, 64), secrets.token_bytes(64 * 64 * 3))
        photo = io.BytesIO()
        image.save(photo, "PNG")
        ffmpeg = (
            Path(__file__).resolve().parents[2]
            / ".tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe"
        )
        with tempfile.TemporaryDirectory(prefix="mustard-gateway-") as directory:
            target = Path(directory) / "synthetic.mp4"
            subprocess.run(
                [
                    str(ffmpeg),
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=0x{secrets.token_hex(3)}:s=320x240:r=15",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:sample_rate=48000",
                    "-t",
                    "6",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-y",
                    str(target),
                ],
                check=True,
                capture_output=True,
            )
            video_bytes = target.read_bytes()
            padding = 50 * 1024 * 1024 - len(video_bytes)
            video_bytes += struct.pack(">I4s", padding, b"free") + b"\0" * (padding - 8)
            for kind, data, source, points in [
                ("photo", photo.getvalue(), "capture", 1),
                ("video", video_bytes, "capture", 3),
                ("photo", photo.getvalue() + secrets.token_bytes(16), "gallery", 0),
            ]:
                path = g + "/gallery"
                if source == "capture":
                    capture = request("POST", g + "/captures", json={"kind": kind})
                    path = g + f"/captures/{capture['id']}/upload"
                key = str(uuid.uuid4())
                upload_headers = {**headers, "Idempotency-Key": key}
                fields = {"caption": "Gateway synthetic\r\nplain <text>"}
                files = {
                    "file": (
                        "synthetic.png" if kind == "photo" else "synthetic.mp4",
                        data,
                        "image/png" if kind == "photo" else "video/mp4",
                    )
                }
                response = client.post(
                    "/api" + path + "?kind=" + kind,
                    headers=upload_headers,
                    data=fields,
                    files=files,
                )
                assert response.status_code == 200, f"Upload status {response.status_code}"
                post = response.json()
                created.append(post["id"])
                assert post["points"] == points
                assert post["caption"] == "Gateway synthetic\nplain <text>"
                replay = client.post(
                    "/api" + path + "?kind=" + kind,
                    headers=upload_headers,
                    data=fields,
                    files=files,
                )
                assert replay.status_code == 200 and replay.json()["id"] == post["id"]
                media = request("GET", g + f"/posts/{post['id']}/media")
                playback = httpx.get(
                    media["url"], headers={"Origin": ORIGIN, "Range": "bytes=0-127"}, timeout=30
                )
                assert playback.status_code == 206
                assert playback.headers["access-control-allow-origin"] == ORIGIN
                assert "no-store" in playback.headers["cache-control"]
                assert httpx.get(media["url"].split("?")[0], timeout=30).status_code >= 400
            if raw.get("slow", True):
                key = str(uuid.uuid4())
                slow_data = photo.getvalue() + secrets.token_bytes(16)
                files = {"file": ("slow.png", slow_data, "image/png")}
                built = client.build_request(
                    "POST", "/api" + g + "/gallery?kind=photo", files=files
                )
                payload = built.read()

                def chunks():
                    size = (len(payload) + 129) // 130
                    for start in range(0, len(payload), size):
                        yield payload[start : start + size]
                        time.sleep(1)

                print(
                    "long_stream_test=starting_approximately_130_seconds_no_database_transaction",
                    flush=True,
                )
                started = time.monotonic()
                try:
                    slow = client.post(
                        "/api" + g + "/gallery?kind=photo",
                        headers={
                            **headers,
                            "Idempotency-Key": key,
                            "Content-Type": built.headers["Content-Type"],
                            "Content-Length": str(len(payload)),
                        },
                        content=chunks(),
                    )
                    outcome = str(slow.status_code)
                except httpx.HTTPError as exc:
                    outcome = type(exc).__name__
                elapsed = round(time.monotonic() - started, 1)
                replay = client.post(
                    "/api" + g + "/gallery?kind=photo",
                    headers={**headers, "Idempotency-Key": key},
                    files=files,
                )
                assert replay.status_code == 200
                created.append(replay.json()["id"])
                print(
                    f"long_stream_status={outcome} elapsed_seconds={elapsed} same_key_recovery=200",
                    flush=True,
                )
            assert len(request("GET", g + "/feed")["items"]) >= 3
            for period in ["weekly", "all"]:
                own = next(
                    row
                    for row in request("GET", g + "/leaderboard?period=" + period)["items"]
                    if row["user"]["id"] == str(user.id)
                )
                assert own["points"] == 4
            browser_check = subprocess.run(
                [
                    "node",
                    str(
                        Path(__file__).resolve().parents[2]
                        / "frontend/scripts/check-cloudflare-session.mjs"
                    ),
                ],
                input=json.dumps(
                    {"cookie": cookie, "group": str(group.id), "post": created[1]}
                ).encode(),
                capture_output=True,
                check=True,
                timeout=90,
            )
            print(browser_check.stdout.decode().strip(), flush=True)
            p = g + f"/posts/{created[0]}"
            assert request("PUT", p + "/like")["like_count"] == 1
            assert request("PUT", p + "/like")["like_count"] == 1
            assert request("DELETE", p + "/like")["like_count"] == 0
            comment_key = str(uuid.uuid4())
            comment_headers = {**headers, "Idempotency-Key": comment_key}
            c = client.post(
                "/api" + p + "/comments",
                headers=comment_headers,
                json={"text": "Synthetic <plain> comment"},
            ).json()
            retry = client.post(
                "/api" + p + "/comments",
                headers=comment_headers,
                json={"text": "Synthetic <plain> comment"},
            ).json()
            assert c["id"] == retry["id"]
            request("DELETE", p + f"/comments/{c['id']}")
        print(
            "gateway_acceptance=session,CSRF,invite,photo1,video3,gallery0,replay,feed,ranks,likes,comments,private_Range_CORS",
            flush=True,
        )
    finally:
        for identifier in created:
            request("DELETE", g + f"/posts/{identifier}")
            with factory() as db:
                post = db.get(Post, uuid.UUID(identifier))
                upload = db.get(Upload, post.upload_id)
                key = upload.object_key
                upload_id = upload.id
                assert post.removed_at and post.caption is None
            storage.delete_object(Bucket=bucket, Key=key)
            try:
                storage.head_object(Bucket=bucket, Key=key)
                raise AssertionError("Synthetic object remained")
            except storage.exceptions.ClientError as exc:
                assert exc.response["ResponseMetadata"]["HTTPStatusCode"] == 404
            with factory.begin() as db:
                db.get(Upload, upload_id).storage_bytes = 0
        if invite_id:
            request("DELETE", g + f"/invites/{invite_id}")
        if created:
            assert request("GET", g + "/leaderboard?period=all")["items"] == baseline
        with factory.begin() as db:
            db.get(LoginSession, digest(cookie)).revoked_at = datetime.now(UTC)
        with factory() as db:
            assert originals <= set(
                db.scalars(
                    select(Post.id).where(Post.group_id == INITIAL, Post.removed_at.is_(None))
                )
            )
            assert sessions <= set(
                db.scalars(
                    select(LoginSession.token_hash).where(
                        LoginSession.user_id == user.id, LoginSession.revoked_at.is_(None)
                    )
                )
            )
        print(
            f"cleanup=complete synthetic_posts={len(created)} original_posts_sessions=preserved",
            flush=True,
        )
        client.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("verification_failed=" + type(exc).__name__, flush=True)
        raise SystemExit(1) from None
