# Progress

## Loading, performance and camera refinement — 2026-11-03

Implemented additive migration `0005` for intrinsic media dimensions and private
photo derivatives. New uploads preserve their sanitized original and create a
960px-bounded WebP thumbnail in private storage. The derivative is counted against
byte/object quota, protected by the existing active-membership/signed-URL path, and
is deleted together with its original. A resumable `backfill-thumbnails` operator
command supports existing live photos without rewriting originals, fingerprints,
captions, posts, scores or grace history. Real MinIO verification covered quota
rejection, lost storage response/resume, byte accounting, cleanup and preservation.

The feed uses a reusable decode-aware `MediaImage`: intrinsic frames, neutral
shimmer, short opacity reveal, cached-image fast path, reduced-motion support,
bounded signed-URL renewal and explicit retry/offline state. Initial first-visible
media is eager with only the LCP image prioritized; below-fold media is deferred.
Private welcome/gallery originals are fetched only in the full-quality viewer.
Synthetic before/after browser measurement using the previous release bundle showed
initial media authorization calls reduced from **17 to 2**. Browser-rendered exact
R2 byte totals were unavailable because signed R2 cross-origin responses omit
`Content-Length`; the test records request reduction and derivative selection.

Added matching feed/profile/leaderboard/comment skeletons, append skeletons,
scroll restoration and media-query isolation so likes/comments do not replace media
or shift the feed. Capture now offers a safe-area-aware familiar camera workspace,
Photo/Video selector, gallery picker, working front/rear switch, front-only preview
mirroring, usable-frame gating, explicit camera/microphone permission explanations,
denial/busy/revocation states and track cleanup. Native still output remains
high-resolution; fallback uses intrinsic frame dimensions and preview-matched native
still settings. Camera controls are fixed above mobile navigation while active.

Actual checks: backend **148 passed** with real PostgreSQL/MinIO/FFmpeg (two
existing adapter deprecation warnings); backend Ruff/format/mypy and Alembic drift
check passed. Frontend lint/typecheck, **36 unit/gateway tests**, production build,
the existing 15 real-backend Chrome tests, and 3 new real-backend Chrome loading /
camera tests passed. New camera checks use synthetic browser streams only; no
physical Android/iPhone camera or keyboard/safe-area verification was performed.
Deployment and production smoke evidence is recorded after the compatible backend
and Cloudflare asset release complete. Rollback is the prior Render commit and
previous Cloudflare Worker deployment; migration downgrade removes derivative
metadata only and must not be used after thumbnails exist without cleanup.

## Cloudflare static frontend and immediate Render wake-up — 2026-11-03

New canonical URL: https://mustaaaaaard-27.eeyramagbetor.workers.dev.
Fallback/backend retained: https://mustaaaaaard-27.onrender.com. Cloudflare Worker
deployment `0e09816c6b8b428f9a711b00a3815d11` publishes the final static bundle and
fixed-backend streaming gateway. Render deployment `dep-dbkobuei0phs73as02u0` is live
at `23bced5e8cd8ce837e5c1aa529e5c6c9fd1c3616`. Render remains Free/auto-deploy off;
existing Neon and private R2 are reused. No domain purchase, plan upgrade,
subscription activation, schema revision, secret rotation or scheduled keep-alive.
Cloudflare billing subscription reads are unavailable to the OAuth connector;
no billing endpoint was modified. Static delivery uses the free asset service.

Read AGENTS, deployment configs/evaluation, README/SPEC and existing progress first.
Latest explicit deployment authorization overrides the older no-deploy project rule.
Retained earlier uncommitted deployment/photo documentation/config and local skill
files. Application commits are 91b540e and 23bced5; subsequent verification/docs
changes do not alter the deployed application. Existing data/media were not moved.

Readiness starts before React render on every document/entry route. One controller
uses uncached JSON ok=true probes, 12s request budgets, 1..8s backoff, 120s overall
timeout, cancellation and explicit Retry. Login waits for readiness plus initial
session resolution; API actions reject before sending while connecting. Cached
interface/navigation/local drafts remain usable on later failures. Recovery refetches
safe queries only; explicit mutation/upload retries retain existing keys/bytes.
Gateway forwards streams directly to only the configured Render origin, keeps
Origin/cookies/CSRF/idempotency, handles redirects manually and never caches API/auth.
Render HTML is converted to not-ready JSON; interrupted Google navigation returns
to static UI with a tab-local relative destination (no auth tokens in browser storage).
Preview URLs disabled; alternate-origin production API/auth denied. No persistent
Worker request logs, browser secrets or private media in public artifacts.

Merged only BASE_URL, exact ALLOWED_ORIGINS, BACKEND_HOSTS and explicit secure/dev
auth flags into Render; secrets preserved. Both origins remain allowed for fallback.
User added the exact Cloudflare Google origin/callback and confirmed real Google
sign-in opens the existing group. Automated initiation checked the correct callback
and secure cookie on both hosts. OAuth relative destinations/invites survive login;
state/nonce/PKCE, host-only HttpOnly Secure Lax cookies and CSRF are preserved.
R2 CORS now permits precisely the new and old origins. Signed GETs force private,
no-store even for preexisting objects, without rewriting those objects.

