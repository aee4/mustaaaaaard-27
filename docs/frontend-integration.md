# Frontend integration contract

The implemented web client lives in frontend/. Its central client calls `/api/*`;
Vite strips that prefix and forwards to the backend paths below. `/auth/*` is also
proxied unchanged for Google navigation/callback. A production same-origin reverse
proxy needs the same mappings and SPA history fallback. See README for local
commands and docs/frontend-verification.md for actual browser evidence. Optional
captions are now supported through migration 0002 and the existing upload endpoints.
Avatars are not in the API contract and are not fabricated by the UI.

New videos: 5–30 seconds inclusive, <=50 MiB, shorter encoded edge <=720px and
longer edge <=1280px. MP4: 8-bit H.264 Baseline/Main/High with optional AAC-LC;
WebM: 8-bit VP8/VP9 with optional Opus/Vorbis. Unsupported codecs/resolutions
return 422 invalid_media with actionable text. The server does not transcode.
Sanitized media can now be video/mp4 **or video/webm**; use the authorized media
URL/content type, never infer MP4. Existing larger videos remain readable. No API
field or endpoint changes. Duration/size, scoring, hash/idempotency and private
signed-media behavior are unchanged. See [video processing](video-processing.md).

Migration 0003 adds internal storage-byte reservations. A full configured storage
budget rejects uploads with 409 `storage_quota_exceeded` and an explanatory message;
existing memories remain. Unknown legacy usage pauses uploads with 503
`storage_usage_unknown` until operator reconciliation. Busy processing, exhausted
resources or timeouts return retryable 503 `media_busy`, `media_resources_exhausted`
or `media_processing_timeout`. Keep the same bytes/caption/key on retry; acceptance
and scoring remain authoritative. Quotas and resource limits do not change gallery=0.

Use `/openapi.json` to generate a typed client; `/docs` has exact
schemas and interactive examples. All IDs are UUID strings, timestamps ISO8601
with UTC offset. API errors never expose validation input or stack traces.

Original backend handoff verified on 2026-11-01 through real local HTTP: two cookie-authenticated
users, invite join, scoring photo/video, gallery=0, three feed posts, weekly/all-time
rankings and private media access. Full suite: 65 passed, no skips. This supports
local frontend integration with development auth. Docker/Compose startup and real
Google consent login remain unverified; see
[handoff-verification.md](handoff-verification.md). Subsequent frontend and group
onboarding verification is recorded in [group-onboarding-verification.md](group-onboarding-verification.md).

## Session, cookies, CSRF and HTTPS

Deploy behind the same HTTPS origin as the frontend; proxy backend routes to this
service. Navigate to `GET /auth/google`. Google returns to
`/auth/google/callback`; server verifies state, nonce, PKCE, ID-token signature,
issuer, audience and expiry, then sets an opaque HttpOnly session cookie and
redirects to `/`. It does not return Google access tokens to the frontend.

On app startup fetch `GET /auth/session` with `credentials: 'include'`. Response:

```json
{"user":{"id":"11111111-1111-4111-8111-111111111111","display_name":"Alice"},"csrf_token":"opaque-random-value","expires_at":"2026-11-09T12:00:00Z"}
```

Keep CSRF in memory. On every POST/PATCH/DELETE use `credentials: 'include'`,
`X-CSRF-Token` and the browser's allowed `Origin`. For JSON set Content-Type to
application/json. Cookies default to SameSite=Lax, Secure in production. Separate
cross-site deployments would require a reviewed cookie/topology change. CORS must
explicitly allow the frontend origin. Never use localStorage for authentication.
401 means reauthenticate; 403 means permission, Origin or CSRF failure. Logout is
`POST /auth/logout`, revokes the session immediately and clears the cookie.

Local only: `POST /auth/dev`, with allowed Origin and JSON
`{"subject":"alice","display_name":"Alice"}` returns the same session body.
Dev subjects are separate from Google subjects. The CLI must explicitly bootstrap
`dev:alice` as admin; login never grants membership or admin. Dev auth is disabled
by default unless `backend/.env` or process environment enables it and is forbidden
in production. Root `.env` is Compose input only.

