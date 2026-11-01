"""Exercise a running local backend through real HTTP, with real photo/video bytes.

Bootstrap dev:handoff-admin before running. No tokens or signed URLs are printed.
"""

import argparse
import io
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image


def checked(response: httpx.Response, status: int = 200) -> dict:
    if response.status_code != status:
        # Server error envelopes contain no credentials; request headers are omitted.
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path}: "
            f"expected {status}, got {response.status_code}: {response.text}"
        )
    return response.json()


def authenticate(client: httpx.Client, subject: str, name: str) -> dict:
    session = checked(client.post("/auth/dev", json={"subject": subject, "display_name": name}))
    client.headers["X-CSRF-Token"] = session["csrf_token"]
    return session["user"]


def photo() -> bytes:
    output = io.BytesIO()
    Image.frombytes("RGB", (16, 16), os.urandom(16 * 16 * 3)).save(output, "PNG")
    return output.getvalue()


def send_media(
    client: httpx.Client, group: str, data: bytes, kind: str, *, gallery: bool = False
) -> dict:
    if gallery:
        path = f"/groups/{group}/gallery"
    else:
        capture = checked(client.post(f"/groups/{group}/captures", json={"kind": kind}), 201)
        path = f"/groups/{group}/captures/{capture['id']}/upload"
    return checked(
        client.post(
            path,
            params={"kind": kind},
            headers={"Idempotency-Key": str(uuid.uuid4())},
            files={"file": ("smoke-media", data, "application/octet-stream")},
        )
    )


def run(base_url: str, admin_subject: str) -> dict:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Smoke workflow is restricted to a local development HTTP server")
    posts: list[str] = []
    group = invite_id = friend_id = None
    headers = {"Origin": "http://localhost:3000"}
    with (
        httpx.Client(base_url=base_url, headers=headers, timeout=240, trust_env=False) as admin,
        httpx.Client(base_url=base_url, headers=headers, timeout=240, trust_env=False) as friend,
    ):
        assert checked(admin.get("/ready")) == {"ok": True}
        alice = authenticate(admin, admin_subject, "Handoff Alice")
        groups = checked(admin.get("/groups"))
        eligible = [g for g in groups if g["name"] == "Mustaaaaaard ’27" and g["role"] == "admin"]
        if len(eligible) != 1:
            raise RuntimeError(f"Bootstrap dev:{admin_subject} using the admin CLI first")
        group = eligible[0]["id"]
        try:
            invite = checked(admin.post(f"/groups/{group}/invites", json={"max_uses": 1}), 201)
            invite_id = invite["id"]
            bob = authenticate(friend, "smoke-" + uuid.uuid4().hex, "Handoff Bob")
            checked(friend.post("/groups/join", json={"token": invite["token"]}))
            friend_id = bob["id"]

            capture_photo = send_media(admin, group, photo(), "photo")
            posts.append(capture_photo["id"])
            assert capture_photo["source"] == "capture" and capture_photo["points"] == 1
            with tempfile.TemporaryDirectory(prefix="mustard-smoke-") as temporary:
                video_path = Path(temporary) / "video.mp4"
                subprocess.run(
                    [
                        os.getenv("FFMPEG", "ffmpeg"),
                        "-nostdin",
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "color=c=yellow:s=64x64:r=10",
                        "-t",
                        "5",
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-metadata",
                        f"comment={uuid.uuid4()}",
                        "-y",
                        str(video_path),
                    ],
                    check=True,
                    timeout=30,
                    capture_output=True,
                )
                capture_video = send_media(friend, group, video_path.read_bytes(), "video")
            posts.append(capture_video["id"])
            assert capture_video["source"] == "capture" and capture_video["points"] == 3
            gallery = send_media(friend, group, photo(), "photo", gallery=True)
            posts.append(gallery["id"])
            assert gallery["source"] == "gallery" and gallery["points"] == 0

            feed = checked(admin.get(f"/groups/{group}/feed"))
            assert {p["id"] for p in feed["items"]} == set(posts)
            for period in ("weekly", "all"):
                ranking = checked(
                    admin.get(f"/groups/{group}/leaderboard", params={"period": period})
                )
                rows = {row["user"]["id"]: row for row in ranking["items"]}
                assert ranking["total"] == 2
                assert [row["points"] for row in ranking["items"]] == [3, 1]
                assert [row["rank"] for row in ranking["items"]] == [1, 2]
                assert rows[alice["id"]]["points"] == 1
                assert rows[bob["id"]]["points"] == 3
                assert rows[alice["id"]]["capture_photos"] == 1
                assert rows[bob["id"]]["capture_videos"] == 1
                assert rows[bob["id"]]["gallery_photos"] == 1
                assert rows[bob["id"]]["streak"]["current"] == 1
            media = checked(admin.get(f"/groups/{group}/posts/{capture_photo['id']}/media"))
            with httpx.Client(timeout=15, trust_env=False) as storage:
                assert storage.get(media["url"]).status_code == 200
                unsigned = media["url"].split("?", 1)[0]
                assert storage.get(unsigned).status_code == 403
            return {
                "readiness": 200,
                "users": 2,
                "groups": 1,
                "capture_photo_points": 1,
                "capture_video_points": 3,
                "gallery_points": 0,
                "feed_posts": 3,
                "weekly_points": [3, 1],
                "all_time_points": [3, 1],
                "signed_media": 200,
                "unsigned_media": 403,
            }
        finally:
            for post in posts:
                checked(admin.delete(f"/groups/{group}/posts/{post}"))
            if invite_id:
                checked(admin.delete(f"/groups/{group}/invites/{invite_id}"))
            if friend_id:
                checked(admin.delete(f"/groups/{group}/members/{friend_id}"))
                checked(friend.post("/auth/logout"))
            checked(admin.post("/auth/logout"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:58000")
    parser.add_argument("--admin-subject", default="handoff-admin")
    args = parser.parse_args()
    print(json.dumps(run(args.base_url, args.admin_subject), indent=2))
