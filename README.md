# Mustaaaaaard ’27

**The Final Season.** Private final-year photo/video sharing. FastAPI/PostgreSQL/
private S3 backend, with a mobile-first React/TypeScript frontend in `frontend/`.
The existing production app is https://mustaaaaaard-27.onrender.com.

The Cloudflare frontend is https://mustaaaaaard-27.eeyramagbetor.workers.dev,
with independent static assets and a same-origin API/auth gateway to the existing
Render Free backend. Neon and private R2 are retained. The Render frontend remains
available as a fallback. See [Cloudflare release and rollback](docs/cloudflare-frontend.md)
and [PROGRESS.md](PROGRESS.md) for verification and outstanding release gates.
Cloudflare serves the interface while Render wakes; Render Free cold starts remain.
No hosting plan upgrade, paid service, custom domain or scheduled pinger is required.

Linux verification can run on GitHub's standard Ubuntu runner without local Docker:
see [the manual container workflow](docs/linux-container-verification.md) for free
allowance checks, exact trigger steps, resource metrics, artifacts and current
limitations. [Run 41355405807](https://github.com/aee4/mustaaaaaard-27/actions/runs/41355405807)
successfully exercised the production image on Linux under that 512 MiB/0.1 CPU
approximation. This is not a deployment or proof of Render, R2, Google OAuth, or
physical-phone compatibility.

Cloudflare hosting compatibility, current costs and provider-domain authentication
tradeoffs are recorded in [docs/cloudflare-evaluation.md](docs/cloudflare-evaluation.md).
That earlier evaluation is historical; the current frontend topology is documented above.

## Repository layout and command locations

`backend/` contains Python source, migrations, tests, backend scripts, Dockerfiles
and the locked Python project. `frontend/` contains the web app and its tooling.
Shared documentation, CI and compose.yaml remain at the root. Commands below run
from the repository root: `uv run --directory backend ...` changes into backend/
and uses backend/.venv; `uv sync --project backend --locked` recreates that environment
from backend/uv.lock. The previous root .venv is unused and was not moved.
Frontend commands use `npm.cmd --prefix frontend`; its dependencies/builds stay there.

Environment loading is explicit:

- Native Python Settings always reads `backend/.env` (optional); process environment
  variables override it. Copy `backend/.env.example` to `backend/.env` if needed.
  Native startup does not read root `.env`. Windows examples set process variables.
- Compose loads root `.env` via each Python service's `env_file`; copy root
  `.env.example` for Compose only. Container process variables override the optional
  `/srv/.env`, which is excluded from the image. Build context is backend/.
- Vite loads frontend/.env, frontend/.env.local and mode files from frontend/;
  process variables take precedence. Never place secrets in VITE_* variables.

Retained native PostgreSQL/MinIO data and portable tools remain under ignored
`.tools/` at the root. Reorganization does not change database URLs or volume names.

## Web frontend

Typography uses self-hosted Inter Variable (`@fontsource-variable/inter`, SIL Open
Font License 1.1; [license](frontend/public/INTER-LICENSE.txt), also shipped in the
build). It is a freely licensed alternative, not Snapchat's exact font. Shared CSS
tokens define one sans-serif family, body/control/heading weights and compact
heading spacing; scores, ranks and countdowns use tabular numerals. No font CDN is
required. Before/after screenshots and verification are described in
[docs/reorganization-typography.md](docs/reorganization-typography.md).

Node 22.13+ (verified on 22.16.0) and npm are required. Start the backend using the
existing instructions below. On a Docker-enabled machine, after copying `.env`
and bootstrapping `dev:alice`:

```powershell
npm.cmd ci --prefix frontend
$env:API_TARGET='http://127.0.0.1:8000'
$env:VITE_DEV_LOGIN='true'
npm.cmd run dev --prefix frontend
```

Open **http://localhost:3000**, development ID `alice`, any display name. In another
browser/private window use a different development ID and join using an invite
created in the admin's Profile screen. IDs are case-sensitive: `alice` is the
bootstrapped admin; `Alice` is a different development identity.

With no memberships, choose **Create group** or **Join with invite**. Creating a
group makes you its admin and opens its feed. Use **Groups** (the plus button on
phones) to create or join another group. The **Your group** selector switches
between active memberships and opens that group's feed. In Profile, admins can
generate a 72-hour invite and copy its private link; ordinary members cannot.
Creation does not grant access to existing groups. The initial Mustaaaaaard ’27
group still requires the explicit bootstrap command below or an invite.

Vite binds loopback and proxies `/api/*` to backend paths without the `/api` prefix;
`/auth/*` proxies unchanged for Google redirects. Browser requests include cookies;
mutations add the in-memory session CSRF token and preserve browser Origin. Keep
`ALLOWED_ORIGINS` including `http://localhost:3000`. For Google configuration, set
backend `BASE_URL=http://localhost:3000` locally (HTTPS frontend origin in production)
and register its `/auth/google/callback`. Real production Google login is confirmed
on the Cloudflare origin; local Google configuration is independent.
The UI shows development login only under Vite development mode **and**
`VITE_DEV_LOGIN=true`; production builds never display it.

For this Docker-free Windows workspace, first start native PostgreSQL and MinIO
using [docs/local-verification.md](docs/local-verification.md), then in a backend shell:

```powershell
$env:DATABASE_URL='postgresql+psycopg://mustard@127.0.0.1:55432/mustard_handoff_test'
$env:S3_ENDPOINT='http://127.0.0.1:59000'
$env:DEV_AUTH='true'
$env:BASE_URL='http://localhost:3000'
$env:FFMPEG=(Resolve-Path '.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe').Path
$env:FFPROBE=(Resolve-Path '.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe').Path
uv run --directory backend alembic upgrade head
uv run --directory backend python -m scripts.init_storage
uv run --directory backend python -m app.cli bootstrap-admin --subject dev:alice --display-name Alice
uv run --directory backend uvicorn app.main:app --host 127.0.0.1 --port 58000 --no-access-log
```

In a separate shell, start the frontend with `API_TARGET=http://127.0.0.1:58000`
and `VITE_DEV_LOGIN=true` as above. These settings are development-only, on loopback.
The disposable handoff DB already exists in this workspace. For a fresh native
install create that DB explicitly before migrating; don't truncate real data.

Frontend checks:

```powershell
npm.cmd run generate:api --prefix frontend
npm.cmd run lint --prefix frontend
npm.cmd run typecheck --prefix frontend
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
npm.cmd audit --prefix frontend
# Backend + frontend must already be running; Chrome must be installed.
# Set FFMPEG as above for generation of distinct synthetic camera fixtures.
npm.cmd run test:e2e --prefix frontend
```

Browser tests mutate the disposable group, create test users/invites and retain
duplicate fingerprints/tombstones. Use a dedicated test database/private bucket
and an admin `dev:alice`; never point them at production. Do not run truncating
backend pytest fixtures against the API's DB concurrently. To use bundled Chromium
instead of installed Chrome, set `PW_BROWSER_CHANNEL=chromium` and install it from
`frontend/` using `npx.cmd playwright install chromium`. Screenshots are ignored
under `frontend/test-results/`; traces/video recording are disabled to avoid
retaining authentication or signed media URLs. Windows commands use npm.cmd to
avoid PowerShell execution-policy issues; on Unix use npm.

Build output is `frontend/dist`. `npm.cmd run preview --prefix frontend` previews
the production build at localhost:3000 using the same API_TARGET proxy. Stop the
dev server before previewing on that port. Vite's proxy is local development/
preview infrastructure; a production server needs the documented same-origin
HTTPS reverse proxy for `/api` and `/auth` plus SPA route fallback. The deployed
Cloudflare gateway forwards those paths to Render's existing mounted web app.

With production preview running on port 3000, `npm.cmd run test:production --prefix
frontend` checks the compiled login screen in Chrome: Google entry exists and the
development form is absent, even if VITE_DEV_LOGIN was enabled for development.
It does not complete Google authentication. Frontend verification evidence is in
[docs/frontend-verification.md](docs/frontend-verification.md).

Optional captions are implemented end-to-end: multipart `caption`, at most 280
characters, displayed as plain text below media. Migration `0002` adds nullable
captions and retry fingerprints; run `uv run --directory backend alembic upgrade head` before startup.
Caption edits after submission are outside scope: retries keep the same caption,
bytes and key. Removed posts lose caption text. Avatars remain unsupported, so real
member names use initials. No social extras added.
Capture and size/duration rules are checked in-browser, with server validation
remaining authoritative. Client limits reflect documented defaults; if operators
change server limits, update frontend constants too. Own points come from paginated
all-time rankings because there is no dedicated own-score endpoint. See
[docs/phone-checklist.md](docs/phone-checklist.md) before claiming phone compatibility.

## Prerequisites

Python 3.12+ (verified on 3.13), [uv](https://docs.astral.sh/uv/), Docker with Compose.
Running Python on the host also needs FFmpeg **and FFprobe** on PATH. Containers
include both. MinIO is built from a pinned upstream source release because upstream
community binaries/images are no longer reliably available ([source release](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z)). Initial image build
downloads Go dependencies and can take several minutes. MinIO is for development;
use maintained private S3-compatible storage for production.

## Start locally

PowerShell, from this directory:

```powershell
Copy-Item .env.example .env
uv sync --project backend --locked
docker compose up -d --build
docker compose exec api uv run --no-sync python -m app.cli bootstrap-admin --subject dev:alice --display-name Alice
Invoke-RestMethod http://localhost:8000/ready
```

Or run the API on your host (FFmpeg/FFprobe required):

```powershell
docker compose up -d postgres minio storage-init
Copy-Item backend/.env.example backend/.env
uv run --directory backend alembic upgrade head
uv run --directory backend python -m app.cli bootstrap-admin --subject dev:alice --display-name Alice
uv run --directory backend uvicorn app.main:app --reload --no-access-log
```

API: http://localhost:8000. Interactive OpenAPI: `/docs`, schema: `/openapi.json`.
Liveness `/health`; readiness `/ready` checks current migration and bucket.
MinIO console: http://localhost:9001 (local credentials in `.env.example`). Bucket
is private. `S3_ENDPOINT` is server-accessible; `S3_PUBLIC_ENDPOINT` optionally
overrides the hostname used to sign browser URLs. Compose sets internal MinIO for
IO and localhost for browser access; never rewrite an already signed URL.

Development login: `POST /auth/dev` with `Origin: http://localhost:3000` and JSON
`{"subject":"alice","display_name":"Alice"}`. Save its cookie in a cookie jar;
use returned `csrf_token` as `X-CSRF-Token` and allowed `Origin` on mutations.
Only the explicit bootstrap command grants admin. Other users need an invite.
Production bootstrap uses `--subject google:GOOGLE_SUBJECT_ID`.

## Configuration and migrations

Native: copy `backend/.env.example` to `backend/.env`; process environment takes
precedence. Compose: copy root `.env.example` to root `.env`. Relevant optional
limits are `IMAGE_MAX_BYTES` (15 MiB), `VIDEO_MAX_BYTES` (50 MiB),
`IMAGE_MAX_PIXELS` (40 million), `IMAGE_MAX_DIMENSION` (12000), `CAPTURE_SECONDS`
(600), `SESSION_SECONDS` (604800), `MEDIA_URL_SECONDS` (120, max300),
`AUTH_RATE`/`INVITE_RATE`/`UPLOAD_RATE` (30/30/60 per minute). `FFMPEG` and
`FFPROBE` accept executable paths. `LEASE_SECONDS` defaults to 300 (minimum300).
Image limits and decoder bomb limits both apply. Rates are fixed-window PostgreSQL
buckets shared across workers; minute boundaries permit a short burst.

```powershell
uv run --directory backend alembic upgrade head
uv run --directory backend alembic check
# Only on disposable databases: uv run --directory backend alembic downgrade base
```

All schema changes need reviewed Alembic revisions. Synchronous SQLAlchemy sessions
are short-lived; blocking routes run in FastAPI's thread pool. Storage, sanitation
and OAuth HTTP calls run outside database transactions. No production `create_all`.
Upload state machine and policies are specified in [SPEC.md](SPEC.md).

## Verification

```powershell
uv run --directory backend ruff check .
uv run --directory backend ruff format --check .
uv run --directory backend mypy app
uv run --directory backend pytest -q
```

For **full** tests, create a dedicated disposable PostgreSQL database ending in
`_test` (tests truncate its public application tables). Never point tests at real
data. For the Compose database:

```powershell
docker compose exec postgres createdb -U mustard mustard_test
$env:DATABASE_URL='postgresql+psycopg://mustard:mustard@localhost:5432/mustard_test'
$env:TEST_DATABASE_URL=$env:DATABASE_URL
$env:TEST_S3_ENDPOINT='http://localhost:9000'
uv run --directory backend alembic upgrade head
uv run --directory backend pytest -q
```

FFmpeg/FFprobe must be on PATH or supplied as `FFMPEG`/`FFPROBE`. Without service
variables, corresponding tests explicitly skip; that is not full verification.
`uv run --directory backend pytest tests/test_storage_video.py -k two_user -v` runs the real two-user
photo/video/gallery/feed/rankings smoke workflow. CI provisions PostgreSQL/MinIO,
runs all tests, checks schema drift and exercises downgrade/upgrade. CI itself has
not been run remotely; local evidence is in [PROGRESS.md](PROGRESS.md).

For a real HTTP smoke check against a running local API, use a fresh development
group with only its bootstrapped admin and no live posts. With the `dev:alice`
admin created above:

```powershell
# Host FFmpeg must be on PATH, or set FFMPEG to its executable path.
uv run --directory backend python -m scripts.smoke --base-url http://127.0.0.1:8000 --admin-subject alice
docker compose exec api uv run --no-sync python -m app.cli cleanup
```

This script logs in two users over HTTP, joins via invite, submits real photo/video
captures plus a gallery image, verifies feed/weekly/all-time rankings and private
media, then removes its posts, revokes its invite, removes its member and logs out.
It creates persistent fingerprints/tombstones and user metadata; use a disposable
development database. It only accepts loopback HTTP targets. Never run it against
production or an existing group's real data.

Handoff re-verification on 2026-11-01: documented integration smoke passed; a
separate Uvicorn HTTP smoke passed with native PostgreSQL/MinIO/FFmpeg; full suite
passed **65 tests with no skips**. **Docker is unavailable on this machine.** No
Docker build or Compose startup has been executed: image builds, Linux runtime
dependencies/permissions, volumes, service DNS, startup sequencing, container
migration/admin commands and container readiness remain unverified. Native checks
validate the application API and real service integrations, not container packaging.
See [docs/handoff-verification.md](docs/handoff-verification.md) for evidence.

## Cleanup, retention and recovery

```powershell
uv run --directory backend python -m app.cli cleanup --limit 100
# Container: docker compose exec api uv run --no-sync python -m app.cli cleanup
```

Run cleanup every minute using your scheduler. It deletes objects for removed
posts immediately and failed/abandoned operations once their leases expire. Each
object is claimed with a new lease, deleted outside transactions, then recorded
clean; failures stay tracked for the next run. It also scans `media/` and deletes
unreferenced objects older than 15 minutes, covering delayed stale-worker writes.
This scans the bucket; plan for listing cost as storage grows. Rerunning is safe. Media may remain
in storage until cleanup succeeds, and signed URLs last up to their expiry.
Original uploaded files are temporary, never served, and removed after processing.
Sanitized media lasts until removal. Fingerprints, minimal post/upload tombstones,
audit and grace history are retained indefinitely. Revoked sessions are unusable
immediately; expired sessions are purged after seven days. Rate buckets age out.
Unused captures and invite metadata are retained; plan retention review before
long-term use. Kill-of-process temporary directory debris is an OS-temp hygiene
concern; use a dedicated ephemeral temp volume in production.

## Production requirements

Set `ENVIRONMENT=production`, `DEV_AUTH=false`, a random `SECRET_KEY` >=32 chars,
`COOKIE_SECURE=true`, HTTPS `BASE_URL` and exact HTTPS `ALLOWED_ORIGINS`.
Register Google web OAuth client with callback `BASE_URL/auth/google/callback`,
set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. Authlib uses discovery and
verifies ID tokens, state/nonce and PKCE. Provider tokens are discarded, identity
is Google's stable subject. Real Google login and the existing group/session are
confirmed on the hosted app; each new deployment still needs correct registration.

Prefer frontend + `/auth` and API paths behind the same HTTPS origin. Cookies are
HttpOnly, Secure in production, SameSite=Lax, host-only and path `/`. A separate
cross-site frontend is unsupported by this topology. Use explicit CORS allowlist,
not wildcard. No tokens in localStorage. Retain the 51 MiB request envelope,
240-second client budget and bounded concurrency. See the Cloudflare guide for
measured upload duration and remaining origin-processing timeout limits. Run Uvicorn with access logs
off; never log signed URLs, cookies, bodies or OAuth callback query strings at the
proxy. Trust forwarded client-IP headers only from your actual proxy (`--forwarded-allow-ips`);
without it, auth IP limits see the proxy. Add TLS/HSTS at the proxy.

Supply PostgreSQL credentials and private object storage credentials with only the
needed bucket object/head/list permissions. Bucket must prohibit anonymous reads and
listing. App does not change production IAM/policies. Configure TLS at the public
object endpoint; browser media URLs must use HTTPS in production. Supply maintained
FFmpeg/Pillow builds, DB backups, storage quotas and monitoring. Local Compose
credentials are expressly development-only. Current production deployment and
rollback evidence is in [the Cloudflare release guide](docs/cloudflare-frontend.md).

## Backups and restore

Use `pg_dump -Fc` on the application database and snapshot/version the private
bucket together. Encrypt backups, restrict access and test restoration into an
isolated environment. Restore database via `pg_restore`, restore matching object
keys, run Alembic upgrade and readiness/smoke checks before enabling writes. Retain
fingerprints, upload rows and grace history; restoring only posts loses guarantees.
Bucket lifecycle must not delete live media. Disable object versioning or expire
noncurrent versions if removal must erase private bytes; otherwise deleting a key
can leave historical versions. Revoking signed URLs early requires rotating keys
or a media proxy, outside the current scope.

Database connections use a 5s connect timeout, 5s lock timeout, and 15s statement/
idle-transaction timeout. New video uploads are limited to 720p (long edge <=1280,
short edge <=720), 5–30 seconds and 50 MiB; video still earns 3 points. Compatible
8-bit H.264/AAC-LC MP4 or VP8/VP9 Opus/Vorbis WebM is decoded for validation, then
remuxed without re-encoding; HEVC/HDR and larger videos are clearly rejected.
Existing videos remain available. See [video processing](docs/video-processing.md).
Video processing has 20s input probing, 120s decoding, 30s remuxing and 10s output
probing budgets; sanitized video must be smaller than the input byte limit +1 MiB.
Configure your reverse proxy upload/read timeout to **240 seconds** to
allow storage retries and database lock waits as well as processing.

## Limits and next step

Browser capture sessions discourage casual misuse but cannot prove camera origin,
depicted-content age or freshness. EXIF is not evidence. Original-byte SHA256 only
detects exact duplicates within a group. Uploads use local temporary disk with a
request cap; size your concurrency/disk and proxy limits accordingly. Reads of
streaks persist elapsed grace under membership locks; there is no background worker.
Large groups/histories may require query tuning. Rank pages use offsets, so ranks
can shift while new posts arrive; feed uses stable keyset pagination.

Build the frontend against [docs/frontend-integration.md](docs/frontend-integration.md):
start with session bootstrap and invite join, then browser capture/session/upload,
gallery, feed, signed media and leaderboard screens. The OpenAPI document is the
machine-readable contract. The implemented frontend follows that contract.

Actual verification results are in [PROGRESS.md](PROGRESS.md). Host-specific
commands for the retained portable Windows test tools are in
[docs/local-verification.md](docs/local-verification.md). A static OpenAPI snapshot
is provided in [docs/openapi.json](docs/openapi.json); the running API schema is
authoritative.

## Local acceptance status

The app is prepared at **http://localhost:3000**, using native API on port 58000,
PostgreSQL on port 55432 and private MinIO on port 59000. Services were left running after the latest
acceptance pass. If the workspace/session restarts, use the native commands above.
Development ID `alice`, display name Alice, has explicitly bootstrapped admin
membership. Automated test posts have been removed; no fixture activity is passed
off as real friend memories.

Feed, Capture and Leaderboard were compared with the supplied phone reference.
Captions now work end-to-end on migration 0002. See
[docs/local-acceptance.md](docs/local-acceptance.md) for visual changes and test
evidence. For Android/iPhone camera testing, follow the exact private-HTTPS recipe
in [docs/phone-https.md](docs/phone-https.md), then record results in
[docs/phone-checklist.md](docs/phone-checklist.md). No physical-device test or LAN
firewall/certificate configuration is claimed passed.