Actual local checks: **147 backend tests**, no skips, real PostgreSQL18/MinIO/FFmpeg;
33 frontend unit tests; four gateway tests; **15 real-backend Chrome browser tests**.
Ruff/format/mypy, ESLint/types, production build passed. OpenAPI matches all 25
checked-in paths; API types regenerated with no contract change. Linux CI passed:
backend run 41593132059, frontend 41593132009, both exact deployed commit. Earlier
91b540e Linux workflows also passed. Three further read-only readiness browser
tests passed on hosted Cloudflare with simulated HTML/unavailable readiness,
timeout/Retry and auth destination restoration. Production compiled login, font
and icons passed in Chrome156; dev form absent. Test-only failures caught a session
bootstrap/login race and missing disabled-link role, both corrected. A camera
navigation run interrupted during live source edits was rerun successfully with
stable source; the final full run passed 15/15 in 46.2s.

Production acceptance reused the existing Google owner and Deployment verification
group with a distinct temporary session. Verified session/CSRF and production dev
auth denial; invite creation/existing-member join/revocation; captured photo=1,
video=3, gallery=0; normalized plain captions; same-key replay; feed, weekly/all
rankings=4, idempotent likes/comment retry/deletion. **50 MiB synthetic MP4 plus
multipart overhead passed through the gateway and replayed successfully.** A real
slow streamed multipart photo completed **200 in 130.1s**, same-key replay=200;
Neon showed zero idle-in-transaction sessions during streaming. Signed R2 Range
returned 206/exact-origin CORS/no-store; unsigned requests denied. Authenticated
production Chrome verified HttpOnly session, CSRF rejection and actual private R2
video playback. No private screenshots/traces or cookie/media/signed-URL logs.

Cleanup confirmed all four synthetic posts removed/captions cleared, their R2
objects deleted (HEAD404), reservations released, temporary invite revoked and
test session revoked. Fingerprints/tombstones remain; original live-post/session
sets preserved and verification-group rankings returned to baseline. User's new
real Google session and original Render sessions remain available. Local cleanup
removed 83 accumulated synthetic MinIO objects after browser tests.
Owned local Vite/Uvicorn/MinIO/PostgreSQL verification services were stopped;
production Render/Cloudflare/Neon/R2 were left available.

Limits: hosted readiness failure tests are simulated. Initial real gateway 429/
non-JSON responses and read timeouts later recovered to readiness200, but provider
sleep/wake timing was not independently confirmed. No forced production sleep or
active-user interruption. This improves waiting; Render Free cold starts remain.
The 130.1s test proves streaming duration, not >125s silent backend processing or
the entire 240s budget. Physical Android/iPhone capture and a second real Google
account/invite acceptance remain unverified. README and docs/cloudflare-frontend.md
contain deployment, exact Google/settings values and rollback to the preserved
Render URL/known-good commit; no data/schema rollback is needed.

## Private social release deployed and verified — 2026-11-02

Live URL: https://mustaaaaaard-27.onrender.com. Deployed exact commit
19e3ddf6431c908a66397c99b8ca1adb7fd7421c (feature 49425c4 plus join-test race fix),
Render deployment dep-dbkgshqjnfac73c16scg. Corrected backend CI 41536477976 and
frontend CI 41536477484 both completed successfully before deployment. Startup
applied additive migration 0004 and readiness is 200. Verified Render Free,
auto-deploy off, and every environment value unchanged before/after deployment.
No Fly.io, paid plan, infrastructure or OAuth/storage-secret change.

Ran the explicit seed-welcome CLI with the verified initial group UUID
bad0f3b9-c9ff-4c6f-a563-56575993e367 and its existing Google-authenticated admin.
Imported the supplied group selfie as the welcome cover plus 11 original photos
in a single private carousel. Two supplied social-app UI screenshots excluded.
One shared pinned parent, 11 hidden album children; system attribution, null
member author and zero points. A second identical CLI invocation retained all 12
post IDs and object records. Initial-group preexisting live-post set was preserved;
no fake account/member post or normal-feed flood was created.

Authenticated production checks used a distinct 15-minute session for the already
verified existing Google owner. All 12 signed photo downloads were pixel-identical
to EXIF-oriented decoded originals, with identical dimensions and no EXIF. No
resize/recompression, private images in public assets, saved production screenshots,
or credential output. Anonymous media API returned 401; unsigned R2 access denied.
Public production Chrome login check passed: Google entry/self-hosted font/icons
loaded, development form absent, /api/auth/dev=404. New public icons are monograms.

