# Mustaaaaaard ’27 — The Final Season.

## Web typography
Use self-hosted, SIL-licensed Inter Variable as the shared sans-serif family across
all screens, branding, forms, dialogs and states. Body 400, controls 500–600,
headings 800; compact heading tracking and normal body spacing. No serif families
or decorative italic styling. Scores, rankings and countdowns use tabular numerals.
Preserve mustard, cream, charcoal, brand/tagline, navigation and prominent capture.
Inter is an alternative and is not represented as Snapchat's proprietary font.

## Authority and calendar
Private group application. Server UTC timestamps establish event timing; accepted_at
determines Africa/Accra activity date and Monday-start week. Intervals are [start,end).
Injected Clock is used by all business services. No client dates, scores or user IDs
are accepted for uploads. Captures earn photo=1/video=3; gallery=0. No scoring cap.

## Identity and authorization acceptance
Google authorization-code OIDC uses Authlib discovery, state, nonce, PKCE S256,
issuer/audience/expiry validation. Subject is the identity key. Random opaque
sessions are stored hashed, expire and revoke on logout. Cookie mutations require
Origin allowlist and a session-bound CSRF header. Dev auth is explicitly enabled
only outside production. Same-origin HTTPS proxy is the production topology.
No first-visitor admin. CLI bootstraps an identified Google subject (or dev subject
locally). Invites are hashed random tokens, expire, revoke and have 1..1000 uses.
Joining locks the invite. Membership removals and moderation are audited.

Authenticated users may POST /groups with only a name. Normalize names to NFC,
collapse whitespace, require 1..100 Unicode code points, reject control/format
characters and enforce existing global case-sensitive name uniqueness. Reserve
the initial Mustaaaaaard ’27 name (case/apostrophe variants) for operator bootstrap.
Create the group, creator's admin membership and group.created audit atomically;
the creator gains no rights in other groups. Require session, Origin and CSRF,
with a per-user PostgreSQL-backed creation limit of 5 attempts/minute by default
(GROUP_RATE). Name conflicts return 409; invalid input 422. New groups use the
existing invite, membership, media and moderation authorization rules.

## Media and retries acceptance
Media admission is bounded per process (default one sanitizer/acceptance job), with
one configured FFmpeg decoder/encoder thread and one filter thread by default.
Busy/resource/timeout failures are retryable 503, not proof of invalid media.
Invalid media retains 422 validation. Size, codec, duration, dimension, scoring,
capture consumption and acceptance-time rules remain unchanged. The free profile
uses an explicitly documented ultrafast encoding preset with potentially larger
output; native default is veryfast. Existing output size/sanitation checks apply.

Storage quotas count sanitized bytes and reserved object count globally across
the app's dedicated DB/bucket, enforced before PUT under a PostgreSQL advisory
transaction lock. Quota rejection is 409 storage_quota_exceeded. Failed/pending
objects and removed posts retain reservations until confirmed physical deletion.
Unknown legacy sizes fail closed under enabled quotas until measured by an
operator. Accepted retries do not reserve again. No quota-driven memory deletion
is allowed. These application quotas are not provider billing caps. Production R2
requires positive quotas and explicit billing-exposure acknowledgement.

Optional captions are accepted as multipart `caption` on capture and gallery
uploads. Maximum 280 Unicode code points after CRLF/CR normalization to LF;
surrounding whitespace is stripped and blank/omitted becomes null. Newlines and
tabs are allowed; other control characters and surrogate code points are rejected.
Captions are plain text, never HTML. They do not affect scoring or duplicate hashes.
The normalized caption is part of the same-key input comparison: changing it
returns 409. Captions cannot be edited after submission in this scope. Removal
clears the post's caption while retaining a SHA-256 caption digest on the upload
for idempotency. Migration 0002 preserves old posts with null captions. Accepted
post and feed responses include nullable `caption`.

