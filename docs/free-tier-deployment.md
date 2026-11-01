# Render Free + Neon Free + private R2 — 2026-11-01

**Deployment blocked.** No production resources, paid plans or R2 subscription
were enabled. Fly.io apps were not changed. The proposed container serves built
React and FastAPI from one Render HTTPS provider origin. No custom domain is needed.
Configuration is prepared; production eligibility and actual deployed flows are
not verified. Do not activate R2 while the resource-test blocker remains unresolved.

## Account eligibility, allowances and billing

No connected Render/Neon tools or local provider credential files were found;
Cloudflare credentials were also unavailable. Therefore **personal account
eligibility, remaining shared quotas, existing payment methods and subscriptions
are unknown**. Connection options for Render and Neon were offered. Public terms
were checked against official documentation on 2026-11-01:

| Service | Published free limits | What happens beyond them |
|---|---|---|
| Render Free | 0.1 CPU, 512 MB; 750 instance hours/workspace/month; sleeps after 15 minutes idle. Hobby currently includes 5 GB bandwidth and 500 standard build minutes. | Hours exhausted: suspension. Bandwidth/build overages can be billed when a payment method exists; without one, services/builds are suspended. A build-minute spend limit is not a universal account spend cap. High external DB/storage traffic can also cause suspension; no numerical threshold is published. |
| Neon Free | 100 projects; 10 branches/project; 100 CU-hours/project/month; 1 GB Postgres/project, 20 GB/account; 5 GB transfer/project/month; sleeps after 5 minutes idle. | Compute/transfer exhausted: compute suspended until reset or upgrade. Storage-growing operations fail at the cap. It does not automatically delete memories or provide a paid allowance. Remain on Free; no paid upgrade authorized. |
| R2 Standard | Account-wide 10 GB-month storage, 1M Class A and 10M Class B operations/month; direct R2 egress free. | **Usage-based billing**, not a hard free cap: extra storage $0.015/GB-month, A $4.50/million, B $0.36/million. Budget alerts do not stop usage or billing. |