Reused the existing isolated Deployment verification group for one synthetic
gallery PNG. Verified PUT-like twice=1, DELETE-like twice=0, comment retry returns
same ID/plain text, own comment deletion, zero-point leaderboard. Production Chrome
passed welcome carousel navigation, literal comment rendering (no HTML), account
tour completion, and no horizontal overflow at 320/390/1440px. No private image
screenshots/traces were saved. Deleted the synthetic post via API, deleted only its
known R2 object and released that upload reservation; retained tombstone/fingerprint.
Temporary session revoked, original login preserved, prior tour completion state
restored so the owner can still experience first-use onboarding. Welcome album
and original live-post set confirmed preserved; environment values still unchanged.

An initial production harness used the wrong saved verification-group suffix;
its read-only assertion failed before importing or creating content. Corrected it
by matching the single existing verification group, then the full run passed.
No application change/redeployment was needed. Local owned MinIO/Vite/backend
verification servers stopped; preexisting PostgreSQL left running.

Evidence: 143 backend tests, 30 frontend unit tests, 12 real-backend browser tests,
plus final four affected tests and five corrected browser-file tests passed locally;
Ruff/format/mypy/lint/types/build/Alembic drift checks passed, both final Linux CI
workflows passed. Physical Android/iPhone camera/keyboard/safe-area checks and a
second real Google account are not automated verification. Previous personal-photo
favicon bytes remain in older Git history; this release replaces current public
assets and does not rewrite historical commits. Earlier deployment config/doc edits
remain outside this feature's commits. This final release evidence is local progress
documentation after the pinned production release; no additional app change.

## Private social redesign — 2026-11-02 (release preparation)

Read the explicit pasted request, AGENTS/SPEC/progress and current capture/feed/
media/auth/scoring implementation. Added migration 0004 without resetting data:
system welcome/album posts, composite-key likes, retry-unique comments and account/
version tour completion. Server membership/live-post/CSRF checks apply to every
social operation. Post/membership locks fence mutation/removal races; likes set/
unset idempotently, comment retries preserve hashes/tombstones and reject changed
text. Trimmed plain text comments max500, keyset pagination, own deletion/admin
moderation, 120 likes/min and 30 comment mutations/min. Scores/grace/video unchanged.

Compact cream/mustard/Inter feed, outline hearts/comments, private welcome carousel,
phone bottom sheet/desktop dialog, optimistic like rollback/rapid-tap protection,
same-key comment retry, four-step keyboard-modal tour with account persistence and
Profile replay. Tour pauses for dirty capture/upload, handles resize/scroll/missing
targets and reduced motion. Detailed capture/ranking rules are under How it works.
No notification/bookmark/comment-like placeholders. Public photo favicon replaced
with a round geometric monogram; earlier photo bytes remain in preexisting Git
history (not rewritten). New original photos never added to public assets/history.

Explicit seed-welcome command accepts the real initial group ID and active admin,
uses bounded lossless/metadata-stripping processing plus existing quota reservations,
and keeps object IO outside transactions. Children are not separate feed entries.
Repeat seed honors unpin/removal; whole-album deletion feeds normal object cleanup.
Verified correct production group UUID bad0f3b9-c9ff-4c6f-a563-56575993e367 by exact
existing name, one existing admin, no active posts. Render is Free/auto-deploy off;
Google/storage secrets present and not printed. No production mutation yet.
All 12 usable original photos exist; group selfie is the cover. Two screenshots
with social-app UI excluded from the album. design-input/ ignored before copying.

Backend Ruff/format/mypy passed; Alembic upgrade from 0003 over existing local
browser-test data and schema drift check passed. 143 pytest passed, no skips,
30.12s against real PostgreSQL/MinIO/FFmpeg (two upstream deprecation warnings).
Frontend lint/types/build and 30 unit tests passed. All 12 real-backend browser tests
passed in 33.8s; final four affected social/photo tests passed again in 11.9s after
caption placement and explicit rollback/rapid-tap coverage. Synthetic high-res
capture native/fallback remains 1920x1080, MAE0.01 vs downsampled720p59.36. Checked
320/390/1440px synthetic screenshots, fixed nav overflow and desktop dialog center.
No personal media in test screenshots/artifacts. Test harness fixes: wait for login
before CSRF tour completion, use a unique friend name after interrupted earlier runs.
Initial expected failures also caught stale schema readiness/old no-comments test.
Physical Android/iPhone camera, keyboard and safe-area checks remain pending.
Deployment and private original-photo import follow only after successful CI.
First remote backend CI passed, including migration round trip. Frontend CI passed
11/12 browser tests; membership-revocation test raced its own join completion after
the old section-label assertion was removed. Replaced the premature selector-visible
check with confirmed selected group UUID before revocation; deployment waits for
the corrected CI run. No production action taken during this gate.

## Photo quality and gallery release deployed — 2026-11-02