Create capture (10 minute default) bound to user/group/kind. Upload multipart bytes
to either capture or gallery endpoint with Idempotency-Key (1..128 characters).
The server hashes bounded original bytes, claims a staged upload, validates/sanitizes,
writes a random private object and atomically accepts the post/consumes capture.
Image maximum: 15 MiB, 40 million pixels, 12000px each axis; JPEG/PNG/WebP only,
single-frame; served as metadata-free lossless PNG without resizing or further
lossy recompression, preserving decoded pixels and EXIF-corrected aspect ratio.
Browser photos request flexible 1920x1080 preview independently of video. Prefer
ImageCapture.takePhoto at supported still dimensions within existing safety limits;
retain its encoded bytes unchanged. If unavailable/failing, capture only the
stream's intrinsic videoWidth/videoHeight with one high-quality JPEG encode (0.95),
never CSS preview dimensions or upscaling. Device resolution is best effort, not
a guarantee. Gallery uploads preserve selected file bytes, have their own visible
photo/video chooser, and retain preview/caption/progress/error/same-key retry.
Video maximum: 50 MiB, duration
5..30 seconds inclusive. New uploads accept at most 720p: shorter encoded edge
<=720px and longer edge <=1280px, allowing landscape and portrait. MP4 requires
8-bit yuv420p H.264 Baseline/Constrained Baseline/Main/High and optional AAC-LC audio;
WebM requires 8-bit yuv420p VP8/VP9 and optional Opus/Vorbis audio. HEVC/HDR,
unsupported codec/container combinations and larger resolutions are rejected with
422 invalid_media and recording/export guidance, never converted or downscaled.
One video and at most one audio stream; no attachments, subtitles or data streams.
Bounded full decoding validates compressed content and decoded duration before
stream-copy remuxing. Preserve picture/audio encoding, frame rate and technical
rotation; strip global/stream tags, chapters and H.264 SEI user data. Served MP4
uses faststart; WebM stays WebM. Source and sanitized duration must both satisfy
5..30 seconds; duration-less streaming WebM is checked after decode/remux. Budgets:
20s input probe, 120s decode, 30s remux, 10s output probe; output must be smaller
than configured video input byte limit +1 MiB to bound container overhead. One
processing job and one decoder/filter thread by default. Browser capture requests
720p/30fps, 2.5Mbps video/128kbps audio, subject to device support; the server is
authoritative. Existing videos are retained and video scoring remains 3 points.
MP4 requires an initial ftyp box with a supported
ISO/MP4 major brand; QuickTime/MOV and generic Matroska are excluded before probing.
Original SHA256 is unique per group forever after acceptance,
including removed posts. Edited visually identical files are not detected.

Same key/user/operation and fingerprint returns original accepted result, including
its removed status; different input=409. A processing request=409 upload_in_progress;
retry after backoff. Failed attempts can retry same input/key. Leases fence stale
workers. Every retry rechecks membership. Acceptance before capture expiry is
required. Capture creation itself is not idempotent; unused sessions expire without
side effects. Gallery uses its own operation. Invalid input earns nothing.
Staging rows reserve random object keys before storage IO; failure leaves a retryable
row and cleanup debt. Cleanup takes expired leases, deletes their objects outside
transactions and retains fingerprints/tombstones. Removed objects are eligible for
immediate cleanup; signed URLs can work for up to 120 seconds after removal.
Cleanup is idempotent, safe to rerun; failed deletes remain pending. API state hides
removed media immediately. Upload acceptance serializes on membership row and
locks capture; no network IO in acceptance transaction.

## Streak and deletion policy (defined before implementation)
Only live scoring captures produce distinct active dates. Evaluate through yesterday;
today contributes if active, and an inactive today never consumes grace. A first
active date starts a streak of one. A missed completed date consumes its week's
single grace only if a streak is live, preserving count; the next miss that week
breaks it. Grace cannot start a streak. Persist (user,group,week,day) when consumed.
Recalculation uses existing grace on its original date only, never moves or deletes
it. Historical deletions replay all remaining active dates with these fixed grace
reservations; a newly missing earlier date can consume grace only if that week has
no reservation. Thus deletion can break a historical streak and reduce longest;
restoring points by reuploading identical bytes is impossible. Serialize calculations
on membership row. Grace history survives membership removal/rejoin.

