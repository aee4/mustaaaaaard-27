"""Upload only the public Vite artifact with a short-lived asset-session JWT on stdin.

Run from the repository root. This helper never loads application credentials.
The upload mode returns its completion JWT to the calling deployment tool; do not
run it with stdout logging. Manifest mode contains public paths/hashes only.
"""

import base64
import getpass
import hashlib
import json
import mimetypes
import sys
from pathlib import Path
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[2] / "frontend" / "dist"
files = {}
manifest = {}
for path in sorted(root.rglob("*")):
    if path.is_file() and path.name not in {"_headers", "_redirects"}:
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()[:32]
        files[digest] = (path, content)
        manifest["/" + path.relative_to(root).as_posix()] = {"hash": digest, "size": len(content)}

if sys.argv[1] == "manifest":
    print(json.dumps(manifest))
else:
    session = json.loads(getpass.getpass("Asset session JSON (hidden): "))
    token = session["jwt"]
    completion = token
    for bucket in session["buckets"]:
        boundary = "mustard-static-artifacts"
        parts = []
        for digest in bucket:
            path, content = files[digest]
            mime = {".js": "application/javascript", ".css": "text/css"}.get(
                path.suffix, mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            )
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{digest}"; filename="{digest}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
                + base64.b64encode(content)
                + b"\r\n"
            )
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        request = Request(
            "https://api.cloudflare.com/client/v4/accounts/8b158add944122fbd78f9d7ff7dbed01/workers/assets/upload?base64=true",
            data=body,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "multipart/form-data; boundary=" + boundary,
            },
        )
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
        if not result["success"]:
            raise SystemExit("Static asset upload failed")
        completion = result["result"].get("jwt", completion)
    print(json.dumps({"jwt": completion}))