Inspected capture/gallery/backend/feed before changing settings: photos shared
the 1280x720 stream request with video; canvas already used intrinsic dimensions,
gallery retained original bytes, backend was lossless PNG/no resize with EXIF
orientation/metadata stripping, and feed served full images with contain rendering.
Implemented flexible independent 1080p photo requests, bounded native still-photo
capture where supported, default/settings/stream fallbacks, single JPEG 0.95 canvas
encode at actual dimensions, no upscaling, pre-allocation bounds, and async capture
cancel/double-click protection. Video constraints/rules and all scoring unchanged.
Gallery now has a prominent Upload from gallery action and Photo/Video controls
above the preview; original-byte/caption/progress/retry/error flow is preserved.
Updated multipart extension handling and SPEC/integration/phone docs.

Frontend lint/types/build and 30 unit tests passed. Backend Ruff/format/mypy passed;
137 pytest tests passed, no skips, 27.36s, real PostgreSQL/MinIO/FFmpeg. Added 7
high-resolution pixel/EXIF/metadata/limit tests. All 11 real-backend browser tests
passed in 36.1s, plus rerun of affected 3 after final allocation guard. Synthetic
chart output was 1920x1080 with error 0.00–0.01 versus 59.36–59.37 for a 720p
downsampled baseline. Gallery lost-response retry/preview/caption/progress and
photo/video zero points/no streak verified. Physical phones remain unverified.
Initial new browser-fixture failures were fixed (emit canvas stream frames; wait
for selected group before reading its ID), not app/backend defects.
Detailed evidence in docs/photo-quality.md. Committed/pushed only this release as
f8d5ba3355576f5e17b47eb656f06e0f57d32297. Backend and frontend GitHub CI both
completed successfully. Render deploy dep-dbkchbc9v7es73cc7prg is live at
https://mustaaaaaard-27.onrender.com; verified all environment values unchanged
before/after deployment, plan Free, auto-deploy off. No schema/scoring/video rule
or production secret change. Earlier unrelated local notes/config remain.

Live production Chrome verification used a temporary session for the already
verified existing owner and the existing isolated verification group, not a new
identity or dev-auth route. Passed visible gallery action, 1920x1080 synthetic
native capture/preview/upload=1 point, gallery JPEG/MP4 selection/preview/captions/
uploads=0, signed video playback, ranking total=1 and mobile layout. Downloaded
the gallery output only in memory: 1080x1920 EXIF-corrected portrait, pixel-identical
to decoded original and metadata absent. Removed 3 accepted test posts and cleaned
their 3 R2 objects after each production verification attempt; test sessions revoked,
fingerprints/audit retained and existing user content/session preserved. The first
production verification attempt reached ranking checks but its test harness lacked
an API baseURL; fixed that harness and reran successfully, without application
changes. Final /api/ready=200; existing production login Chrome check also passed.
Synthetic tests are not physical Android/iPhone camera/focus/exposure verification.

## Circular favicon update — 2026-11-02

Updated the existing deterministic icon generator to apply an antialiased circular
alpha mask and retain RGBA instead of flattening generated PNGs to RGB. Original
supplied favicon.png is preserved. Regenerated 16/32px PNG, all ICO sizes, 180px
Apple icon and 192/512px derivatives. Added versioned icon URLs so browsers can
refresh cached square assets. Validated transparent corners/opaque centers in
every PNG and ICO frame. Frontend lint/typecheck, all 20 unit tests and production
build passed. No new tests or product scope added.

Committed/pushed only the eight favicon-related source/assets as
87d75ccb434f877b3e6946363d4595a6e223666d. Other deployment notes/config changes and
ignored credentials were preserved outside that commit. Started pinned deployment
dep-dbk8fh8u01pc739bpog0 on the existing Render service after verifying Free and
auto-deploy off. Deployment is live. Verified all six generated icon files from
provider HTTPS match the new local assets byte-for-byte and have transparent
corners; versioned links are served and /api/ready=200. Existing production Chrome
check passed against the live app. Latest backend/frontend CI was still running
at the preceding status check; local required frontend checks all passed. No
secret settings changed.

## Production deployment and single-user acceptance passed — 2026-11-02

Live URL: https://mustaaaaaard-27.onrender.com. User completed real Google sign-in;
read-only DB verification found exactly one Google account with an active session.
Ran existing bootstrap-user operator CLI for that verified existing user; initial
Mustaaaaaard '27 group/admin bootstrap succeeded. No fabricated Google identity or
development authentication was used. The original browser session was preserved.

For authorized production acceptance, created a separate short-lived session for
that same verified account using the existing login service, keeping its cookie/
CSRF only in process memory. Created one clearly named Deployment verification
2026-11-02 group and reused it for checks; normal initial-group content was not
modified. Actual HTTPS API tests passed: missing CSRF rejected; capture photo=1;
capture video=3; gallery photo=0; normalized CRLF/CR caption; idempotent replay
returns same post; changed caption cannot evade original-media duplicate rejection;
feed contains the three accepted posts; weekly/all-time rank 1 totals 4 with correct
photo/video/gallery counts. Real R2 media signed GET=200 and range GET=206;
unsigned GET rejected with 400. No cookie, credential, media bytes or signed URL
was printed, saved in browser storage files or committed.

