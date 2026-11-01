"""Real HTTP upload workload for a locally constrained backend; never production login."""

import argparse
import io
import json
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx
from PIL import Image


def run(
    base_url: str,
    directory: Path,
    results: list[dict[str, object]] | None = None,
    names: tuple[str, ...] = ("720p", "portrait720p", "720p-high"),
    verify_media: Callable[[httpx.Client, str, str, str], None] | None = None,
) -> list[dict[str, object]]:
    if not base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise ValueError("Synthetic development authentication is restricted to local test servers")
    results = results if results is not None else []
    with httpx.Client(
        base_url=base_url, timeout=250, headers={"Origin": base_url}, trust_env=False
    ) as client:
        response = client.post(
            "/api/auth/dev",
            json={
                "subject": "resource-" + uuid.uuid4().hex,
                "display_name": "Synthetic resource check",
            },
        )
        response.raise_for_status()
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        group = client.post(
            "/api/groups", json={"name": "Synthetic resources " + uuid.uuid4().hex}
        ).json()["id"]
        created = []
        try:
            for name in names:
                capture = client.post(f"/api/groups/{group}/captures", json={"kind": "video"})
                capture.raise_for_status()
                started = time.monotonic()
                try:
                    with (directory / f"{name}-50mib.mp4").open("rb") as media:
                        response = client.post(
                            f"/api/groups/{group}/captures/{capture.json()['id']}/upload?kind=video",
                            headers={"Idempotency-Key": str(uuid.uuid4())},
                            files={"file": ("synthetic.mp4", media, "video/mp4")},
                        )
                    item = {
                        "fixture": name,
                        "status": response.status_code,
                        "seconds": round(time.monotonic() - started, 2),
                    }
                    if response.status_code in {200, 201}:
                        body = response.json()
                        assert body["points"] == 3
                        created.append(body["id"])
                    else:
                        item["error"] = response.json().get("error", {}).get("code")
                    results.append(item)
                    if response.status_code in {200, 201} and verify_media is not None:
                        verify_media(client, group, body["id"], name)
                except httpx.HTTPError as exc:
                    results.append(
                        {
                            "fixture": name,
                            "error": type(exc).__name__,
                            "seconds": round(time.monotonic() - started, 2),
                        }
                    )
                print(json.dumps(results[-1]), flush=True)
            gallery = io.BytesIO()
            Image.new("RGB", (32, 32), (10, 180, 210)).save(gallery, format="PNG")
            response = client.post(
                f"/api/groups/{group}/gallery?kind=photo",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                files={"file": ("gallery.png", gallery.getvalue(), "image/png")},
            )
            if response.status_code in {200, 201}:
                assert response.json()["points"] == 0
                created.append(response.json()["id"])
            results.append({"fixture": "gallery-photo", "status": response.status_code})
            ranks = client.get(f"/api/groups/{group}/leaderboard?period=all").json()
            assert ranks["items"][0]["points"] == 3 * sum(
                r.get("status") in {200, 201} for r in results if r["fixture"] in names
            )
            assert client.get(f"/api/groups/{group}/feed").status_code == 200
        finally:
            for post in created:
                client.delete(f"/api/groups/{group}/posts/{post}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:58001")
    parser.add_argument(
        "--fixtures", type=Path, default=Path(__file__).resolve().parents[2] / ".tools/free-tier"
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result: list[dict[str, object]] = []
    try:
        run(args.base_url, args.fixtures, result)
    except Exception as exc:
        result.append({"fixture": "server-or-cleanup", "error": type(exc).__name__})
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    raise SystemExit(0 if all(r.get("status") in {200, 201} for r in result) else 1)
