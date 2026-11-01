# Frontend verification — 2026-11-01

## 720p remux update

Current verification: 116 backend tests, 20 frontend unit tests, and 8 real-backend
Chrome integration tests passed; lint/format/typing/migration checks and production
build passed. The new integration test uploads supported MP4 and VP8/VP9 WebM,
plays remuxed media through private signed MinIO URLs and confirms unsigned=403.
Capture still uses synthetic camera/audio; no physical Android/iPhone or Safari
verification is claimed. See [video-processing.md](video-processing.md) for exact
formats, 720p rules, metadata checks, Windows results and the pending Linux gate.

## Earlier local acceptance update

Optional captions have since been added through migration 0002, validation,
caption-sensitive idempotency, generated API types, preview input and feed display.
Current affected checks: backend 79 passed; frontend 13 unit and 5 real-backend browser
tests passed; lint/type/build/audit passed. Visual changes and exact evidence are
in [local-acceptance.md](local-acceptance.md). App left running at localhost:3000.
Physical phones remain unverified; see [phone-https.md](phone-https.md).

The initial frontend verification below is retained as historical evidence.

Frontend implemented in frontend/ using React 19.3.1, TypeScript 5.9.3, Vite 8.3.5,
Tailwind 4.3.3 and TanStack Query 5.105.1; npm lockfile provided. API types
generated with openapi-typescript 7.13.0 from docs/openapi.json. Actual running
FastAPI OpenAPI compared equal to that snapshot (20 paths). No endpoint, caption,
avatar or authoritative scoring field was invented. Backend code/tests preserved.

## Actual checks

| Check | Observed result |
|---|---|
| npm run lint | Passed, no lint warnings |
| npm run typecheck | Passed |
| npm test | 13 passed across 3 files |
| npm run build | Passed; static assets in dist/ |
| npm run generate:api | Passed using updated lock/override |
| npm audit | Zero vulnerabilities |
| npm run test:e2e | 5 passed against real backend |
| npm run test:production | Passed against compiled production preview |
| uv run --directory backend pytest -q | 65 passed, no skips, 2 existing warnings in 13.92s |
| Backend Ruff/format/mypy | Passed; 45 Python files formatted, 23 app files typed |

Tests used native PostgreSQL 18 (127.0.0.1:55432), source-built MinIO
(127.0.0.1:59000), FFmpeg/FFprobe 9.0.2, Uvicorn (58000), and Vite dev/preview
(localhost:3000). Development admin dev:alice was explicitly bootstrapped in the
disposable mustard_handoff_test database. Backend pytest used separate mustard_test
sequentially after frontend media cleanup; do not truncate an active app's DB or
share buckets across unrelated live databases and orphan sweeps.

Playwright 1.64.1 used installed **Chrome 156.0.8078.79** with a 390×844 viewport and
1440×1000 desktop layout. No physical camera/phone was used. It drives real browser
getUserMedia/MediaRecorder with synthetic Y4M video and fake audio, then uploads
through the real API/decoder/storage pipeline. The runner generates a distinct
synthetic source per run because default Chrome fake frames can hash identically;
duplicate protection correctly persists after deletion. No production media is
altered to bypass hashing.

## Browser evidence

1. Two independent cookie contexts: admin creates invite, friend joins through UI;
   camera photo earns 1, recorded video earns 3, gallery photo earns 0. Feed contains
   all 3, sanitized video plays, weekly/all-time rows show authoritative counts,
   admin removes friend's video and friend removes own gallery post.
2. Camera denial is injected as NotAllowedError (a negative-path simulation), then
   real synthetic camera opens. Leave dialog traps Tab/Shift-Tab and supports Escape;
   confirming departure stops every captured track. Photo preview tracks also stop.
3. Backend session request deliberately aborted: explicit unavailable/retry UI,
   no fabricated feed or sign-in fallback.
4. First gallery submission actually accepted by backend, its response deliberately
   dropped. Browser retries exact same key/bytes/path and gets one post, gallery 0.
5. Admin actually removes friend's membership; friend's next capture request gets
   real backend 403 and a distinct permission-denied UI.

Unit tests cover cookie credentials, in-memory CSRF headers, no localStorage writes,
401/network distinction,403/422/503 error envelopes/request IDs, opaque cursor
pagination/end detection, upload progress/unknown outcomes/stable retry key,
gallery labels, codec detection, byte limits and Accra Monday/midnight boundaries.

Mobile/desktop feed screenshots were visually inspected; synthetic test images
are clearly fixtures, not real friend activity. Supporting text contrast was
checked against the cream palette and darkened where necessary. This is not a
full WCAG audit or screen-reader certification. Ignored screenshots remain under
frontend/test-results; browser traces/videos are off to avoid storing auth headers
or signed media requests.

Compiled production preview was checked independently: Google entry present,
development ID/form absent even with VITE_DEV_LOGIN=true in the preview shell.
Actual Google credentials were not supplied and consent/callback was not completed.

## Limits and next checks

- No physical iPhone/Android, Safari or Firefox verification; no real microphone,
  rotation/backgrounding or cellular testing. See phone-checklist.md.
- HTTPS private-LAN Caddy example is documentation, not an executed setup.
- Docker/Compose packaging and new remote CI workflow remain unexecuted here.
- Avatars remain absent. Optional captions are now implemented; caption editing
  after submission is outside scope. Feed uses real profile names/initials.
- Browser capture is not tamper-proof. Acceptance time/eligibility/points/streaks
  remain server authority. Countdown is a display estimate synced from server time.
- Upload plans and CSRF exist only in memory. Refresh/tab closure or confirmed
  departure discards a safe retry key; the server may already have accepted an
  in-flight upload. Warnings explain that. There is no background upload queue.
- Signed URLs are renewed before expiry and after a bounded load-failure retry;
  removed membership prevents new issuance. Old URLs remain bearer access until
  expiry. No URL is written to persistent browser storage.
- Image defaults 15 MiB/40 Mpx/12000 px and video 50 MiB/5–30s/720p (<=1280px long
  edge, <=720px short edge) are UI checks;
  custom server limits must be reflected in the frontend. The server always decodes.
- Leaderboard offset pages may change during concurrent scoring. Own-row lookup
  follows existing pagination and stops at the backend's offset bound 10000.
- Google authentication navigates to the existing backend flow; real Google
  integration remains an external credential/configuration gate.

No deployment, public tunnel, paid service or unsupported social feature was added.

Final run: unit tests 13/13 (2.67s), browser tests 5/5 (18.2s); final production
build and compiled login check passed. Cleanup deleted four remaining test media
objects and schema drift check passed. All owned test servers were stopped after
verification; retained tool files and disposable databases support reruns.
