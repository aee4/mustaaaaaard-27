# Local acceptance — 2026-11-01

## Run state and accounts

App: **http://localhost:3000**. Native FastAPI: http://127.0.0.1:58000;
readiness at /ready. PostgreSQL 18 listens on 127.0.0.1:55432, source-built MinIO
on 127.0.0.1:59000 (also ::1). Vite on port 3000/API on port 58000/PostgreSQL are IPv4 loopback only.
Development auth is enabled only in this local environment, and the UI shows it
only in Vite development mode. Nothing was deployed or bound to a public address.

Sign in with **Development ID alice**, display name Alice. This ID was explicitly
bootstrapped as group admin. For a second user choose another ID, then have alice
create an invite in Profile. Paste its link/token into the second user's join form.
The existing disposable mustard_handoff_test DB is retained. Services are left
running; if stopped/restarted, follow README's native startup. Test photos/videos
are removed after checks; no sample activity is fabricated for acceptance.

Fixture rate limits were raised while browser tests ran. The running acceptance API
was restarted afterward with documented defaults: auth 30/min, invite 30/min and
upload 60/min. Its migration is 0002 (head). Latest direct checks returned 200 for
the frontend, /api/ready through Vite and /ready directly. Database check found zero
live test posts. Final cleanup deleted eight remaining test media objects.

## Reference comparison

| Screen | Material differences fixed | Deliberately preserved |
|---|---|---|
| Feed | Removed oversized mobile intro; compact brand/account header; date-led journal; cream stats card; mustard point pills; caption below media; mobile navigation | Real member initials because no avatar field; real accepted media only; no fake points/streaks |
| Capture | Compact dark heading; Camera/Gallery segmented control; Photo/Video moved below preview; scoring note; shutter kept above bottom nav; no route-scroll carryover | Camera opens on user action; full preview without deceptive sample scene; session expiry and gallery 0 rules |
| Leaderboard | Centered dark title; mustard weekly/all-time switch; leading rank highlight; Your season points/streak/uploads/grace card beneath phone rankings | Current server week only; no inert week-navigation arrows or invented historical endpoint |

Phone-sized screenshots inspected at 390×844; desktop feed checked at 1440×1000.
Screenshots in frontend/test-results/feed-mobile.png, capture-mobile.png,
leaderboard-mobile.png and feed-desktop.png use explicitly synthetic test media.
These are desktop browser renders, not phone screenshots. Focus outlines remain
visible for keyboard use; the skip link is visually clipped until keyboard focus.
Browser assertion checks live recording shutter does not overlap bottom navigation.

## Optional captions

Migration 0002 adds nullable posts.caption and uploads.caption_hash; preexisting
posts remain valid with caption=null. The optional multipart caption field is
available on both existing capture upload and gallery endpoints. No extra endpoint
or social feature was added.

- Maximum 280 Unicode code points after CRLF/CR→LF normalization; outer whitespace
  trimmed; empty/omitted becomes null. Newlines/tabs allowed; other controls and
  surrogate code points rejected. Plain text only, escaped by React.
- Preview includes optional caption input and character count for both sources.
  Over-limit text is blocked before network submission. Caption freezes on first
  attempt; retries preserve caption, bytes, session, kind and idempotency key.
- Same key/different normalized caption returns 409. A new caption cannot bypass
  original-byte duplicate protection. Caption text does not affect points/streaks.
- Deletion clears caption text; upload retains its digest to check retries. Removed
  post replay has caption=null. There is no edit-after-posting feature in this scope.

OpenAPI and generated TypeScript updated; docs/frontend-integration.md documents
request/response and retry details. Readiness expects revision 0002.

## Checks actually performed

| Check | Result |
|---|---|
| Full pytest with real PostgreSQL/MinIO/FFmpeg | **79 passed**, no skips, 2 existing adapter warnings, 12.85s |
| Caption-specific pytest | 14 cases passed, including multiline boundary, blank replay, controls, storage failure, deletion and caption conflict |
| Ruff check/format; mypy app | Passed; 48 Python files formatted, 23 app files typed |
| Frontend ESLint/TypeScript | Passed |
| Frontend Vitest | **13 passed** (including caption-preserving multipart retry assertions) |
| Vite production build | Passed |
| Real-backend Chrome Playwright | **5 passed**, 21.1s |
| npm audit | Zero vulnerabilities |
| Generated API types / live OpenAPI comparison | Passed; 20 paths, no new endpoints |
| Migration 0002→0001→0002, only disposable mustard_test | Passed; preexisting post ID/fingerprint preserved, new columns null after re-upgrade |
| Local frontend/readiness HTTP checks | Both 200 |

The downgrade test deliberately drops caption columns only in the disposable test
database. Never use it on real data without a backup/data-loss plan. Acceptance DB
mustard_handoff_test was only upgraded. Backend pytest runs separately on mustard_test;
don't run truncating tests against the active acceptance DB or share a live media
bucket with an unrelated database's orphan sweep.

Browser evidence covers two cookie contexts/invite join; actual browser-generated
photo 1/video 3 and gallery 0 through real storage/validation; accepted caption in feed;
plain-text HTML-like/multiline caption; rejected 281-character input; caption frozen
across a deliberately lost acceptance response and same-key retry returning one
post; both ranking periods; video playback; own/admin removal; permission denial;
unavailable API; track cleanup and keyboard leave dialog. Negative network/media
permission failures are injected deliberately; member removal/403 is real backend
authorization. Camera/audio devices are synthetic Chrome inputs.

## Manual PC acceptance

1. Open localhost:3000, sign in as alice. Inspect Feed, Capture, Leaderboard and
   Profile on desktop and a narrow browser window. Values must reflect the server.
2. In a private browser window sign in with a second ID and join through an admin
   invite. Test a new optional caption on both a camera capture and gallery share.
3. Preview/retake/cancel; record 5–30 seconds. Check photo 1/video 3/gallery 0 and that
   gallery does not maintain a streak. Captures count on server acceptance date.
4. Read multiline/emoji/HTML-like captions in the feed, test the 280-character limit,
   remove own/admin posts and verify scores update. Identical removed media remains
   a duplicate even with a changed caption.
5. Stop/restart the API only if testing unavailable states, then retry safely with
   unchanged bytes/caption/key. Confirm no duplicate post after a lost response.

## Physical devices and HTTPS

**Android physical: not run. iPhone physical: not run.** Synthetic Chrome capture
does not establish Safari/mobile codecs, real microphones, rotation, locking or
cellular resilience. Google production login and Docker packaging remain unverified.

Use [phone-https.md](phone-https.md) for exact private-IP HTTPS ports, restricted
firewall, Caddy CA transfer/trust on Android and iPhone, secure cookies/origins/media
host and teardown. No public tunnel/port forwarding. Those steps were documented
against official OS/proxy guidance but not executed here. Record actual results in
[phone-checklist.md](phone-checklist.md); no physical boxes are prechecked.