## Endpoint inventory

| Method | Route | Request/result |
|---|---|---|
| GET | `/health`, `/ready` | Liveness/readiness `{ "ok": true }` |
| GET | `/auth/google` | Begin Google login navigation |
| GET | `/auth/google/callback` | OAuth callback, session cookie, redirect `/` |
| POST | `/auth/dev` | Local JSON subject/display_name; session |
| GET | `/auth/session` | User, CSRF, expiry |
| POST | `/auth/logout` | Revokes cookie session |
| PATCH | `/me` | `{ "display_name": "Alice" }` -> user |
| GET | `/groups` | Active memberships: id/name/role |
| POST | `/groups` | `{ "name": "Our people" }` -> id/name/role (`admin`), 201 |
| POST | `/groups/join` | `{ "token": "invite-token" }` -> group/id/role |
| POST | `/groups/{g}/invites` | Admin: max_uses (1..1000), expires_in_hours (1..720) |
| DELETE | `/groups/{g}/invites/{invite}` | Admin revocation |
| DELETE | `/groups/{g}/members/{user}` | Admin removes member; admins managed by operator |
| GET | `/groups/{g}/members/{user}` | Basic user + current/longest streak/grace |
| POST | `/groups/{g}/captures` | `{ "kind": "photo" }` or video -> capture/expiry |
| POST | `/groups/{g}/captures/{capture}/upload?kind=photo` | Multipart `file`, Idempotency-Key -> accepted post |
| POST | `/groups/{g}/gallery?kind=photo` | Separate multipart zero-point flow |
| GET | `/groups/{g}/feed?limit=20&cursor=...` | Posts, next_cursor, server_time |
| GET | `/groups/{g}/leaderboard?period=weekly&limit=20&offset=0` | period=weekly/all, ranked rows, boundaries |
| GET | `/groups/{g}/posts/{post}/media` | Member-authorized signed URL + expiry |
| DELETE | `/groups/{g}/posts/{post}` | Own post or group admin removal |

Except health/readiness and login, routes require a valid session. Every group
resource route checks membership. Creating a group requires authentication but
no existing membership. Basic group/profile metadata never exposes email or
Google subjects. Group resources from another group remain unavailable.

Group names: 1..100 Unicode code points, NFC normalization, collapsed whitespace,
no control/format characters. Names are globally unique and case-sensitive.
409 `group_name_unavailable` means choose another name; `group_name_reserved`
protects the initial operator-bootstrap name. Invalid input is 422. Extra fields
(including role/user_id/group_id) are rejected. Creation requires cookie, allowed
Origin and CSRF; default GROUP_RATE is 5 attempts/user/minute (429 on excess).
Creation commits the group, creator-admin membership and audit in one transaction.
POST creation has no idempotency key and is not automatically retried. If a response
is lost, refresh GET /groups before submitting again: the unique name prevents a
second group with the same name. The frontend immediately caches the returned
membership, selects it, opens Feed, then refreshes memberships. Switching resets
group-specific views, including previously generated invite links.

Invite response includes token **only on creation**:

```json
{"id":"22222222-2222-4222-8222-222222222222","token":"opaque-invite-token","expires_at":"2026-11-05T12:00:00Z","max_uses":1}
```

Encode that token in a frontend join link and have the frontend POST it. The
backend does not assume a frontend join URL. Avoid analytics/logging on invite
links. Tokens are random and stored hashed, expire and can be revoked.

## Browser capture → acceptance

1. User chooses photo/video; obtain camera/microphone permissions. Browser camera
   access requires HTTPS, with localhost exceptions. Check browser codec support.
2. Immediately before capture, `POST /groups/{g}/captures` with kind. Response:
   `{"id":"33333333-3333-4333-8333-333333333333","kind":"photo","expires_at":"2026-11-02T12:10:00Z"}`.
