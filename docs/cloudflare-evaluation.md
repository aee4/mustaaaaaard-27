# Cloudflare deployment evaluation — 2026-11-01

Status: documentation/code review only. No Cloudflare resources, paid plans or
deployments created. No Fly.io apps changed. Existing deployment preparation is
preserved; it is not evidence of a verified production deployment. Docker is
unavailable locally. Actual Cloudflare upload, cookie, Google consent, database
connectivity and physical-device tests remain outstanding.

## Compatibility with the actual application

| Component | Assessment |
|---|---|
| React/Vite | Compatible with Workers Static Assets or Pages. Build frontend/ with npm ci and npm run build; publish dist. Existing assets fit the 25 MiB/file static limit. Keep development login compiled out. Configure SPA navigation and ensure API/auth requests never fall back to index.html. |
| Private R2 | Compatible in principle with the existing boto3/SigV4 adapter. Set S3_ENDPOINT to the account's HTTPS S3 API endpoint, S3_REGION=auto, private bucket and bucket-scoped server credentials. Persistent uploads stay in R2. |
| PostgreSQL | Keep real managed PostgreSQL. App uses synchronous SQLAlchemy/psycopg, PostgreSQL upserts, locks and Alembic. D1 and Durable Object SQLite are not substitutes. Hyperdrive connects/pools an existing external database; it does not supply managed PostgreSQL storage. |
| Python Workers | Not a deployment target for the unchanged backend. FastAPI support exists, but this app also invokes native FFmpeg/FFprobe subprocesses, uses thread-pooled synchronous handlers, native dependencies and temporary files. Python Workers run in Pyodide/WebAssembly, not a normal Linux process. |
| Cloudflare Containers | A viable candidate for preserving CPython/FastAPI/Uvicorn/FFmpeg in a Linux image, with external PostgreSQL. Requires a Worker/Container lifecycle adapter, secrets, routing, startup/readiness, placement near the DB, controlled migrations and cleanup scheduling. Compatibility is not yet execution-verified. |

