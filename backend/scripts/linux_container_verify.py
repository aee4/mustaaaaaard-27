"""Local synthetic CI only. Fail closed on missing cgroup evidence; no raw logs/URLs."""

import argparse
import io
import json
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
from PIL import Image

from scripts.resource_smoke import run

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:58001"
MEMORY = 512 * 1024 * 1024
FILES = (
    "memory.current",
    "memory.peak",
    "memory.max",
    "memory.swap.max",
    "memory.events",
    "cpu.max",
    "cpu.stat",
)


def execute(args, *, input=None, timeout=30, check=True):
    return subprocess.run(
        args, input=input, capture_output=True, check=check, timeout=timeout
    ).stdout


def snapshot(container):
    # The kernel peak includes uv/Python, all FFmpeg/FFprobe children, temporary
    # file page cache and this tiny diagnostic interpreter, not only the encoder.
    code = (
        "import json;from pathlib import Path;"
        f"print(json.dumps({{n:Path('/sys/fs/cgroup',n).read_text().strip() for n in {FILES!r}}}))"
    )
    state = json.loads(
        execute(
            [
                "docker",
                "inspect",
                "--format",
                '{"running":{{.State.Running}},"oom_killed":{{.State.OOMKilled}},'
                '"exit_code":{{.State.ExitCode}},"restarts":{{.RestartCount}}}',
                container,
            ]
        )
    )
    usage = (
        json.loads(execute(["docker", "exec", container, "/srv/.venv/bin/python", "-c", code]))
        if state["running"]
        else {}
    )
    return {"cgroup": usage, "state": state}


def validate_snapshot(sample):
    values, state = sample["cgroup"], sample["state"]
    # Manual restart is an explicit later phase; preserve restart counters without
    # treating that intentional recovery action as an automatic-restart failure.
    assert state["running"] and not state["oom_killed"]
    assert int(values["memory.max"]) == MEMORY
    assert int(values["memory.swap.max"]) == 0
    assert 0 < int(values["memory.peak"]) <= MEMORY
    quota, period = map(int, values["cpu.max"].split())
    assert abs(quota / period - 0.1) < 0.00001
    events = dict(line.split() for line in values["memory.events"].splitlines())
    assert int(events["oom"]) == int(events["oom_kill"]) == 0


def wait_ready(deadline=180):
    started = time.monotonic()
    with httpx.Client(timeout=6, trust_env=False) as client:
        while time.monotonic() - started < deadline:
            try:
                if client.get(BASE + "/api/ready").status_code == 200:
                    return round(time.monotonic() - started, 2)
            except httpx.HTTPError:
                pass
            time.sleep(1)
    raise TimeoutError("readiness_deadline")