3. Capture the image or record 5..30 second video. Browser capture sessions cannot
   prove camera origin, content age or freshness against modified clients. EXIF
   is never used as proof. Explain that honestly in product language.
4. Generate a UUID idempotency key and retain it with these exact bytes and capture
   ID until resolution. Send multipart `file`, query `kind` and that key. Do not
   manually set multipart Content-Type; browser must generate its boundary.
5. Server validates original bytes, hashes them, sanitizes metadata, stores private
   media, then atomically accepts the post and consumes the capture. Only acceptance
   before expiry earns points. Until acceptance show a pending state.

```javascript
const form = new FormData();
form.append('file', blob, 'capture');
const result = await fetch(`/groups/${groupId}/captures/${captureId}/upload?kind=photo`, {
  method: 'POST', credentials: 'include',
  headers: { 'X-CSRF-Token': csrfToken, 'Idempotency-Key': uploadKey },
  body: form,
});
```

Example accepted response (no public media URL):

```json
{"id":"44444444-4444-4444-8444-444444444444","user_id":"11111111-1111-4111-8111-111111111111","group_id":"55555555-5555-4555-8555-555555555555","kind":"photo","source":"capture","points":1,"accepted_at":"2026-11-02T12:00:03Z","removed":false,"caption":"Final year, same people."}
```

Gallery: choose an existing file and POST directly to `/groups/{g}/gallery?kind=...`
with its own key, without a capture session. Result source=gallery, points=0;
it never qualifies as streak activity. Never infer eligibility from a local source flag.

Images: JPEG/PNG/WebP, single frame, 15 MiB; default <=40 million pixels and <=12000
pixels on either axis. Video: 5..30 seconds inclusive, 50 MiB, <=720px short edge
and <=1280px long edge. Accept 8-bit H.264 Baseline/Main/High MP4 with optional
AAC-LC or 8-bit VP8/VP9 WebM with optional Opus/Vorbis. Video is fully decoded for
validation then remuxed in its compatible container without encoding. Metadata
including original GPS tags and H.264 SEI user data is removed. Technical rotation
is preserved. Images are sanitized to JPEG/PNG. Extensions/MIME are untrusted.
Do not send arbitrary remote URLs; API only takes uploaded bytes. Hash duplicate
protection is exact original bytes per group, including previously removed posts.
Edited visual duplicates may not be detected. There is no daily scoring cap.

## Retry contract

Optional caption: add `form.append('caption', 'Final year, same people.')` to either
upload flow. The limit is 280 Unicode code points after CRLF/CR becomes LF; outer
whitespace is trimmed, blank/omitted becomes null. Plain text only (React escapes
it); line breaks/tabs supported, other control characters rejected. Too-long text
returns 422 and invalid controls use `invalid_caption`. Do not change caption after
sending: it participates in the same-key comparison along with media kind/bytes.
Normalized whitespace/newline-equivalent text replays the original outcome. The
frontend freezes caption input after the first attempt. A different caption under
the same key returns 409; different captions do not evade original-media duplicate
protection. There is no caption-edit endpoint. Post/feed output includes nullable
`caption`, cleared on removal; only its digest survives for retry protection.

Capture creation is cheap and **not idempotent**: retry may create another unused
session, which simply expires. Each accepted capture can produce one post.

Both upload endpoints scope keys to user + group + capture ID (or gallery operation).
Same key and same original bytes/kind/caption returns the same accepted post ID; different
bytes/kind/caption returns 409 idempotency_conflict. Keep key, bytes, kind and URL unchanged
when retrying a lost response or 503. During processing 409 upload_in_progress is
expected; use bounded exponential backoff (e.g. 1,2,4,8 seconds, then show pending).
409 cleanup_pending requires scheduled/operator cleanup after the lease expires;
don't create new keys repeatedly. Failed validation can retry the same key/input,
but corrected bytes require a **new** key. Rejected attempts consume no capture.
Replays of removed accepted posts report removed=true and points=0. Membership
is required on every retry, including successful replays. Never retry a 409 with
different input under the same key. 429 means wait until next server minute.

