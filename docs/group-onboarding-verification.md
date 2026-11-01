# Group onboarding verification — 2026-11-01

Implemented authenticated POST /groups, validated names, atomic creator-admin
membership and audit, PostgreSQL uniqueness/concurrent creation handling and
GROUP_RATE (5 attempts/user/minute). Existing schema supports this; no new migration
is needed (head remains 0002). OpenAPI export and generated TypeScript include it.

Explicit bootstrap was rerun for dev:alice against native mustard_handoff_test.
Actual HTTP login with lower-case alice returned Mustaaaaaard ’27 with role admin;
its feed returned 200. Login alone still never adds membership. The initial group
name is reserved, and creating another group gives no rights in existing groups.

Frontend now has a clear no-membership state, Create group / Join with invite,
automatic selection and Feed navigation on success, Groups manager and membership
selector. Profile admins can generate/copy private invite links, with a manual-copy
fallback if clipboard access fails. Switching opens Feed and resets group view
state, including previously generated invite links. Existing mustard/cream design,
capture discard confirmation and server authorization remain intact.

Checks actually performed:

- Ruff check/format, mypy: passed.
- Full pytest against real PostgreSQL/MinIO/FFmpeg: **90 passed**, no skips,
  21.03 seconds; two existing httpx adapter deprecation warnings.
- Added API coverage: authentication/CSRF, forbidden privilege fields, invalid and
  normalized names, reserved/duplicate names, concurrent creation, creator-admin
  audit/membership, invite joining, member admin denial and cross-group isolation.
- ESLint, TypeScript, **15 unit tests**, production build and npm audit: passed;
  audit reported zero vulnerabilities. Unit coverage includes empty state,
  creation/select/feed and creation cookie/CSRF contract.
- **7 real-backend Chrome tests passed**, 25.2 seconds. Two added scenarios verify
  Alice's initial admin access and a fresh user's empty state → create → Feed →
  generate/copy invite → friend joins as member → second group → switching.
  Distinct real gallery uploads/captions verify feeds do not leak between groups;
  a member cannot create invites or read a group before joining. Old invite UI
  clears on switching. Existing capture/media/retry/error tests also pass.
- Compiled production preview: Google entry present, development form absent.
  This checks login presentation, not a real Google authentication roundtrip.
- Live OpenAPI equals docs/openapi.json, including POST /groups.

Browser runs used disposable unique development identities/groups in the local
handoff database, temporary raised test rate limits and synthetic Chrome video/audio.
Fixture posts were removed and private objects cleaned afterward. Test groups,
memberships and audit/tombstone records remain; no group deletion API was added.
Backend pytest used separate mustard_test and did not truncate the running app DB.
Restored default auth/invite/upload/group rates: 30/30/60/5 per minute.

Local development URL: http://localhost:3000 (loopback); API 127.0.0.1:58000.
PostgreSQL/MinIO remain native loopback services. No deployment/public tunnel.
Physical Android/iPhone, Safari, real Google login and Docker packaging remain
unverified. Synthetic camera tests do not establish physical-device compatibility.
Private HTTPS phone instructions remain in [phone-https.md](phone-https.md).

Manual acceptance: log in as alice to see the initial admin group. In another
private window log in with a new ID, create a group and confirm Feed opens. Generate
an invite in Profile; join it in a third user window. Use Groups to create/join a
second group, then the Your group selector to switch. Confirm each group's Feed,
rankings and Profile permissions correspond to the selected membership.