An initial synthetic 2-second clip was correctly rejected by the existing 5–30s
duration policy (422 invalid_duration). This was a verification-fixture mistake,
not an app defect; the corrected 6-second H.264/AAC fixture passed. No app-code
change or extra deployment was needed.

Authenticated headless Chrome against the live Render site passed feed rendering,
literal caption text (no injected b element), signed video playback (320px width,
advancing time), 4-point leaderboard, and desktop width check. Browser used the
temporary session, not automation of Google consent. User's real Google callback
was independently verified above. Media/390x844 viewport were synthetic; physical
Android/iPhone camera/microphone/recording behavior remains unverified. A second
Google user/invite/membership flow has not been exercised on production.

Removed every accepted verification post via production API: first-run photo plus
three corrected-run posts. Existing cleanup service confirmed removal of the four
associated R2 objects and released reservations. Post captions cleared, tombstones
and original fingerprints retained. Final verification feed empty and rank points=0.
Temporary sessions revoked, original Google session remains active. The empty
verification group, audit history and failed/expired capture/upload records remain
as intended; there is no group-delete API and none was invented.

Live readiness, schema 0003, production dev-auth=404, frontend, Google sign-in,
single-user live API scoring/feed/rankings and private media are verified. Source
commit remains c241e769883b88b4dcbd5fc6ee3e5bfae515ebc0, Render plan Free,
auto-deploy off. No paid plan, billing-method change, unrelated resource or Fly.io
mutation occurred. Credentials remain ignored locally and in provider secrets.
Physical phones, second-user acceptance and backup/restore rehearsal are pending.

## Production app live; real Google sign-in pending — 2026-11-02

Deploy dep-dbk87e49v7es73c0gaag completed live on existing Render Free service
srv-dbk7ej942hec73ervp5g, main c241e769883b88b4dcbd5fc6ee3e5bfae515ebc0.
Live origin: https://mustaaaaaard-27.onrender.com. Auto-deploy remains off; no
paid plan, new checkout, unrelated resource or Fly.io change occurred.

Actual provider HTTPS checks: /health=200, /api/ready=200 and /=200 HTML.
Read-only Neon check confirms Alembic revision 0003; normal locked startup release
performed migrations (not a manual schema mutation). Production POST /api/auth/dev
returns 404; unauthenticated /api/auth/session returns 401. /auth/google returns
302 to accounts.google.com with configured client, exact callback and openid
scope. OAuth temporary cookie has Secure/HttpOnly/SameSite=Lax; no cookies or
authorization URLs were printed. This verifies initiation, not user consent.

Ran existing frontend `npm run test:production` against the real Render origin:
passed on Chrome 156.0.8078.79. Verified exact page title, Google entry, disabled
development form, icons, Inter font and license. Ignored login screenshot was
saved by that existing script under frontend/test-results. This is synthetic
desktop browser/390x844 viewport verification, not physical phone testing.
Earlier live R2 temporary-object read/write/list/signed/range/CORS/private-denial
and deletion checks remain passed. No app media upload has yet been performed.

Asked user to complete real Google sign-in in their own browser and report only
completion or safe error text. Actual consent/callback/session, initial owner
bootstrap and authenticated upload/scoring/feed/rankings remain pending. Preserve
that task scope; do not claim those flows passed based on HTTP readiness.

## First production deployment started — 2026-11-02

User saved the Google Web OAuth JSON to root .env.google-oauth.json. Confirmed
it is ignored/untracked, parsed only in memory, and validated the client type,
exact JavaScript origin and callback against https://mustaaaaaard-27.onrender.com.
Transferred GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET through official per-variable
Render PUT endpoints, then compared both values and all other environment variables
in memory. Both credentials matched, other variables were unchanged, no deployment
was triggered by transfer, and full native production Settings validation passed.
No credential values appeared in output, documentation or tracked files; .env.*
is also excluded from Docker build context.

Removed the temporary Docker command with a narrowly scoped service PATCH;
confirmed Free, Frankfurt, origin and /health were preserved and auto-deploy
remains off. Started dep-dbk87e49v7es73c0gaag using existing service
srv-dbk7ej942hec73ervp5g and main commit c241e769883b88b4dcbd5fc6ee3e5bfae515ebc0.
Build is in progress. Normal Dockerfile startup will check storage and apply
locked Alembic migrations before serving. No manual schema writes or dev data
imports performed. Readiness/live UI and actual Google login remain pending.

## Google management integration recheck — 2026-11-02

At user's request, searched the live integration directory for Google Cloud OAuth
and inspected current tools/configured MCP servers. No Google Cloud OAuth/consent
management integration or browser/computer-control tool is exposed. Directory
results were unrelated Workspace apps and unavailable BigQuery; installed none.
Configured/authenticated MCP servers remain Neon, Render and Cloudflare. gcloud
is not on PATH. Official Google remote-MCP authentication documentation requires
an existing OAuth client for that sign-in route and does not provide a verified
bootstrap route here. Do not claim all Google MCP implementations lack this
feature; no suitable accessible integration was established in this environment.
Earlier browser launch rejection remains in force; no attempt to circumvent it.