Examples (2026): Monday Nov 2 active, Tuesday missed, Wednesday active => current
2, longest 2, Tuesday grace. Thursday missed => current 0 after Thursday ends.
Saturday Oct 31 active, Sunday missed, Monday Nov 2 missed, Tuesday active =>
current 2, with one grace in each week. Monday active, Tuesday today inactive =>
current 1, no grace until Wednesday. Deleting Monday when Tuesday had grace does
not allow that grace to start a streak; Wednesday begins a new streak.

## Feed, ranks and removals acceptance
Private social release: one shared operator-seeded system welcome post per initial
group, title “The Final Season 💛”, caption “Our people. Our everyday moments.”
Its cover and ordered welcome album use the existing private, sanitized media
pipeline and storage quotas. System posts have no member author, points or streak
credit. Album children never appear as separate feed posts. Admins may unpin or
remove the welcome; seeding is resumable/idempotent and never repins or resurrects
removed content. No automatic seeding into new/unrelated groups.

Feed returns `pinned` separately from paginated `items`, with author display name,
like/comment counts, current viewer's liked state and private album post IDs.
PUT/DELETE post `/like` set/unset membership-scoped likes; composite primary key
enforces one per account. Like mutations serialize on the live post and do not
affect scores. Comments are trimmed, newline-normalized plain text, 1–500 Unicode
code points, newest-first signed keyset pagination scoped to group/post. Creation
requires Idempotency-Key (1–128), unique per post/account; changed normalized text
under the same key conflicts. Removed retry results retain a digest, never text.
Authors delete their own comments; admins moderate their group. Removed posts,
album children and revoked memberships cannot be accessed through social routes.
Deletion clears comment text, retaining tombstones/retry protection. CSRF/Origin
apply to every mutation; PostgreSQL fixed-window rates are 120 likes/minute and
30 comment mutations/minute per user. No comment likes/replies/notifications.

Tour completion/skip is stored by authenticated account and tour version through
GET/PUT `/me/tour/{version}`. Feed → Capture → Leaderboard → Profile, with Back,
Next, Skip/Done and Profile replay. The tour pauses during dirty capture/uploads;
keyboard-modal focus, reduced motion and missing targets are handled gracefully.

Feed descending (accepted_at,id) keyset cursor, default 20/max100, cursor scoped
to group. Leaderboards include all active members, zero scores included, weekly
or all time; rank=1,1,3, tie order display_name then UUID. Counts distinguish scoring
photo/video and gallery photo/video. Include server_time/period bounds, current and
longest streak and this-week grace. Offset pagination bounded size 100, max offset
10000. Membership required for every group read and signed URL issuance.
Owner or group admin may remove a post idempotently; keep minimal tombstone,
fingerprint, timestamps and upload result; remove media through cleanup. Scores
and streaks immediately exclude it. No public object URL in post representations.

## Operational acceptance
Structured errors {error:{code,message,request_id}}, generated request IDs, no
stack traces. Auth/invite/upload fixed-window PostgreSQL-backed limits; 30/30/60
per minute defaults per IP/user. Reverse proxy must preserve client IP securely;
do not blindly trust forwarded headers. Upload body capped before multipart parsing
and additionally while reading. Expired operation leases default to 5 minutes,
longer than the media-processing budget. Cleanup also lists old media objects and
reconciles unreferenced keys after 15 minutes, covering delayed stale-worker writes.
Fingerprints remain in the database. Health is liveness; readiness checks
DB schema revision and private bucket availability. Production rejects defaults,
dev auth, insecure cookies, non-HTTPS origin/base URL, missing Google credentials.