Sources: [Static Assets](https://developers.cloudflare.com/workers/static-assets/),
[Python runtime](https://developers.cloudflare.com/workers/languages/python/how-python-workers-work/),
[standard-library restrictions](https://developers.cloudflare.com/workers/languages/python/stdlib/),
[Containers](https://developers.cloudflare.com/containers/),
[database options](https://developers.cloudflare.com/workers/databases/connecting-to-databases/).

Current Python Hyperdrive documentation explicitly supports psycopg and synchronous
SQLAlchemy. Therefore, the assessment does **not** assume Python database support
is absent. Binding/driver setup and concurrency behavior would still need changes
and tests; native media processing remains the decisive Workers incompatibility.
[Python Hyperdrive](https://developers.cloudflare.com/hyperdrive/examples/python-workers/).

## Uploads, execution and persistence

The backend accepts photo files up to 15 MiB and video files up to 50 MiB, with a
51 MiB HTTP envelope by default. FFmpeg gets 120 seconds, with additional probes,
database/storage work and a 240-second client timeout. Workers Free has 128 MB
memory/10 ms CPU; Paid permits up to five minutes CPU. HTTP wall time has no fixed
Workers limit while the client remains connected. These are Worker limits, not
the container's CPU/RAM limits. Stream proxied bodies; do not buffer uploads in
Worker memory. Free/Pro zone incoming request limits are 100 MB, enough for the
current input envelope. [Workers limits](https://developers.cloudflare.com/workers/platform/limits/).

The app can produce a sanitized video approaching 200 MiB and currently uses one
boto3 PutObject. A Container **outbound handler** has a separate 100 MiB/request
limit. Do not confuse this with the incoming 50 MiB file limit. If using that
handler, multipart S3 upload with bounded parts is needed, or an approved higher
limit; alternatively verify an appropriate direct egress path. Streaming/chunked
encoding does not bypass the handler limit.
[Container limits](https://developers.cloudflare.com/containers/platform/limits/).

Containers require linux/amd64 images. Disk is ephemeral by default, which suits
the app's temporary processing files; it must not hold persistent media or the
database. Check in-flight work before sleep/restarts and test the existing leased
upload/idempotency recovery. With internet disabled, non-HTTP database ports are
blocked: HTTPS-only outbound allowlisting alone cannot enable PostgreSQL TCP.
Use a separately verified secure database network path.
[Lifecycle](https://developers.cloudflare.com/containers/concepts/architecture/),
[outbound networking](https://developers.cloudflare.com/containers/configuration/outbound-traffic/).

Cloudflare's ordinary origin proxy documents a **125-second read timeout** and
30-second write timeout. A Worker having unlimited HTTP wall time does not prove
every downstream origin/container connection supports the app's entire budget.
Test the exact route with slow uploads and >125-second backend processing before
using an API proxy. Do not silently lower media limits or replace acceptance with
an asynchronous protocol. [Connection limits](https://developers.cloudflare.com/fundamentals/reference/connection-limits/).

## Cookies, CSRF and Google

The existing client calls same-origin /api, sends credentials and in-memory CSRF,
and navigates to /auth/google. Backend cookies are host-only, HttpOnly,
Secure in production, SameSite=Lax. Both OAuth state and application sessions must
remain on the browser's canonical origin.

An independent pages.dev/workers.dev frontend making direct requests to an
onrender.com API is cross-site. CORS alone cannot make current Lax cookies work;
changing them to SameSite=None also does not defeat third-party-cookie blocking.
Do not claim that topology compatible without changing and testing authentication.

A same-origin Worker gateway is possible in principle: forward /api and /auth to
the container without caching, preserve Origin, CSRF, cookies and Set-Cookie,
restrict the upstream, and adapt allowed-host checks to the real gateway/backend
hosts. Validate timeout and cookie behavior on actual provider domains first.

Use the final canonical HTTPS provider origin as BASE_URL and the sole normal
ALLOWED_ORIGINS entry. Google Web OAuth redirect is exactly
`BASE_URL/auth/google/callback`; if adding an authorized JavaScript origin, use
BASE_URL with no path. No custom domain is required for this server-side flow.
Keep secrets in the provider secret manager, disable dev auth on both sides,
and establish the production admin through the explicit operator bootstrap.
Actual Google consent/callback and browser tests are still required.
[Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server).

R2 signed GETs use its S3 API domain, not r2.dev or a custom media domain. Keep
public access disabled. Current expiry is 120 seconds; authorization happens before
signing. Configure GET/HEAD CORS for the canonical app origin and test Range/video
playback, expired-link refresh, and denial without the signature. R2 uses bearer
URLs rather than the application's session cookie. Never log their query strings.
[R2 signed URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/),
[R2 CORS](https://developers.cloudflare.com/r2/buckets/cors/).

## Verified list prices and illustrative cost

USD, checked 2026-11-01; taxes, other account usage and overages excluded.

- Static Assets: free, unlimited asset requests. Dynamic Worker requests are
  separate; Free allows 100,000/day. Paid starts at $5/month, including 10 million
  requests and 30 million CPU-ms; overages $0.30/million requests and $0.02/million
  CPU-ms. [Asset billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/),
  [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/).
- R2 Standard: 10 GB-month, 1 million Class A and 10 million Class B operations
  included monthly. Beyond that: $0.015/GB-month, $4.50/million A and
  $0.36/million B; direct R2 egress is free. These are allowances, not a hard spend
  cap. [R2 pricing](https://developers.cloudflare.com/r2/pricing/).
- Containers require Workers Paid. Included monthly: 25 GiB-hours memory,
  375 vCPU-minutes, 200 GB-hours disk. Additional rates: $0.0000025/GiB-second,
  $0.000020/active-vCPU-second and $0.00000007/GB-second. Workers, Durable Objects,
  logs and container egress can add costs. Memory/disk billing follows provisioned
  size while awake; CPU follows active usage. [Container pricing](https://developers.cloudflare.com/containers/platform/pricing/).

Example, not a quote: standard-1 (4 GiB RAM, 0.5 vCPU, 8 GB disk) awake for 730
hours, with 10 active vCPU-hours, costs about **$32.75/month** including the $5
Workers base, before database/other usage. At 30 awake hours and five active
vCPU-hours the same calculation is **$5.87**. Sleep behavior changes the bill
substantially; FFmpeg latency/throughput at this size has not been benchmarked.

## Recommendation preserving the application

Do not rewrite the backend for Python Workers. Cloudflare Containers is plausible
but needs a paid pilot and external managed PostgreSQL; it is not an already
verified complete stack or a free PostgreSQL-inclusive service.

A conservative hybrid is Cloudflare frontend asset hosting + private R2, with
FastAPI in a Render Linux container and managed Render PostgreSQL on the same
private network. For the first provider-domain deployment, keep the browser's
canonical app document at the Render HTTPS URL and optionally serve its versioned
JS/CSS/fonts from Cloudflare. Vite's asset base and public-asset CORS need configuring;
the HTML and published asset versions must match. Keep the Cloudflare asset URL
from becoming a second unsupported login entrypoint. Browser API/OAuth requests
then stay directly same-origin on Render, avoiding both cross-site cookies and
Cloudflare origin timeouts for uploads. Private media still streams directly from R2.

If a workers.dev URL must be the primary app URL, use the same-origin Worker
gateway described above only after its long-request tests pass. Otherwise retain
the Render app URL rather than redesigning scoring/upload/authentication for hosting.

The hybrid baseline is **about $32/month**: Render 1 CPU/2 GB container $25,
managed PostgreSQL 256 MB $6, scheduled cleanup minimum $1; Cloudflare static
assets and R2 within free allowances $0. Render Hobby workspace is $0, currently
includes 5 GB bandwidth; excess is $0.15/GB. Database includes 1 GB SSD; additional
database storage is $0.30/GB-month. Build/backup/usage charges may add costs.
This small database is a starting size, not an HA service. No capacity benchmark
has been run. A paid Worker gateway would add at least $5/month.
[Render pricing](https://render.com/pricing), [cron minimum](https://render.com/docs/cronjobs).

Render's live pricing page was checked in desktop Chrome as well as official
documentation because its price table is loaded dynamically. Render documents
HTTP responses up to 100 minutes, but the app retains its 240-second client budget.
Do not substitute its 30-day, no-backup free PostgreSQL for production persistence.
[HTTP limits](https://render.com/docs/render-vs-heroku-comparison),
[free-tier restrictions](https://render.com/docs/free).

Next decision is hosting/budget approval, not credentials in chat. After approval:
connect the selected accounts, create an empty production DB/private bucket,
set secrets securely, run controlled migrations, configure the allocated provider
URL in Google, bootstrap the verified owner, then run actual production acceptance.