The minimal remaining manual operation is Google Auth Platform consent registration
and creation/download of this app's Web OAuth client, using the already confirmed
Render origin/callback. Await .env.google-oauth.json (still absent) before secure
credential transfer, app deployment and startup migrations. No provider resources,
secrets or plan settings changed during this recheck.

## Production connectivity verified; Google client creation pending — 2026-11-02

Using only credentials already stored in Render, tested the dedicated R2 bucket
with a unique temporary object outside media/. HEAD bucket, PUT, HEAD object,
authenticated GET, prefix-scoped List, signed GET, signed byte-range GET (206)
and exact-origin CORS all passed. Unsigned S3 GET was rejected with HTTP 400;
do not describe it as a 403. Finally deleted the object and confirmed HEAD 404.
No object bytes, credential values or signed URLs were printed or persisted.
No user media was read or altered.

Read production settings presence without printing values: only GOOGLE_CLIENT_ID
and GOOGLE_CLIENT_SECRET are missing. Confirmed service is Free and startup guard
remains set. Neon read-only connectivity passed over TLS, PostgreSQL 18; migration
table is absent in the fresh database. No schema mutation performed. Initial DB
probe used an unsupported connection-info attribute; corrected the probe to read
pgconn.ssl_in_use and obtained the successful result above.

User requested exact Google consent/client guidance and will download the client
JSON locally for secure transfer. Verified root .env.google-oauth.json is already
ignored by .env.*. Expected Web client origin:
https://mustaaaaaard-27.onrender.com; callback:
https://mustaaaaaard-27.onrender.com/auth/google/callback. Configure External
Testing audience, intended test users, basic openid/email/profile scopes, and
contact email; no billing or unrelated APIs needed. Awaiting the ignored JSON.
Once supplied, validate its web client/origin/redirect and transfer only the two
Google values via per-variable Render API updates, preserving all other settings.
Then validate production settings, remove temporary dockerCommand, deploy existing
Free service and verify startup migrations/readiness. Actual Google sign-in and
authenticated upload/scoring/feed/rankings still pending; phone tests unverified.

## Storage credentials transferred without deployment — 2026-11-02

User explicitly supplied the S3 credentials and authorized writing them to local
root .env and transferring them to the existing Render service. Neither root nor
backend .env existed at the start. Wrote only the two requested S3 entries to root
.env, verified it is Git-ignored and untracked, then updated the two individual
Render environment variables through official per-variable PUT endpoints.
Credential values were not printed or included in documentation or tracked files.
Provider read-back matched both values; all other existing service environment
variables were preserved. Deploy history before/after showed zero new deployments,
and the setup startup guard remained in place. No app launch or commit occurred.
Google OAuth credentials remain pending; actual storage/app verification remains.

## Render/R2 provisioned; credential dashboard steps remain — 2026-11-02

User explicitly approved R2 billing/overage exposure in the authorization response.
This supersedes earlier pending-consent notes; do not request that consent again
for this installation. Cloudflare and Render MCP authorization retries succeeded.
Render requires its documented pre-registered OAuth client `codex`; generic/DCR
login failed, then `codex mcp add Render --url https://mcp.render.com/mcp
--oauth-client-id codex` worked. Render OAuth settings also exist in the user's
global MCP config from that command. Render CLI 2.34.0 was installed outside the
repo under LocalAppData/CodexDeploymentTools, and user approved device login.

Verified account access with actual tool calls. Render workspace is My Workspace,
ID tea-d0aejn95pdvs73cmvl40. Cloudflare account 8b158add944122fbd78f9d7ff7dbed01
already had R2 storage, so no subscription checkout/payment changes were needed.
Created only mustaaaaaard-production: Standard, WEUR, default jurisdiction.
Verified managed r2.dev access disabled and zero custom domains. Set/read back
CORS for https://mustaaaaaard-27.onrender.com: GET/HEAD, Range allowed, exposed
Content-Range/Accept-Ranges/Content-Length/ETag, 3600s preflight cache.
Existing services and bucket were not modified; no Fly.io access occurred.

Render API rejected maxShutdownDelaySeconds=240 on Free (HTTP 400, no service).
Removed this unsupported field from render.yaml and corrected dashboard docs.
Created srv-dbk7ej942hec73ervp5g, mustaaaaaard-27, Free, Frankfurt, Docker root
context and Dockerfile, main, auto-deploy off, /health. Confirmed allocated URL
https://mustaaaaaard-27.onrender.com. To honor the no-app-launch gate, its temporary
dockerCommand is `python -c "raise SystemExit('Deployment setup pending storage
and Google OAuth')"`. This prevents app import/migrations even if a build starts.
Restore dockerCommand to empty only after all production settings are complete.
Canceled initial deploy dep-dbk7ek142hec73ervrd0. Generated SECRET_KEY directly
into Render and transferred DATABASE_URL from Neon MCP to Render in memory,
validated exact direct endpoint/database and TLS, never printed/written locally.
Neon get_connection_string needs actual branch ID br-sparkling-hall-bartwbpd:
passing main returned 404 despite its schema claiming name support.