Other mutations: profile PATCH sets the requested value and is safe to repeat;
post removal and invite revocation are idempotent while authorized. Repeated join
does not spend another use for an already-active member while the invite remains
valid/unexhausted; exhausted/revoked/expired invites return 409 even on retry.
Invite creation has no idempotency key: retry can create a second link; revoke
unneeded links. Membership removal on an already removed member returns 403.
Logout invalidates its session; retry may return 401. Dev login creates a fresh
session per call. Google code callback is single-use; restart login after failure.

## Feed, media and rankings

Feed default20/max100 sorted newest accepted_at then UUID descending. Pass opaque
next_cursor unchanged; null means no more rows. Cursor is signed and group-scoped.
Removed posts disappear immediately. An idempotency replay still returns their
minimal tombstone, never media.

Fetch `/posts/{id}/media` just before rendering. Response is
`{"url":"https://private-storage/...signed-query...","expires_at":"2026-11-02T12:02:00Z"}`.
URLs default to 120 seconds, max300, and are bearer access until expiry. Do not
persist, log, rewrite or share them. On expiry fetch a new URL; removed members
and removed posts cannot get new URLs. Already issued URLs can remain valid until
expiry, and object cleanup may make them fail earlier. Native img/video elements
can consume the URL; JS/canvas fetches require bucket CORS matching the frontend
origin, configured by the operator without enabling anonymous access.

Leaderboard uses current Accra week (Monday00:00..next Monday00:00), or all time.
Returns items + total/offset/limit + period_start/period_end (null for all time) +
server_time. Each row has user, rank, points, capture_photos, capture_videos,
gallery_photos, gallery_videos, and streak `{current,longest,grace_used_this_week}`.
Ranks are competition ranks (1,1,3), ties sorted by display_name then UUID. Counts
and points reflect selected period; streak reflects full current history. All
active members appear including zero points. Offset pages can shift as scores
change. Removed posts do not count. Users removed from membership disappear from
rankings. Group feed retains their unremoved posts.

All activity is server-timed at **final acceptance**, UTC stored, Africa/Accra
calendar dates. Intervals start inclusive/end exclusive. Photo capture=1, video
capture=3; gallery=0. Current day cannot be a miss until it ends. Distinct active
capture dates count once toward streak; grace preserves a live streak but adds
neither active days nor points. One automatic grace per calendar week, no carry.
Second miss in a week breaks it. Sunday and Monday can use different weeks' grace.
Deleting a post replays remaining activity and preserves each grace's original
date, so historical longest can decrease. See SPEC.md for explicit examples.

## Errors

```json
{"error":{"code":"capture_expired","message":"Capture session expired","request_id":"server-generated-request-id"}}
```

`X-Request-ID` repeats the ID. Handle codes, not message wording. Common codes:

| Status | Codes |
|---|---|
| 401 | authentication_required, oauth_invalid |
| 403 | csrf_invalid, origin_forbidden, membership_required, admin_required, post_forbidden |
| 404 | not_found, capture_not_found, post_not_found, invite_not_found, invalid_invite, media_unavailable |
| 409 | capture_expired, capture_consumed, capture_kind_mismatch, duplicate_media, idempotency_conflict, upload_in_progress, cleanup_pending, upload_lease_lost, invalid_invite, admin_removal_forbidden |
| 413 | media_too_large |
| 422 | validation_error, invalid_media, invalid_duration, invalid_caption, invalid_cursor |
| 429 | rate_limited |
| 503 | upload_unavailable, media_tools_unavailable, google_unconfigured, not_ready |
| 500 | internal_error |

Malformed multipart/unknown routes may use http_error. Never display raw server
errors as HTML. Give support the request ID, without tokens or signed URLs.
