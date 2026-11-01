"""Single process container entry; trust only explicitly configured proxy peers."""

import json
import os
import threading
import time

import uvicorn

if __name__ == "__main__":
    # Render provides the allocated provider URL; keep OAuth and API same-origin.
    if os.environ.get("RENDER_EXTERNAL_URL"):
        os.environ.setdefault("BASE_URL", os.environ["RENDER_EXTERNAL_URL"].rstrip("/"))
        os.environ.setdefault("ALLOWED_ORIGINS", json.dumps([os.environ["BASE_URL"]]))
    if os.environ.get("RUN_RELEASE_ON_START", "false").lower() == "true":
        from scripts.release import release

        release()
    if os.environ.get("CLEANUP_WHILE_AWAKE", "false").lower() == "true":

        def cleanup_awake() -> None:
            from app.cli import cleanup

            while True:
                try:
                    cleanup(limit=100)
                except Exception:
                    # No secrets, media keys or signed URLs in diagnostics.
                    print("cleanup_deferred", flush=True)
                time.sleep(3600)

        threading.Thread(target=cleanup_awake, daemon=True).start()
    peers = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
    if "*" in peers:
        raise SystemExit("Use explicit trusted proxy IPs/CIDRs, not a wildcard")
    uvicorn.run(
        "app.web:production_app",
        factory=True,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "10000")),
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips=peers,
        limit_concurrency=16,
        timeout_graceful_shutdown=240,
    )