def login(client):
    response = client.post(
        "/api/auth/dev",
        json={"subject": "linux-" + uuid.uuid4().hex, "display_name": "Synthetic CI"},
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    response = client.post("/api/groups", json={"name": "Synthetic CI " + uuid.uuid4().hex})
    assert response.status_code in {200, 201}
    return response.json()["id"]


def failure_recovery():
    with httpx.Client(
        base_url=BASE, headers={"Origin": BASE}, timeout=30, trust_env=False
    ) as client:
        group = login(client)
        capture = client.post(f"/api/groups/{group}/captures", json={"kind": "photo"}).json()["id"]
        path = f"/api/groups/{group}/captures/{capture}/upload?kind=photo"
        bad_key = str(uuid.uuid4())
        for _ in range(2):
            bad = client.post(
                path,
                headers={"Idempotency-Key": bad_key},
                files={"file": ("bad.png", b"not media", "image/png")},
            )
            assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_media"
        image = io.BytesIO()
        Image.new("RGB", (32, 32), (33, 77, 99)).save(image, format="PNG")
        headers = {"Idempotency-Key": str(uuid.uuid4())}
        files = {"file": ("valid.png", image.getvalue(), "image/png")}
        post = None
        try:
            accepted = client.post(path, headers=headers, files=files)
            assert accepted.status_code == 200
            post = accepted.json()["id"]
            assert accepted.json()["points"] == 1
            replay = client.post(path, headers=headers, files=files)
            assert replay.status_code == 200 and replay.json()["id"] == post
            assert len(client.get(f"/api/groups/{group}/feed").json()["items"]) == 1
        finally:
            if post:
                assert client.delete(f"/api/groups/{group}/posts/{post}").status_code in {200, 204}
    return {
        "invalid_retries": 2,
        "recovered": True,
        "capture_preserved": True,
        "accepted_replay_unique": True,
    }


def processor_recovery(container):
    """Kill only an FFmpeg child in this disposable container; retry identical input/key."""
    with httpx.Client(
        base_url=BASE, headers={"Origin": BASE}, timeout=200, trust_env=False
    ) as client:
        group = login(client)
        capture = client.post(f"/api/groups/{group}/captures", json={"kind": "video"}).json()["id"]
        path = f"/api/groups/{group}/captures/{capture}/upload?kind=video"
        key = {"Idempotency-Key": str(uuid.uuid4())}

        def upload_video():
            with (ROOT / ".tools/free-tier/720p-high-50mib.mp4").open("rb") as source:
                return client.post(
                    path, headers=key, files={"file": ("synthetic.mp4", source, "video/mp4")}
                )

        children = """import os,signal
from pathlib import Path
found=[]
for path in Path('/proc').iterdir():
    if path.name.isdigit():
        try:
            if path.joinpath('comm').read_text().strip()=='ffmpeg':
                found.append(int(path.name))
        except FileNotFoundError:
            pass
"""
        find = children + "print(bool(found))"
        kill = children + "assert found\nfor pid in found: os.kill(pid,signal.SIGKILL)"
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(upload_video)
            started = time.monotonic()
            while time.monotonic() - started < 60:
                if (
                    execute(
                        ["docker", "exec", container, "/srv/.venv/bin/python", "-c", find]
                    ).strip()
                    == b"True"
                ):
                    break
                assert not future.done()
                time.sleep(0.25)
            else:
                raise TimeoutError("ffmpeg_child_not_observed")
            image = io.BytesIO()
            Image.new("RGB", (33, 33), (17, 29, 71)).save(image, format="PNG")
            photo_key = {"Idempotency-Key": str(uuid.uuid4())}
            photo_path = f"/api/groups/{group}/gallery?kind=photo"
            photo_files = {"file": ("busy.png", image.getvalue(), "image/png")}
            busy = client.post(photo_path, headers=photo_key, files=photo_files)
            assert busy.status_code == 503 and busy.json()["error"]["code"] == "media_busy"
            execute(["docker", "exec", container, "/srv/.venv/bin/python", "-c", kill])
            failed = future.result(timeout=45)
            assert (
                failed.status_code == 503
                and failed.json()["error"]["code"] == "media_resources_exhausted"
            )
        posts = []
        try:
            recovered = upload_video()
            assert recovered.status_code == 200 and recovered.json()["points"] == 3
            posts.append(recovered.json()["id"])
            replay = upload_video()
            assert replay.status_code == 200 and replay.json()["id"] == posts[0]
            photo = client.post(photo_path, headers=photo_key, files=photo_files)
            assert photo.status_code == 200 and photo.json()["points"] == 0
            posts.append(photo.json()["id"])
            assert len(client.get(f"/api/groups/{group}/feed").json()["items"]) == 2
        finally:
            for post in posts:
                assert client.delete(f"/api/groups/{group}/posts/{post}").status_code in {200, 204}
    return {
        "child_sigkill_status": 503,
        "busy_status": 503,
        "same_key_recovered": True,
        "accepted_replay_unique": True,
    }


def playback(client, group, post, name, results):
    response = client.get(f"/api/groups/{group}/posts/{post}/media")
    assert response.status_code == 200
    url = response.json()["url"]
    assert urlsplit(url).hostname in {"127.0.0.1", "localhost"}
    unsigned = urlunsplit(urlsplit(url)._replace(query=""))
    with httpx.Client(timeout=15, trust_env=False) as storage_client:
        assert storage_client.get(unsigned).status_code == 403
    result = json.loads(
        execute(
            ["node", str(ROOT / "frontend/scripts/check-container-media.mjs")],
            input=json.dumps({"base": BASE, "url": url}).encode(),
            timeout=60,
            check=False,
        )
    )
    result = {
        key: result[key]
        for key in ("passed", "failure", "width", "height", "duration")
        if key in result
    }
    results.append({"fixture": name, **result, "unsigned_status": 403})
    assert result["passed"] and 5 <= result["duration"] <= 30.1
    assert (
        0 < min(result["width"], result["height"]) <= 720
        and max(result["width"], result["height"]) <= 1280
    )
    if name in {"720p", "portrait720p", "720p-high"}:
        assert (result["width"], result["height"]) == (
            (720, 1280) if name == "portrait720p" else (1280, 720)
        )
        assert abs(result["duration"] - 30) < 0.1


def small_webm(playbacks):
    with httpx.Client(
        base_url=BASE, headers={"Origin": BASE}, timeout=180, trust_env=False
    ) as client:
        group = login(client)
        for name in ("vp8-opus", "vp9-vorbis"):
            with (ROOT / f".tools/frontend-{name}.webm").open("rb") as source:
                response = client.post(
                    f"/api/groups/{group}/gallery?kind=video",
                    headers={"Idempotency-Key": str(uuid.uuid4())},
                    files={"file": ("synthetic.webm", source, "video/webm")},
                )
            assert response.status_code == 200 and response.json()["points"] == 0
            post = response.json()["id"]
            try:
                playback(client, group, post, name, playbacks)
            finally:
                assert client.delete(f"/api/groups/{group}/posts/{post}").status_code in {200, 204}


def lifecycle(container):
    # Never publish tracebacks, access logs, inspect.Env, request bodies or URLs.
    raw = execute(["docker", "logs", container]).decode(errors="replace")
    allowed = ("Release migrations applied; no development data imported", "cleanup_deferred")
    events = []
    for line in raw.splitlines():
        if line in allowed:
            events.append(line)
    return events


def verify(container, destination):
    report = {
        "passed": False,
        "platform": "Linux Docker cgroup v2; approximates Render",
        "stage": "startup",
        "snapshots": [],
        "uploads": [],
        "playbacks": [],
    }
    stop = threading.Event()
    probes = []

    def monitor():
        with httpx.Client(timeout=6, trust_env=False) as client:
            while not stop.is_set():
                started = time.monotonic()
                try:
                    status = client.get(BASE + "/api/ready").status_code
                except httpx.HTTPError:
                    status = 0
                probes.append({"status": status, "seconds": round(time.monotonic() - started, 3)})
                stop.wait(2)

    thread = None
    try:
        report["image_id"] = (
            execute(["docker", "inspect", "--format", "{{.Image}}", container]).decode().strip()
        )
        report["ffmpeg_version"] = (
            execute(["docker", "exec", container, "ffmpeg", "-version"]).decode().splitlines()[0]
        )
        report["initial_readiness_seconds"] = wait_ready()
        first = snapshot(container)
        validate_snapshot(first)
        report["snapshots"].append(first)
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        report["stage"] = "maximum_uploads_and_playback"
        assert all(
            (ROOT / f".tools/free-tier/{name}-50mib.mp4").stat().st_size == 50 * 1024 * 1024
            for name in ("720p", "portrait720p", "720p-high")
        )
        run(
            BASE,
            ROOT / ".tools/free-tier",
            report["uploads"],
            verify_media=lambda c, g, p, n: playback(c, g, p, n, report["playbacks"]),
        )
        assert len(report["uploads"]) == 4
        assert all(
            item["status"] == 200 and item.get("seconds", 0) <= 180 for item in report["uploads"]
        )
        report["stage"] = "webm_playback"
        small_webm(report["playbacks"])
        report["stage"] = "validation_failure_recovery"
        report["failure_recovery"] = failure_recovery()
        report["stage"] = "processor_failure_recovery"
        report["processor_recovery"] = processor_recovery(container)
        stop.set()
        thread.join(timeout=10)
        assert probes and all(probe["status"] == 200 for probe in probes)
        before_restart = snapshot(container)
        report["snapshots"].append(before_restart)
        validate_snapshot(before_restart)
        report["stage"] = "restart_recovery"
        execute(["docker", "restart", "--time", "10", container], timeout=40)
        report["restart_readiness_seconds"] = wait_ready()
        report["post_restart_recovery"] = failure_recovery()
        final = snapshot(container)
        report["snapshots"].append(final)
        validate_snapshot(final)
        report["stage"], report["passed"] = "complete", True
    except Exception as exc:
        report["failure_type"] = type(exc).__name__  # no exception text/locals
    finally:
        stop.set()
        if thread:
            thread.join(timeout=10)
        report["readiness_probes"] = probes
        try:
            last = snapshot(container)
            report["snapshots"].append(last)
            validate_snapshot(last)
            report["lifecycle"] = lifecycle(container)
        except Exception as exc:
            report["passed"] = False
            report["diagnostic_failure_type"] = type(exc).__name__
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.container, args.report) else 1)