Render's MCP environment-update tool triggered deploy dep-dbk7fuec6qcc73don15g
despite auto-deploy off. Canceled it, guard intact. Use direct API/save-only UI for
further secret edits, not that MCP tool. Service read-back confirms Free/off/guard;
only DATABASE_URL and SECRET_KEY of required secret keys were present at last
check. Storage endpoint/bucket/quotas and R2_BILLING_ACKNOWLEDGED=true are set in
Render under the received consent. Template render.yaml retains false by default.

Cloudflare OAuth MCP explicitly returned 403 for /user/tokens/permission_groups
and states no OAuth scope supports token management. Creating scoped S3 API
credentials therefore needs the R2 API Tokens dashboard. User asked if automated:
explained this verified limitation; never ask for keys in chat. Requested only
creation of Object Read & Write token scoped to mustaaaaaard-production, with its
two S3 values entered directly into Render Environment and Save only.
GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET are also pending. Google web OAuth client
must use origin https://mustaaaaaard-27.onrender.com and redirect exactly
https://mustaaaaaard-27.onrender.com/auth/google/callback. Browser session from
the previous turn was unreachable; automatic approval review rejected a fresh
Chrome remote-debugging launch as blocked by policy. Do not circumvent this
rejection. Unsupported OAuth console steps need user dashboard interaction.

No application launch, production migration or real user acceptance occurred.
Ruff check/format and mypy passed after the YAML correction. Backend pytest:
49 passed, 81 skipped, two existing httpx deprecation warnings, 1.26s. Integration
fixtures were not enabled in this invocation; it is not a fresh real-services pass.
Latest unchanged-source GitHub backend/frontend/Linux evidence remains the full
verification baseline. No frontend source changed. git diff --check passed.

## Autonomous deployment takeover: authorization pending — 2026-11-02

User authorized setup and deployment through integrations, then official CLI/API,
then browser, while forbidding paid plans, unapproved R2 exposure and unrelated/
Fly.io changes. Existing no-launch-until-storage/OAuth-ready gate remains intact.
Rechecked live GitHub: latest backend 41356947713 and frontend 41356947772 remain
successful at c241e769883b88b4dcbd5fc6ee3e5bfae515ebc0. No source changes required.

Inspected live integration directory individually for Render, Cloudflare and
Google Cloud. Render plugin is available but uninstalled/unconnected; invoked its
connection suggestion under the user's explicit connection request. It has not
been confirmed connected, and no account/workspace access is claimed. Neon plugin
also exists but is unnecessary: existing local MCP still reports OAuth and the
production project will be reused. No Cloudflare plugin was returned. Google
results were unrelated Workspace apps/BigQuery, not an OAuth-management integration.

Official Cloudflare docs identify https://mcp.cloudflare.com/mcp. Added that
OAuth-only server to project .codex/config.toml and started `codex mcp login
Cloudflare --oauth-client-registration dcr`. Browser authorization is pending;
latest CLI status is Not logged in. This is account connection only, not R2
activation. Requested explicit R2 billing approval with primary-payment-method,
free-allowance, overage-rate and no-hard-spend-cap explanation; no decision received.
R2 remains inactive and acknowledgement remains false.

No gcloud, render or wrangler CLI was on PATH and no standard local gcloud,
.render or .wrangler configuration directory was found. AWS CLI exists but does
not establish Cloudflare access. Official Google documentation directs OAuth web
client creation through Google Auth Platform. Opened a dedicated visible Chrome
session through existing Playwright for that unsupported dashboard work, using a
temporary browser profile outside the repo and loopback CDP port 9224. It is at
Google sign-in (accounts.google.com); user sign-in is pending. No personal browser
profile/cookies were read, no credential input or secret output captured, and no
Google resources or billing changes occurred. Keep that browser open for continuation.

Inspected official Render create-service OpenAPI in memory: no skip-initial-deploy
or suspended-on-create field was found. Do not create a running service before
storage and Google settings are ready. The service plan must explicitly be free:
the API otherwise documents a paid default. Startup storage readiness precedes
migrations. No service creation, deployments, production SQL, secret transfer,
R2 operations or Fly.io access occurred. Next dependencies are Render connection,
Cloudflare authorization, Google browser sign-in and the separate R2 consent
decision. No application files changed; git diff --check was used for these notes.

## Deployment resumed: MCP verified, Render prepared — 2026-11-02

