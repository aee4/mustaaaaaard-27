# Repository separation and typography — 2026-11-01

## Repository verification completed before UI changes

Moved 46 source/configuration files into backend/ and verified their SHA256 hashes
immediately after the move. Subsequent intentional backend edits are Settings'
explicit backend/.env path, Alembic's absolute paths/OS path separator, Docker
ignore rules and example-env comments. Existing app code, tests, uv.lock and
migration revision files are otherwise preserved. The MinIO Dockerfile also moved
to backend/docker/. No database recreation, volume deletion or migration-history
rewrite occurred. Native data/tools remain under root .tools/. Root .venv/caches
were left in place; uv sync recreated backend/.venv from the existing lock.

Root retains shared docs, rules, CI, compose.yaml and Compose .env.example.
backend/scripts contains backend storage/smoke tooling. There are no cross-project
scripts yet, so no empty root scripts directory was created. Frontend API type
generation still reads ../docs/openapi.json from frontend/; that path is unchanged.
CI and Compose build paths now use backend/. Named volumes and service ports are
unchanged. Native commands in README and phone/local guides use uv --directory.

The first Alembic check exposed Windows path splitting in a directory containing
spaces; path_separator=os fixed it. Actual application DB remains at 0002 (head),
with no schema drift. No downgrade was run against working data. The separate
mustard_test DB was used for pytest's existing disposable fixtures.

Before typography changes, checks passed:

- Backend Ruff check/format, mypy, 90 pytest tests (21.39s, two existing adapter
  deprecation warnings); alembic upgrade/check on test DB, current/check on app DB.
- Frontend API generation, ESLint, TypeScript, 15 unit tests, production build.
- Seven real-backend Chrome integration tests (23.7s), including media, group
  onboarding, permissions, retry and switching.
- Native API restarted through the updated root command; frontend, direct API
  readiness and proxied readiness each returned 200.
- Compose/CI YAML parsed and build-context paths reviewed. Docker executable is
  absent: image build and Compose startup remain unverified, as do remote CI runs.
- Source secret-pattern review found no candidates. No live root/backend .env
  files exist. This workspace has no .git metadata, so a tracked-file/history
  secret audit or Git diff was unavailable; preservation used file hashes instead.

Live OpenAPI comparison also found an existing mojibake apostrophe in the exported
API title. Refreshed the export from the actual live schema; endpoint/schema content
was unchanged. Generated TypeScript continues to use the existing API contract.

Before screenshots captured at 390×844, 1440×1000 and 320×740 cover login, Feed,
Capture, Leaderboard, Profile and backend-unavailable state under ignored
.tools/typography-before/. Run from root with
`node frontend/scripts/visual-review.mjs before` (or `after`) while local services run.
The review uses real development login and an explicitly simulated network failure
for the error screen; it never supplies fabricated activity.

## Typography and final checks

Self-hosted Inter Variable 5.3.0 replaces all editorial serif families and italic
styling. Shared family/weight/heading-spacing tokens cover branding, navigation,
controls, stats, forms, dialogs and feedback. Weights are 400/500/600/800; numeric
scores/ranks/countdowns use tabular numerals. Reduced headings and slogans preserve
mustard/cream/charcoal and prominent capture. Fixed Capture's 320px overflow by
explicitly sizing its aspect-ratio preview and allowing grid/tab children to shrink.
The SIL Open Font License is included in frontend/public/INTER-LICENSE.txt and the
built output. Inter is an alternative, not Snapchat's exact font; no proprietary
fonts or third-party font CDN are used.

After typography: ESLint, TypeScript, 15 unit tests, production build and npm audit
(zero findings) passed. Seven real-backend browser tests passed again in 22.9s.
Production preview verified Google entry, hidden development login, loaded Inter
and served license. Live OpenAPI equals the refreshed export. Backend did not
change after its 90-test verification, so no additional backend regression run
was necessary for the CSS/font changes.

Reviewed screenshots at 320/390/1440px, including real synthetic-media posts,
Feed/Capture/Leaderboard/Profile/login, no-group/create/join, gallery/preview,
camera-denied, backend-unavailable and leave-capture dialog. The reusable review
asserts loaded Inter, normal font style, compact tracking, tabular numerals and
no horizontal overflow. Before/after artifacts remain in .tools/typography-before
and .tools/typography-after; real integration screenshots are in
frontend/test-results. Loading states were also inspected with delayed requests.
These are desktop Chrome checks with synthetic devices and simulated errors;
physical Android/iPhone, Safari, Docker execution and remote CI remain unverified.

Fixture posts were removed and 12 private objects cleaned after integration tests.
Default rate limits restored; local native app left on http://localhost:3000,
API 127.0.0.1:58000. No deployment, public exposure or working-data reset.