Sources: [Render specifications](https://render.com/docs/compute-plans),
[Render Free](https://render.com/docs/free), [Render pricing](https://render.com/pricing),
[Neon limits/overage behavior](https://neon.com/docs/introduction/plans),
[R2 pricing](https://developers.cloudflare.com/r2/pricing/),
[budget alerts](https://developers.cloudflare.com/billing/manage/budget-alerts/).

Neon advertises Free signup without a credit card; confirm the selected organization's
actual Free status before creating the project. Render's public documentation
describes no-payment-method behavior, but does not guarantee that a particular
account will not require payment verification. Stop if checkout requires a charge,
upgrade or billing authorization not already approved. Cloudflare requires an R2
subscription checkout and a primary payment method for product purchases; inspect
the actual account checkout. **Do not complete R2 checkout without explicit user
approval of the overage exposure.** No such approval has been received.
[Neon signup](https://neon.com/blog/thousands-of-neon-projects-now-included-in-your-pricing-plan),
[R2 activation](https://developers.cloudflare.com/r2/get-started/),
[Cloudflare payment requirements](https://developers.cloudflare.com/billing/get-started/create-billing-profile/).

The intended cost is $0 while all allowances are respected, not a guaranteed
zero-dollar liability. Existing projects share allowances. R2 signed GETs can be
repeated directly without contacting this app, so storage quotas/rate limits do
not bound Class B billing. Other account activity, orphan objects, retained data,
backups and metadata operations also matter. No software quota is represented as
a provider-enforced spending cap.

## Resource findings and deployment gate

Docker is unavailable and WSL has no installed distribution on this workstation.
However, [manual GitHub Linux run 41355405807](https://github.com/aee4/mustaaaaaard-27/actions/runs/41355405807)
successfully built the production image and passed the 512 MiB/no-swap/0.1 CPU
cgroup gate without installing Docker/WSL locally. That CI run approximates the
target and does not establish actual Render performance.

Supporting Windows tests did run the real backend/FFmpeg process tree in a Job
configured with 512 MiB committed-memory limit, and a CPU-rate cap approximating
0.1 CPU. Windows committed memory is not equivalent to Linux RSS/cgroup accounting;
the Job even reported a peak above its configured limit in the original preset.
These are stress results, not proof of Render compatibility.

The current approved acceptance policy is **720p maximum**, with validated remuxing
instead of encoding. Three supporting Windows 512 MiB / approximate 0.1 CPU runs
accepted 30s / exactly 50 MiB 1280×720 and 720×1280 H.264/AAC fixtures.
The last run also included a 720p/30fps H.264 High-profile B-frame fixture: 54.10s
HTTP acceptance, peak 140,247,040 bytes (~134 MiB committed memory) across the
process tree. Video=3, gallery=0, feed and ranking checks passed. See
[video processing](video-processing.md) for codec rules, all evidence and gaps.
This resolves the observed Windows encoder failure; **Linux execution remains a
required pending gate**, along with account eligibility and R2 overage approval.

Historical pre-change findings below used the old encoding pipeline, not the
current policy. Those real HTTP workloads used native PostgreSQL/MinIO and synthetic
H264/AAC MP4 fixtures: 30.000 seconds, 1920×1080 and 3840×2160, each exactly 52,428,800 bytes.
Motion/noise/audio are generated and a valid MP4 free box pads the byte boundary.
Independent FFprobe confirmed their dimensions/codecs/duration. Tests exercise
capture-session acceptance, video=3, gallery=0, feed and rankings. Test auth is
enabled **only on the loopback synthetic server**, not production.

| Profile | 1080p result | 4K result | Reported peak |
|---|---|---|---|
| One thread, veryfast, 512 MiB, unrestricted CPU | Accepted, 28.58s | Encoder allocation failure; final classification 503 media_resources_exhausted | About 521 MiB |
| One thread, veryfast, 512 MiB, approximate 0.1 CPU | 503 media_processing_timeout, 123.55s | Failed | About 521 MiB |
| One thread, ultrafast, 512 MiB, approximate 0.1 CPU | Accepted, 125.84s total HTTP time | **503 media_processing_timeout, 124.10s** | About 401 MiB |

Those results blocked the previous 4K pipeline. New uploads above 720p are now
rejected under the user's explicit approval; existing videos remain untouched.
No encoder, preset, downscaling or automatic conversion remains in the current
upload path. Duration, size, validation and scoring guarantees remain. Do not
substitute these historical results for the pending Linux remux verification.

Artifacts: .tools/free-tier/windows-512-final.json,
windows-512-cpu01.json, windows-512-4k.json and
windows-512-ultrafast-cpu01.json. Diagnostics omit tokens, media and signed URLs.

On a Docker-enabled Linux runner, use the isolated test stack (no working volumes):

```powershell
# From repository root; host FFmpeg/FFprobe and uv installed.
uv run --directory backend python -m scripts.prepare_resource_media
docker compose -p mustard-resource-check -f compose.resource.yaml up -d --build
# Wait for http://127.0.0.1:58001/api/ready to return 200.
uv run --directory backend python -m scripts.resource_smoke --base-url http://127.0.0.1:58001 --report ../.tools/free-tier/linux-512.json
docker stats --no-stream
docker compose -p mustard-resource-check -f compose.resource.yaml exec app cat /sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.events
docker compose -p mustard-resource-check -f compose.resource.yaml stop
```

The Compose file enforces memory/swap=512m and CPUs=0.1. Record cgroup memory peak,
OOM events, per-upload latency, repeatability and exit codes; one success is not a
reliability claim. Do not use the synthetic development-auth settings publicly.
Windows supporting reproduction is `uv run --directory backend python -m
scripts.windows_budget --cpu-fraction 0.1 --report ../.tools/free-tier/windows-check.json`;
it requires the separate mustard_resource_test DB and native service variables.

## Prepared controls

- Root Dockerfile builds React with production Vite, installs FFmpeg/FFprobe and
  runs one unprivileged Python web process. frontend/dist and /api share one origin;
  /auth/google and callback route to the existing backend. Storage is always S3;
  local disk is temporary processing space only.
- render.yaml specifies only one `plan: free` web service. No managed Render DB,
  paid cron, persistent disk, paid workspace or paid pre-deploy command is declared.
  It validated against Render's current published JSON schema.
- MEDIA_CONCURRENCY=1 serializes sanitization/storage acceptance per process;
  decoder and filters are bounded to one thread; videos use stream-copy remuxing,
  not an encoder. Other uploads receive a
  retryable 503 media_busy, preserving their idempotency key. Resource exhaustion
  and processing timeout are 503; corrupt media remains 422.
- HTTP concurrency is 16 so browser asset connections do not exhaust a four-slot
  server; expensive media concurrency remains one. A compiled-app browser check
  exposed and fixed the lower connection limit returning 503 for favicon/assets.
- Migration 0003 tracks storage reservations. STORAGE_QUOTA_BYTES=8000000000 and
  STORAGE_OBJECT_QUOTA=10000 are global across groups in this dedicated DB/bucket.
  PostgreSQL advisory locking serializes quota checks before PUT. Pending/failed
  object bytes remain reserved until deletion is confirmed; removed posts retain
  their byte reservation until cleanup. Replays do not consume another reservation.
  Quota failure is 409 storage_quota_exceeded with a clear message. No memories are
  silently deleted. Unknown legacy sizes pause writes until operator reconciliation.
  Use `python -m app.cli reconcile-storage` with the proper private environment;
  measuring objects makes billable HEAD requests and requires prior R2 approval.
- Production R2 config refuses startup unless positive quotas and explicit
  R2_BILLING_ACKNOWLEDGED=true are set. The supplied template leaves it false.
- Render Free cannot run pre-deploy commands or shell/one-off jobs. The startup
  release runs schema migrations under a PostgreSQL session advisory lock before
  serving. No development data is imported. Cleanup runs hourly **only while awake**,
  and only removes user-removed/abandoned media plus expired auth/rate metadata.
  Sleeping/restarts can delay cleanup and hold quota; no paid scheduler was added.
- Health checks use /health to avoid continuously waking Neon or spending R2 HEAD
  operations. /api/ready remains an explicit DB/schema/bucket check. At fixed 0.25 CU,
  100 CU-hours is only 400 awake hours/month; do not assume always-on DB service.
- Native session/CSRF logic is preserved: Secure/HttpOnly/SameSite=Lax, host-only
  cookies, exact Origin allowlist and session-bound CSRF header. Provider URL sets
  BASE_URL; no cross-site cookie dependency. Proxy trust is restricted to explicit
  IPs/CIDRs, never `*`; default ignores forwarded headers from non-loopback peers.
  OAuth uses configured HTTPS URLs; do not trust user-supplied forwarded hosts.
  If verified proxy peers are unavailable, login rate limiting conservatively sees
  the proxy IP. Confirm this on the actual host before public acceptance.
- DEV_AUTH=false in production and development form absent from the compiled app.
  Configuration/CLI errors suppress secret input/local-variable dumps.
- Supplied favicon.png is preserved. Generated 16/32px PNG, ICO, 180px Apple icon
  and 192/512px images are in frontend/public. frontend/index.html wires icons,
  exact browser title, description and mustard theme color. No PWA was added.

## Ordered account and secret setup, after the deployment gate passes

1. Verify the chosen Render workspace is Hobby + Free instance and has enough
   shared hours/build/bandwidth remaining. Check payment-method and overage behavior
   directly; don't add a paid plan or billing authorization to bypass a restriction.
   Verify Neon organization is **Free**, with sufficient compute/storage/transfer.
   Connect the accounts using their official login/connector; never paste keys here.
2. Create an **empty** Neon Free Postgres project near Render Frankfurt. Choose
   direct TLS connection for migrations and this small connection pool (two DB
   connections; no overflow). Put the connection string directly into Render's
   DATABASE_URL secret. postgres:// and postgresql:// are normalized to psycopg.
   Neon Free uses a public authenticated TLS endpoint; it is not private networking
   or a paid IP-allowlist deployment. Do not import local users, sessions or media.
3. **Stop for explicit R2 overage approval before checkout.** After approval, create
   a new dedicated Standard bucket named mustaaaaaard-production; public r2.dev
   access and custom-domain/public access remain disabled. Create bucket-scoped
   object read/write credentials including the HEAD/List operations this app needs.
   Enter keys only in Render's secret manager. Do not reuse a populated bucket with
   an unrelated/new empty DB: orphan cleanup assumes exclusive ownership of media/.
4. Connect a private source repository to Render. Create the web service from the
   root Dockerfile with root build context, **Free** plan, Frankfurt and auto-deploy
   off. There is no Git metadata/remote in this workspace, so repository connection
   is an outstanding manual step. Keep external request/query/body logging disabled.
5. Copy non-secret settings from render.yaml. Set secrets DATABASE_URL,
   GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, S3_ACCESS_KEY and S3_SECRET_KEY directly
   in Render. Generate SECRET_KEY randomly (32+ characters). S3_ENDPOINT is
   `https://ACCOUNT_ID.r2.cloudflarestorage.com`, S3_REGION=auto; do not rewrite
   signed URLs or substitute r2.dev. BASE_URL/ALLOWED_ORIGINS derive from Render's
   allocated RENDER_EXTERNAL_URL, or set them explicitly to that exact HTTPS origin.
   Set R2_BILLING_ACKNOWLEDGED=true **only after approval**, keeping both quotas.
6. In Google Console create/select a **Web application** OAuth client. For the
   allocated URL `https://ACTUAL-SERVICE.onrender.com`, the JavaScript origin entry
   is that exact origin and redirect URI is exactly
   `https://ACTUAL-SERVICE.onrender.com/auth/google/callback`. Configure consent
   audience/test users for the intended accounts. Put the client secret only in
   Render. Production Google consent/callback is not yet verified.
7. Configure R2 CORS for that exact app origin: GET/HEAD, allow Range, expose
   Content-Range/Accept-Ranges/Content-Length/ETag as needed for playback. Browser
   media uses short-lived signed GETs, not app cookies. Do not enable public reads.
8. Only after eligibility, resource and R2 approval gates pass, deploy. Startup
   applies migrations before serving; /api/ready must return 200. Confirm /api/auth/dev
   returns 404 and compiled frontend has no development login. Do not repeatedly
   force restarts or disable sleep to evade free-tier limits.
9. Log in through Google as the intended owner. Obtain only your non-secret user
   UUID from your own /api/auth/session response. Because Free lacks shell access,
   run the operator command locally with a private, ignored production env file:
   `uv run --directory backend --env-file C:/PRIVATE/mustard-production.env python
   -m app.cli bootstrap-user --user-id YOUR_UUID`. Follow backend/production.env.example;
   confirm the effective environment/database hostname without displaying credentials
   before mutation. This requires an existing verified Google user, not a first visitor.
10. Verify two actual Google users, admin/bootstrap, create/join/invite/switch,
    camera photo=1, video=3, gallery=0/no streak, captions, feed and leaderboards.
    Verify media unsigned access is denied, signed playback/range works, expiry
    refresh works, quotas reject cleanly, and repeated upload retries don't duplicate.
    Test actual Android/iPhone over provider HTTPS; record consent/device/browser
    results separately from synthetic desktop tests.

## Backup and restore

Free does not provide a full production backup/SLA guarantee. Before acceptance,
arrange encrypted off-host DB and matching R2 backups within approved usage. With
a compatible PostgreSQL client and secure pg_service/pgpass files outside Git:

```powershell
pg_dump --dbname=service=mustard-production --format=custom --file=mustard.dump
# Restore only into a separate, empty target; never overwrite the working DB.
pg_restore --dbname=service=mustard-restore --no-owner --no-acl mustard.dump
# AWS credentials must come from a protected profile/environment, never argv/chat.
aws s3 sync s3://mustaaaaaard-production C:/ENCRYPTED-BACKUP/media --endpoint-url https://ACCOUNT_ID.r2.cloudflarestorage.com --only-show-errors
# Matching restore to a separate approved bucket; no --delete.
aws s3 sync C:/ENCRYPTED-BACKUP/media s3://NEW-RESTORE-BUCKET --endpoint-url https://ACCOUNT_ID.r2.cloudflarestorage.com --only-show-errors
```

Quiesce writes for a consistent DB/media pair. Retain fingerprints, upload rows,
audit and grace history. R2 backups/read requests also consume allowances and can
incur charges; creating extra Neon branches consumes its Free limits. Run migrations,
readiness and real acceptance against the isolated restore before switching URLs.
No restore or production backup is claimed performed.

## Actual local verification

Ruff check/format and mypy passed. Full backend suite with the current 720p remux
path: **116 passed**, no skips, 21.87s, two existing httpx adapter deprecation warnings.
Alembic check/current: no new operations, 0003 head. Coverage
includes atomic concurrent byte/object reservations, unknown legacy usage, cleanup
debt, replay, busy processor retry, existing scoring/captions/auth, and secret-safe
configuration errors, codec/resolution rejection, independent decoded duration,
unchanged decoded picture hashes, rotation and container/stream/SEI metadata removal.
Frontend ESLint/TypeScript, **20 unit tests** and production build passed.
**Eight real-backend browser tests** passed in 23.8s using synthetic camera/audio
devices; real signed MP4, VP8/Opus and VP9/Vorbis playback and unsigned access
denial were verified with native private MinIO. The previous audit found zero issues;
dependencies did not change in this video update.
After the final HDR guard, the remux playback/unsigned-access browser test passed
again (1 test, 3.6s). Render blueprint still validates against its published schema.
Native localhost:3000 and /api/ready remain available (200), loopback only.

The built React app was also served directly from the new FastAPI/Starlette web
entrypoint on a separate loopback port. Chrome verified the exact title, favicon
derivatives, loaded Inter/license, Google entry and absence of development login.
That local server returned /api/ready=200 and development POST /api/auth/dev=404.
This is local presentation/routing/disabled-auth evidence, not real Google consent
or production verification. Production account quotas, R2 unsigned/signed access,
provider TLS/cold starts, Neon connectivity and physical phones remain unverified.