Verified Neon MCP rather than assuming CLI authentication applies. Initially
`codex mcp list` reported Not logged in. The normal OAuth flow reached callback
but failed token exchange with invalid_request / Invalid redirect URI. Retried
`codex mcp login Neon --oauth-client-registration dcr`; user approved in browser
and login succeeded. Fresh CLI listing reports OAuth. A separate read-only Codex
app-server initialize + mcpServerStatus/list probe against the configured Neon URL
reported name Neon, authStatus oAuth and 127 discovered tools. No model turn or
sub-agent was launched, no SQL or database-credential tool called, and no database
credentials were fetched/printed. Running chat tool availability has not refreshed;
authenticated server discovery is verified, deployed app connectivity is not.

Reviewed existing root Dockerfile, render.yaml, production env example, Settings
validation and serve_web origin derivation. Added exact Render dashboard fields,
public settings, secret transfer instructions, Google prerequisites and R2 billing
exposure to docs/free-tier-deployment.md. Render's official docs confirm Create Web
Service starts the first build/deploy even with later auto-deploys disabled: keep
the form unsubmitted until storage and exact Google OAuth settings are ready.
Environment updates on an existing service must use Save only. Render plugin is
available but not connected (already suggested previously); no dashboard account
or workspace eligibility was inspected. No Render resources or app launch occurred.

Official Render, Cloudflare and Google guidance checked live. R2 requires subscription
checkout; Cloudflare requires a primary payment method for product purchases. Free
Standard allowances do not cap excess storage/operation billing; quotas and alerts
do not bound signed-link replay or shared account usage. R2 approval remains absent,
activation has not occurred and R2_BILLING_ACKNOWLEDGED remains false. No paid plan,
billing change, Fly.io access, migrations or production bootstrap performed.
Documentation-only updates passed git diff --check; app suites were not rerun.

## Neon organization setup completed — 2026-11-02

Followed the user-requested https://neon.com/get-started/prompt.md using Neon CLI
8.16.0. Initial browser login expired; retry with `login --keyring` succeeded.
OAuth session is in the Windows OS keyring, outside this repository. Read the
organization API: Emmanuel Eyram Korku (`org-dark-mouse-16460218`) is Free and had
no projects. Created exactly one empty project `mustaaaaaard-27-production`, ID
`morning-shape-51677264`, AWS Frankfurt, PostgreSQL 18. Read back its project,
branch, endpoint and database: `main`, `neondb`, `neondb_owner`, min=max 0.25 CU,
1 GiB logical branch limit, six-hour history. Endpoint suspend timeout `0` means
the plan default according to the live API description; Free's five-minute
scale-to-zero is retained. No paid plan or billing setting changed.

Linked `.neon` using `--no-env-pull --no-config`; CLI added `.neon` to .gitignore.
No database password or connection URI was fetched or written. Existing root and
backend environments were preserved; production DATABASE_URL still belongs in
Render's secret manager. Installed project-local `neon` and `neon-postgres` skills
from neondatabase/agent-skills with skills-lock.json. The CLI's first skill attempt
required newer Node, and its retry hit a Windows npx invocation failure; direct
skills installation with temporary npm Node 22.22.0 completed successfully without
upgrading system Node 22.16.0. `neon init` configured OAuth MCP in .codex/config.toml
at https://mcp.neon.tech/mcp. Agent restart/first-use MCP authorization remains;
MCP tool connectivity is not claimed verified in this running session.

Read-back verification and git diff --check passed. No application code/schema or
deployment configuration changed, so application suites were not rerun. Database
connectivity through the deployed app, migrations, Render, Google OAuth, R2 and
physical devices remain unverified. R2 activation approval is still absent and
R2_BILLING_ACKNOWLEDGED remains false. No deployment or local data import occurred.

## Free-tier account setup preparation — 2026-11-02

User authorized the documented Render Free / Neon Free / private R2 setup after
Linux verification, one service at a time starting with Neon. Paid plans remain
prohibited; R2 activation requires separate explicit overage approval, still absent.
Read live GitHub main and latest workflow runs: local/remote HEAD both
`c241e769883b88b4dcbd5fc6ee3e5bfae515ebc0`. Backend run 41356947713 succeeded
at 2026-11-01 22:27:42 UTC; frontend run 41356947772 succeeded at 22:28:07 UTC.
Read both job step lists: backend checks/tests/migration round-trip and frontend
lint/types/unit/build/real-backend Chromium checks all passed. Camera was synthetic.
Manual Linux run 41355405807 also remains successful, on earlier SHA 6ecab195;
no claim of actual Render/Neon/R2/Google/physical-device verification is made.

Reviewed root Dockerfile, render.yaml, production env example and two-connection
SQLAlchemy pool. Corrected obsolete deployment blockers/repository statements and
added exact Neon project/Connect field choices, PostgreSQL 18 matching CI, direct
TLS, 0.25 CU and scale-to-zero guidance. Official Neon/R2 terms were checked live.
No credentials requested, read or written; no resources, subscriptions, deployment,
paid plans or billing changes performed. R2 acknowledgement remains false.
Account eligibility, actual quotas and Neon project completion require dashboard
confirmation. Documentation-only changes: checked diff/whitespace; no local test
rerun, application/configuration unchanged. Latest CI evidence is recorded above.

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
