# Private group social release

The mobile mockup guides the compact cream/mustard layout, self-hosted Inter,
outline controls and bottom-sheet comments. Notification/bookmark/comment-like
buttons are intentionally absent because those features are not implemented.
Detailed scoring stays under **How it works**. Capture quality, validation, video
limits, Ghana dates, scoring and grace rules are unchanged.

## API

See [openapi.json](openapi.json) for generated request/response contracts.

- `GET /groups/{group_id}/feed`: separate nullable `pinned`, ordinary paginated
  `items`, author_name, liked, like_count, comment_count, album UUIDs.
- `PUT /groups/{group_id}/posts/{post_id}/like`: idempotent set.
- `DELETE /groups/{group_id}/posts/{post_id}/like`: idempotent unset.
- `GET .../comments?limit=20&cursor=...`: signed descending keyset pages, max100.
- `POST .../comments`: `{text}`, Idempotency-Key required, trimmed 1–500 code points.
- `DELETE .../comments/{comment_id}`: own comment or group admin; text cleared.
- `PATCH .../pin`: `{pinned}`; group admin, system welcome only.
- `GET/PUT /me/tour/1`: account/version completion; PUT also records Skip.

Every group interaction requires active membership and a live parent post.
Mutations use existing secure cookies, Origin and CSRF. Likes use a composite
primary key and post lock; comments use a database unique retry constraint, text
digest and post lock. UI prevents simultaneous heart requests and rolls back a
failed optimistic update. A lost comment response retains the same retry key/text;
the composer offers Retry or Discard. Social activity never awards points.

## Explicit welcome import

Migration 0004 is additive. It retains all existing posts, users, memberships,
upload fingerprints and grace history. System posts have nullable user_id, source
system and zero score. Their Upload records retain the importing operator solely
for accounting; UI attribution is the group. Child photos are hidden from normal
feed pagination and only returned through the welcome album. All objects count
toward the existing global storage quotas and use short-lived authorized access.

Import only after migrating, using the normal production environment injected
securely. Do not paste secrets into terminals, documentation or chat. Example:

```powershell
uv run --directory backend python -m app.cli seed-welcome `
  --group-id bad0f3b9-c9ff-4c6f-a563-56575993e367 `
  --operator-id EXISTING_ADMIN_UUID `
  --photo 'ABSOLUTE_PATH_TO_GROUP_SELFIE.jpg' `
  --photo 'ABSOLUTE_PATH_TO_NEXT_ORIGINAL.jpg'
```

First photo is the cover. Repeat --photo in the same order on resume. The importer
rejects every group except the explicitly identified initial Mustaaaaaard ’27
group and requires its active admin. A session advisory lock fences simultaneous
operator imports; it is committed before media IO. Bounded sanitization strips
metadata and preserves decoded pixels/orientation/aspect ratio without resizing.
Reservations are committed before object PUT; acceptance is atomic after PUT.
Interrupted uploads remain recoverable cleanup debt; no DB transaction spans IO.
Re-running skips existing seed keys, honors admin unpin/removal and retains
original fingerprints. Removal marks the whole album for normal object cleanup.

`design-input/` is ignored before any local copying. Supplied originals stay
outside source/public assets/Git/screenshots/CI artifacts. Welcome storage is
private. Public favicons now use a deterministic round M monogram; the earlier
photo favicon remains in historical Git commits, which this release does not
rewrite. Import uses the original photographs, excluding the two social-app UI
screenshots (profile-sharing and camera overlays), with no inferred identities.

## Verification

Local browser tests use isolated synthetic content with real FastAPI/PostgreSQL/
MinIO. Screenshots at 320px, 390px and 1440px contain synthetic media only.
Physical phone camera and keyboard behavior require actual device checks.
