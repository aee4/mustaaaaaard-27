# Cloudflare frontend and Render gateway

Canonical frontend: https://mustaaaaaard-27.eeyramagbetor.workers.dev

Fallback/backend: https://mustaaaaaard-27.onrender.com

Cloudflare Worker `mustaaaaaard-27`, account `8b158add944122fbd78f9d7ff7dbed01`.
Render service `srv-dbk7ej942hec73ervp5g`, Free, auto-deploy off. Existing Neon
project `morning-shape-51677264`, existing private R2 bucket
`mustaaaaaard-production`. No schema revision, secret rotation or data migration.
See PROGRESS.md for actual deployed versions, checks and remaining limitations.

## Routing and limits

`frontend/wrangler.jsonc` publishes Vite dist as Workers Static Assets, with SPA
fallback. Only /api and /auth invoke the gateway. These routes never fall back to
index.html. Static asset delivery is free/unlimited; gateway use consumes Workers
allowances (Free: 100,000 requests/day, 10ms CPU, 128MB). No plan upgrade was requested.
Account billing subscription visibility is unavailable through the OAuth connector;
no billing/subscription endpoint was modified.

The gateway fixes the upstream to the existing Render origin, preserves browser
Origin/cookies/CSRF/idempotency headers, streams request/response bodies directly,
does not follow redirects, and forces no-store for API/auth responses. Preview
URLs are disabled and alternate-origin API/auth requests are rejected. No app,
database, Google or R2 credentials are placed in Worker code or frontend bundles.
Worker observability is disabled to avoid persisting query strings or cookies.
R2 playback remains direct signed GET/Range, private; signed responses override
Cache-Control to private,no-store even for preexisting objects.

Current photo/video limits remain 15/50 MiB; the backend HTTP envelope and gateway
declared-length check are 51 MiB. Unknown-length streams remain bounded by the
backend's receive guard. Cloudflare's 100MB incoming request allowance exceeds
this envelope. Client media timeout remains 240s; FFmpeg budget remains 120s.
Workers document no fixed wall-time limit while clients remain connected, but
ordinary Cloudflare origin connections document 125s read/30s write limits.
An actual >125s upload/processing route must be measured before claiming the
entire 240s budget works. A synthetic local test cannot prove provider limits.
Do not lower media limits, buffer uploads, purchase a timeout upgrade or silently
switch to cross-site cookie authentication to work around a failed test.

Sources: [Workers limits](https://developers.cloudflare.com/workers/platform/limits/),
[static asset billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/),
[origin limits](https://developers.cloudflare.com/fundamentals/reference/connection-limits/).

## Google and application settings

In the **existing** Google Web OAuth client's authorized JavaScript origins add:

`https://mustaaaaaard-27.eeyramagbetor.workers.dev`

Authorized redirect URI:

`https://mustaaaaaard-27.eeyramagbetor.workers.dev/auth/google/callback`

Keep the original Render origin and callback registered for rollback. Do not
create another client or rotate Google secrets. Console path: Google Cloud Console
→ APIs & Services → Credentials → existing OAuth 2.0 Web client → edit.

Render nonsecret settings for the new release:

```dotenv
BASE_URL=https://mustaaaaaard-27.eeyramagbetor.workers.dev
ALLOWED_ORIGINS=["https://mustaaaaaard-27.eeyramagbetor.workers.dev","https://mustaaaaaard-27.onrender.com"]
BACKEND_HOSTS=["mustaaaaaard-27.onrender.com"]
DEV_AUTH=false
COOKIE_SECURE=true
```

OAuth uses the gateway's exact configured application origin, or the exact allowed
Render origin on the fallback entry point. State, nonce, PKCE and session cookies
remain host-only, Secure, HttpOnly, SameSite=Lax. Browsers must sign in once on the
new host; an existing Render cookie cannot transfer across provider domains.
The database identity and original Render session remain intact. Relative return_to
is signed into OAuth state storage; invitations/destinations survive redirects.
R2 GET/HEAD/Range CORS permits exactly these two origins, without wildcards.

## Deploy

1. Run backend Ruff, format check, mypy and pytest against dedicated real PostgreSQL/
   MinIO, frontend lint/typecheck/unit tests/build, and real-backend browser tests.
2. Build `npm run build --prefix frontend`. With authorized Cloudflare CLI credentials,
   run Wrangler deploy using `frontend/wrangler.jsonc` from frontend/. Reuse this
   Worker; do not create a Sites project, paid plan or alternate production domain.
   The connected API can also upload static assets using a manifest/session, then
   the Worker multipart API. `uv run --directory backend python -m scripts.cloudflare_assets
   manifest` emits public hashes. Its upload mode accepts the short-lived upload
   session JSON through hidden stdin and returns the completion JWT to the calling
   tool in memory; never log/save that output. `_headers` requires Wrangler's parser
   when deploying via CLI; direct API deployments must supply parsed asset headers.
3. Verify static deep links while API readiness fails, gateway no-store/session/
   CSRF, and preview rejection before updating backend public settings.
4. Add Google entries above; deploy the tested backend commit with the settings
   above through Render. Merge only intended environment keys; never replace all
   variables. Preserve secrets, Free plan, disabled auto-deploy and original frontend.
5. Complete actual Google login and isolated upload/social/playback acceptance on
   the Cloudflare origin. Remove synthetic posts and objects, revoke temporary
   sessions, retain fingerprints/tombstones. Only then promote links to the new URL.

## Rollback

Keep using the original Render URL; no old-entry redirect or deletion is needed.
Restore BASE_URL to `https://mustaaaaaard-27.onrender.com`; keep that origin in
ALLOWED_ORIGINS and its Google callback/R2 CORS. Retaining both exact origins is
safe during rollback; remove the Cloudflare entries only after testing concludes.
If necessary redeploy known good Render commit
`19e3ddf6431c908a66397c99b8ca1adb7fd7421c`. No schema rollback is required.
Cloudflare can retain its assets or restore the prior Worker version. Do not
delete databases/buckets, rotate secrets, revoke original user sessions or remove
fingerprint/grace history. Never redirect the Render entry point until the new
origin's actual Google/session/upload flow is verified.
