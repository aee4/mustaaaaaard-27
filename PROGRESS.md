# Progress

## Linux container verification passed — 2026-11-01

[Manual run 41355405807](https://github.com/aee4/mustaaaaaard-27/actions/runs/41355405807)
completed successfully on the intended public repository. It built the root production
image and ran isolated PostgreSQL/MinIO, migrations, and **130** backend/integration
tests successfully. The application container was actually constrained by Linux
cgroup v2 to 536,870,912 bytes, no swap, and `cpu.max=10000 100000` (0.1 CPU).
Its highest recorded whole-cgroup memory peak was 356,626,432 bytes; `oom` and
`oom_kill` remained zero.

Initial readiness was 37.81 s; restart readiness was 16.58 s. Synthetic maximum
30-second 720p landscape, portrait, and H.264 High uploads succeeded in 28.59 s,
29.16 s, and 72.53 s. Chromium playback succeeded for those outputs plus VP8/Opus
and VP9/Vorbis media; unsigned media was denied (403). Invalid-media retry,
busy-processor handling, FFmpeg-child SIGKILL recovery with the same idempotency
key, replay uniqueness, and app-container restart recovery all passed. Artifact
publishing was disabled, so no Actions artifact storage was used; sanitized evidence
was reviewed from the job log. This verifies the approximate Linux target gate, not
actual Render behavior, Neon/R2 networking, Google OAuth, or physical phones.

## GitHub publication in progress — 2026-11-01

User supplied https://github.com/aee4/mustaaaaaard-27. Confirmed empty/public repo,
authenticated aee4 push/admin access and Actions enabled. Initialized local main
and added that exact origin without changing working files. Audited all 134 Git
candidates: no runtime paths, private videos/databases/keys, token signatures or
oversized files detected. Explicit .env ignores checked; only placeholder/example
env files and intentional public branding icons are included. Added database,
private-video and key ignore patterns; local working data/dependencies are preserved.

Standard public hosted compute is free; account billing/usage API returned 404,
so artifact storage cannot be confirmed. Added optional artifact publishing
(default false), with sanitized reports in job logs/summary for a storage-free run.
No paid usage/billing changes, hosting deployment or R2 activation are authorized.
The repository was published as a sequence of focused commits and the Linux result
is recorded above. No paid Actions setting, hosting deployment, R2 activation, or
Fly.io change was made.

## Manual Linux container verification prepared — 2026-11-01

Added `.github/workflows/linux-container.yaml`, separate from deployment and the
unchanged automatic backend/frontend workflows. Manual dispatch requires explicit
confirmation of existing free Actions compute/storage and stop-usage policy. One
standard Ubuntu 24.04 job, 45-minute timeout, no larger runner, paid plan, image
push or dependency-cache publication; sanitized JSON artifacts expire after 3 days.
The checkbox/timeout are not a spending cap and account allowances are unverified.

The job builds the real root production image, starts isolated PostgreSQL/MinIO,
applies/checks migrations and runs the full backend/integration suite. Test DB and
bucket are distinct from the resource workload; all published ports bind loopback.
The production image runs with CI-only test authentication overrides, never public
development auth. No production secrets or Google/hosting/R2 credentials are used.

The new Linux runner asserts whole-cgroup 512 MiB/no-swap/0.1 CPU limits and records
memory current/peak/events, CPU quota/usage/throttling and selected Docker exit/OOM
state before/after workloads/restart. It tests maximum-size landscape/portrait/High
720p videos, 180s HTTP acceptance budgets, readiness during processing, real signed
Chromium MP4/VP8/VP9 playback, unsigned denial, scoring/feed/rankings, invalid-upload
retry, media_busy, deliberate FFmpeg-child SIGKILL with same-key recovery/replay,
and application-container restart recovery. It fails on missing counters/OOM and
preserves pre-restart evidence. Diagnostics exclude media, URLs, cookies, raw test
captures, full container logs/environment and database dumps.

Actual local verification: actionlint **1.7.12** passed the new workflow; official
Compose schema validation passed both files (actual merging/build pending). Ruff
lint/format and mypy passed; **126 backend tests passed**, no skips, 89.59s, real
native PostgreSQL/MinIO/FFmpeg, two existing httpx deprecation warnings. This includes
10 new helper tests for fail-closed limits/OOM and safe artifacts. Frontend lint,
TypeScript, **20 unit tests** and production build passed. Native HTTP/browser runs
of the new helpers passed invalid-media/replay recovery, all three 30s/50 MiB MP4
fixtures and both WebM variants, with real signed playback and unsigned GET=403.
These helper runs used **unconstrained native Windows services/Chrome**, not Linux
containers. Existing working data and services were preserved.

This historical preparation note predates publication and dispatch. The actual
storage-free run is recorded above and in
[docs/linux-container-verification.md](docs/linux-container-verification.md). No
WSL/system installation, cloud provisioning, R2 activation, paid usage or Fly.io
changes occurred. The CI pass approximates target resource limits; it does not prove
actual Render performance, Neon/R2 access, Google consent or phone support.

## Approved 720p video remux — 2026-11-01

Implemented before provisioning. New video limit is <=720px short edge and
<=1280px long edge (portrait supported); duration 5–30 seconds, size 50 MiB and
video=3/gallery=0 are unchanged. Existing stored videos were not changed or removed.
Previous universal libx264/AAC conversion caused the resource failures below.
Compatible H.264/AAC-LC MP4 and VP8/VP9 Opus/Vorbis WebM now undergo full bounded
decode validation then stream-copy remuxing, with independent decoded/output timing
checks. Original global/stream tags, chapters and H.264 SEI user data are stripped;
technical rotation is preserved. Unsupported codecs/profiles, HEVC/HDR, resolutions
and container combinations return actionable 422 errors without conversion.
One-processing-job/one-thread defaults, byte/object quotas, private storage,
hash/idempotency/lease rules and atomic scoring remain. Obsolete encoder preset
configuration was removed. No migration or public API schema change is needed.

Browser requests 720p/30fps at ~2.5Mbps video/128kbps audio and prefers explicit
H.264/AAC when supported. Preview validation checks actual dimensions; UI explains
device constraints are best-effort, accepted formats and 0-point export/gallery.
SPEC, README, frontend integration/verification, private HTTPS and deployment docs
updated; details in [video-processing.md](docs/video-processing.md).

Actual checks: **116 backend tests passed**, no skips (21.87s), with real native
PostgreSQL/MinIO/FFmpeg and two existing httpx deprecation warnings. Ruff lint and
format, mypy, Alembic check/current (0003 head, no pending operations), frontend
ESLint/TypeScript, **20 unit tests**, production build passed. **8 real-backend
Chrome tests passed** (23.8s), including real signed MP4/VP8/VP9 playback, unsigned
storage denial, synthetic capture, group permissions/switching, retries and scoring.
Synthetic fixture tests verify landscape/portrait 720p, rotation, metadata/SEI
removal, unchanged decoded picture hashes, duration boundaries and rejections.
After the last HDR rejection guard, the signed remux playback/unsigned-denial
browser test passed again (1 test, 3.6s). Render blueprint schema validation passed.
Native app remains at http://localhost:3000 with /api/ready=200; backend and Vite
bind only loopback and normal native rate limits were restored after browser tests.

Three supporting Windows process-tree runs at configured 512 MiB/approximate 0.1 CPU
accepted 30s/exactly 50 MiB landscape and portrait H.264/AAC videos. Second run:
23.10s/22.08s HTTP, peak 137,326,592 committed bytes (~131 MiB), aggregate CPU5.95s.
A third run added H.264 High/30fps/B-frames: 54.10s acceptance, peak 140,247,040
bytes (~134 MiB), aggregate CPU10.77s. Seven maximum-size video uploads succeeded.
Windows committed-memory accounting is not Linux cgroups. **Docker is absent and
WSL has no distribution: Linux 512 MiB/0.1 CPU and Docker build remain pending.**
No genuine Android/iPhone fixtures or physical devices/Safari were tested. No
provisioning, paid services, R2 activation or Fly.io changes occurred. Production
development authentication remains disabled in configuration. Account eligibility,
R2 overage approval and real deployed acceptance remain separate pending gates.

## Earlier free-tier deployment preparation — 2026-11-01

Historical findings below describe the earlier 4K encoder pipeline; the current
720p remux results and remaining gates are recorded above.

Target: Render Free single-origin React/FastAPI container, Neon Free PostgreSQL,
private R2 Standard. **Not deployed; no production URL.** No paid plans, R2 checkout
or provider resources enabled, and no Fly.io apps modified. Published eligibility,
allowances, payment/overage behavior checked; account-specific eligibility and
remaining quotas unverified because Render/Neon/Cloudflare access is unavailable.
R2 allowances and budget alerts are not hard spending caps; explicit exposure
approval remains required and the production acknowledgement flag stays false.

Prepared root production image (FFmpeg/FFprobe), Render Free blueprint, production
env reference, same-origin static/API routing, secret-safe errors, explicit owner
bootstrap, startup migration lock and cleanup only while awake. Free has no paid
pre-deploy/shell/cron features configured. Render /health avoids continuously waking
Neon; /api/ready checks schema/bucket explicitly. Supplied favicon preserved and
16/32px PNG/ICO, Apple 180px and 192/512px derivatives wired in index.html; exact
title, description and mustard theme, no PWA.

Migration 0003 adds reserved object bytes. Atomic global byte/object quota checks
before PUT, unknown legacy usage fails closed, cleanup debt retained until confirmed
deletion, no memory eviction, idempotent replay preserved. Media concurrency one,
one-thread decoder/encoder/filter, bounded existing timeouts, retryable busy/resource
errors. Native image sanitation now avoids redundant full-size copies while keeping
orientation/metadata stripping. Free profile explicitly uses ultrafast (larger
possible outputs), preserving accepted bounds, validation, scoring and timestamps.

**Resource blocker:** 30s H264/AAC motion/noise fixtures at exactly 50 MiB, 1080p and
4K. In a Windows 512 MiB Job + approximate 0.1 CPU test, veryfast timed out on 1080p
and failed 4K allocation. Ultrafast reduced reported peak to about 401 MiB and
accepted 1080p in 125.84s, but 4K still returned media_processing_timeout in 124.10s.
Gallery stayed zero; failed video earned nothing. No faithful Linux/Render memory
claim: Docker unavailable, WSL has no distribution. Isolated compose.resource.yaml
and repeatable workload provided for Linux 512m/0.1 CPU verification. Deployment
remains blocked rather than weakening limits or silently removing video support.

Actual checks: **105 backend tests passed** with ultrafast (26.22s, no skips, two
existing adapter warnings), Ruff/format/mypy and migration checks passed. Disposable
0003→0002→0003 preserved three post IDs/fingerprints/timestamps/tombstones; working
DB upgraded additively to head 0003 without reset. **15 frontend unit tests**, lint,
TypeScript, production build and audit (zero findings) passed. **7 real-backend
browser tests passed** (25.6s), synthetic devices only. Compiled single-origin local
app verified title/icons/font/license, no dev form, readiness 200 and dev login 404.
Its browser check exposed an overly low HTTP connection cap; raised to 16 while
keeping expensive media admission at one. Render Free YAML validated against the
official schema; live core OpenAPI still matches export. No Docker image execution,
real Google consent, Neon/R2 deployment or physical-phone result is claimed.

Exact account/secret setup, billing limitations, backup/restore commands and all
resource evidence: docs/free-tier-deployment.md. Local development app remains
http://localhost:3000 on loopback; production authentication is separate and disabled
for development identities. Next gate is reliable Linux resource proof, followed
by account verification and explicit R2 overage acknowledgement before provisioning.

## Cloudflare evaluation — 2026-11-01

Reviewed current official Workers, Containers, R2, Hyperdrive, pricing and limits
against actual native dependencies, PostgreSQL transactions, FFmpeg subprocesses,
cookie/CSRF and upload code. Python Workers is not an unchanged deployment target;
Cloudflare Containers is a plausible Linux target but needs paid runtime testing
and external PostgreSQL. Found separate 100 MiB Container outbound-handler limit
versus potentially 200 MiB sanitized output, and ordinary origin proxy 125-second
read timeout versus app's 240-second client budget. Proposed conservative hybrid
with same-origin provider URL and optional Cloudflare frontend asset hosting.
No resources purchased/created or Fly apps changed. No Cloudflare runtime or
production login/media verification claimed. Details: docs/cloudflare-evaluation.md.

## Repository separation and typography — 2026-11-01

Completed in order: backend source/configuration/tests/scripts moved into backend/;
46 files hash-verified, lock and migrations preserved. Updated Compose build
contexts, CI, native commands, ignore rules and explicit backend/.env loading.
Recreated backend/.venv; root environment/caches and all .tools data stayed put.
Fixed Alembic Windows path splitting; app remains 0002/head with no drift.
Before UI changes: 90 backend tests (21.39s), Ruff/format/mypy, migration checks,
15 frontend tests/lint/type/build and seven real-backend browser tests (23.7s) passed.

Then applied self-hosted SIL-licensed Inter Variable throughout, shared typography
tokens, compact bold headings, normal styles/spacing and tabular numeric displays.
Preserved colors/navigation/capture; fixed 320px Capture overflow. Final frontend
lint/type/15 tests/build/audit passed; seven real-backend browser tests passed
(22.9s). Production preview verified font/license and no development login.
Screenshots inspected at 320/390/1440px, including dialog, errors and onboarding.
Default rate limits restored and loopback development app left running.

No database recreation/volume deletion/deployment. Docker absent, physical phones,
Safari and remote CI unverified. No Git metadata: tracked-secret/history audit
unavailable; source-pattern review found no candidates. Full evidence and
before/after locations: docs/reorganization-typography.md.

## Group onboarding — 2026-11-01

Completed authenticated group creation, atomic creator-admin membership/audit,
validated/unique names, reserved initial name, CSRF and creation rate limiting.
Explicitly bootstrapped and verified lower-case alice as initial group admin.
No schema change required (head 0002). Added actionable no-group state, create/join
manager, automatic select/open Feed, group switching and invite copy/error feedback.
Switching resets group-specific views and generated invite links.

Actual checks: 90 backend tests passed (21.03s, two existing deprecation warnings),
15 frontend unit tests, 7 real-backend Chrome tests (25.2s), Ruff/format/mypy,
ESLint/typecheck/build, live OpenAPI/export match and npm audit (zero findings).
Production preview verified development login absent. New tests cover creation,
joining, permissions, concurrent conflicts, copying links and distinct group feeds.
Restored default rates and development app at http://localhost:3000 on loopback.
Test posts removed/private objects cleaned; test group/audit records retained.
No deployment. Synthetic media only; physical phones, Docker and real Google
remain unverified. See docs/group-onboarding-verification.md for evidence.

## Local acceptance preparation — 2026-11-01

App running at http://localhost:3000; native API at 127.0.0.1:58000, PostgreSQL on port 55432,
MinIO on port 59000 (IPv4/IPv6 loopback only). Development admin ID alice available. No
deployment, public tunnel, LAN listener or firewall change was performed.

Compared Feed/Capture/Leaderboard mobile screenshots against supplied reference:
compressed feed header/removed mobile marketing intro, date-led journal and real
captions; capture mode controls below live preview, compact heading and unobscured
shutter; highlighted ranking and Your season/grace card. Corrected route scroll
position and offscreen skip-link screenshot artefacts. Existing keyboard focus,
track cleanup and membership authorization preserved. Initials replace unsupported
portraits; no fabricated names/points or unsupported historical-week buttons.

Captions implemented end-to-end: migration 0002, optional multipart caption on both
existing upload endpoints,280-character Unicode limit, newline/whitespace handling,
plain text display, caption digest in idempotency comparison, frozen caption on
retry. Removal clears caption text. Browser test exposed multipart CRLF handling;
fixed normalization before validation and covered boundary/replay cases. Original
media duplicate fingerprints and scoring unchanged.

Actual checks: **79 backend tests passed** (12.85s,2 existing adapter warnings),
**13 frontend unit tests passed**, **5 real-backend Chrome tests passed** (21.1s),
Ruff/format/mypy, ESLint, TypeScript, production build, OpenAPI generation/live
comparison and audit (zero vulnerabilities) passed. Migration 0002→0001→0002 on
disposable mustard_test preserved existing post IDs/media fingerprints and restored
nullable new columns. Native acceptance DB upgraded without dropping existing data.
Readiness and frontend each returned 200.

Browser tests use synthetic Y4M video/fake audio, not physical cameras. Android,
iPhone, Safari, private-LAN Caddy TLS and certificate/firewall setup remain untested.
Exact private HTTPS steps provided in docs/phone-https.md; no dev auth exposed
publicly. See docs/local-acceptance.md for evidence and manual acceptance steps.
Services intentionally left running under the user's latest instruction.

Final readiness: frontend 200, proxied /api/ready 200, direct /ready 200; schema 0002
(head), no migration drift. Default auth/invite/upload rate limits restored after
tests (30/30/60 per minute). Cleanup removed eight remaining test media objects;
acceptance DB has zero live fixture posts. All four services verified listening
only on loopback (MinIO also ::1). Latest five-test browser run completed in 21.1s.

Earlier milestones below describe the state at their original completion times;
the previous caption limitation is resolved by this acceptance update.

## Frontend implementation — 2026-11-01

User authorized frontend/ React/TypeScript/Vite/Tailwind work. Read project rules,
product spec, all handoff guides, actual FastAPI routes/schemas and OpenAPI. Preserved
backend source and tests. OpenAPI has no caption/avatar fields: no invented caption
editor or fake identities; feed uses member names/initials and server metadata.

Implemented four responsive views, conditional dev/Google entry, invite/group
flows, cursor feed, weekly/all-time ranks, authoritative profile stats, moderation,
private media renewal, camera photo/video/previews/retake/cancel, gallery=0, upload
progress/stable-key retries, Ghana day/week countdowns and accessible focus states.
No backend application code, database schema or existing tests changed.

Actual frontend verification: ESLint and TypeScript passed; Vitest 13 passed;
production Vite build passed; audit zero vulnerabilities; regenerated API types;
live OpenAPI equals checked-in snapshot (20 paths). Browser tests: **5 passed**
against real native PostgreSQL 18/MinIO/FFmpeg and Uvicorn, using Chrome 156.0.8078.79
and synthetic camera/audio. Verified two users/invite join, photo 1/video 3/gallery 0,
feed, video playback, weekly/all-time ranks, own/admin deletion, track cleanup,
keyboard dialog focus, mobile/desktop overflow, explicit network failure, real
membership denial, and retry of a response lost after actual server acceptance
with the same key and no duplicate. Screenshots visually inspected at 390/1440px.

Production preview browser check passed: Google link present and dev login absent.
This does not verify real Google login. Backend full regression rerun: **65 passed,
2 existing adapter warnings in 13.92s**, Ruff/format/mypy passed. No skipped backend
tests. Dependencies upgraded to Vite 8/Vitest 5/ESLint 10 after initial audit; a fresh
coherent lock resolved stale npm peer state without suppressing peer checks. One
countdown test expectation was corrected for its displayed 24-hour format. Browser
capture exposed a transient URL lifecycle typo and native-dialog Tab wrapping;
both fixed and tests rerun. Default fake camera repeated identical original bytes
and correctly hit permanent duplicate protection; test runner now generates a
distinct Y4M fixture per run without modifying production capture bytes.

Native backend used loopback port 58000, Vite localhost:3000, isolated handoff DB, explicit
dev:alice bootstrap, raised fixture rate limits and real media binaries. No hosted
site registration, publication, deployment or paid service. CI workflow added but
remote CI and Docker packaging remain unverified. Physical phones, Safari, Firefox,
private-LAN TLS proxy and real Google login remain untested. See
docs/frontend-verification.md and docs/phone-checklist.md for evidence and limits.

Final frontend run: 13 unit tests passed (2.67s), 5 browser tests passed (18.2s),
fresh production build passed, and compiled production-login check passed again.
Final audit: zero vulnerabilities. Media cleanup deleted the four remaining test
objects; migration drift check passed. Vite, Uvicorn, MinIO and the isolated
PostgreSQL cluster were stopped. Tool files/disposable DBs retained for reruns.

Exact next action: run local services using README and perform the physical-phone
checklist on a private HTTPS setup. Any caption support needs an explicit backend
contract extension; none was invented here. Earlier backend-only milestones below
are retained as historical evidence.

## Handoff re-verification — 2026-11-01

Read README, this file and frontend integration guide. Docker was checked again:
command not found; standard Docker Desktop binaries absent. Compose execution
remains unverified, including image build, Linux permissions/dependencies, volumes,
DNS, startup sequencing, in-container migration/admin commands and readiness.

Restarted actual native PostgreSQL 18/MinIO/FFmpeg setup. Reapplied Alembic head
and confirmed no drift. Documented smoke: 1 passed, 8 deselected. Full suite:
**65 passed, no skips, 2 existing deprecation warnings in 10.15s**.

Also created isolated `mustard_handoff_test`, applied migrations, ran explicit
dev-admin CLI, and launched Uvicorn on loopback port 58000. Real HTTP smoke passed:
two users/one group, photo=1, video=3, gallery=0, feed=3, weekly/all-time scores
3/1, readiness=200, signed media=200 and unsigned media=403. Added reusable
scripts/smoke.py plus docs/handoff-verification.md and clarified README/frontend
guide. No application failure found. No frontend or deployment started.

Verdict: ready for local frontend API integration with development auth/native
services. Docker packaging, real Google login and production setup remain gates.
Detailed original implementation evidence follows.

HTTP smoke also passed a second run; cleanup removed six smoke media objects.
Final Ruff check/format (44 files), mypy (23 app files), lock and migration-drift
checks passed. Temporary Uvicorn/MinIO/PostgreSQL processes were stopped; no
production data was modified. The disposable test databases remain locally.

2026-11-01 — all six backend implementation phases complete and locally verified.
No frontend, deployment, paid service, social extras or notifications were created.
Product policies and architecture were documented before implementation.

## Actual verification evidence

Host: Windows PowerShell, Python 3.13.12, uv 0.10.12. No Docker available. Used
real PostgreSQL 18, an isolated `mustard_test` database at 127.0.0.1:55432, real
source-built MinIO at 127.0.0.1:59000 with a private bucket, and FFmpeg/FFprobe
9.0.2. No SQLite. Portable tools/data are ignored under `.tools/`; Go caches are
outside this project. See docs/local-verification.md for exact repeat commands.

Final full suite after auth/error-schema changes:

```text
uv run pytest -q
65 passed, 2 warnings in 9.85s
```

No skips. Verified cross-user/group authorization, session expiry/logout/CSRF,
invite limits and concurrency, seven RSA-signed mocked-OIDC cases including
state/nonce/PKCE/issuer/audience/expiry/signature, production dev-auth rejection,
actual media decoding/metadata removal, duration/codec/size limits, live WebM,
concurrent cross-user duplicate constraint, idempotency/replay/conflict, capture
single-consumption and atomic rollback, partial storage writes, DB commit ambiguity
and outages, revoked membership during upload, orphan cleanup, real MinIO private
denial/signed success/expired denial, two-user photo/video/gallery/feed/rankings
smoke, deterministic grace and deletion/week/day boundaries.

Final commands actually passed:
- `uv run ruff check .`: all checks passed.
- `uv run ruff format --check .`: 41 files already formatted.
- `uv run mypy app`: no issues in 23 source files.
- `uv lock --check`: 67 packages resolved; lock is consistent.
- Alembic `downgrade base`, `upgrade head`, `check`: sequentially after tests,
  successful round-trip and no schema drift on the disposable PostgreSQL DB.
- Explicit bootstrap-admin CLI successfully exercised against disposable DB.
- OpenAPI exported to docs/openapi.json and error-envelope schema verified.
- Default application `/health` and `/ready` each returned 200 against real
  PostgreSQL/MinIO after the migration round-trip.

Temporary MinIO and the isolated PostgreSQL cluster were stopped after verification;
their ignored tool/data files remain available for repeat checks.

Two upstream warnings concern Starlette/Authlib's httpx adapter deprecation in
favor of httpx2; not suppressed. Revisit with the next dependency upgrade.

## Resolved verification issues

An early test run overlapped a migration round-trip. Its setup error was discarded,
followed by sequential passing runs. OIDC mock fixture initially reused Authlib's
cached client; an isolated registry fixed it. Live WebM fixtures now explicitly
disable duration headers and exercise missing inferred timing with real decoding.

Upstream MinIO binary download returned 410. Built pinned source
RELEASE.2025-10-15T17-29-55Z using portable Go 1.25.5; Compose/CI build the same
source. Background Start-Process was rejected by execution policy; foreground
loopback-only server was allowed and tested successfully. No approval blocker remains.

## Remaining external configuration and limits

- Dockerfile/Compose runtime and remote CI have not run here. Compose YAML parsed;
  that is not a container-runtime check.
- Real Google credentials absent; signed mocked-provider verification passed, but
  real Google account consent/discovery/callback remains unverified.
- Production needs random secret, registered Google client/callback, HTTPS proxy,
  secure cookies, exact origins, maintained private S3/IAM, public HTTPS signing
  endpoint, optional bucket CORS, cleanup schedule, quotas and backups.
- Production IAM, HTTPS topology and backup/restore have not been exercised.
- Browser sessions do not prove camera origin/content freshness; SHA256 detects
  exact original bytes only. Signed URLs remain bearer access until expiry.
- Grace history is immutable; deletion can reduce current/longest. Fingerprints
  and tombstones persist; object versioning requires noncurrent deletion policy.
- MinIO source is development infrastructure. Size temporary disk/concurrency and
  bucket prefix-scan cost for production. See README for retention/known limits.

## Exact next action

On a Docker-enabled workstation follow README: copy .env.example, `uv sync
--locked`, `docker compose up -d --build`, then explicit admin bootstrap. Generate
a frontend client from `/openapi.json`; implement `/auth/session` cookie/CSRF
handling and invite join, then capture-session/upload per docs/frontend-integration.md.
Backend remains authoritative over dates, points, eligibility and identity.
