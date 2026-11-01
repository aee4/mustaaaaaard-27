# Mustaaaaaard ’27

Backend: one FastAPI application, Python 3.12+, synchronous SQLAlchemy 2
sessions and PostgreSQL. Keep routes thin, services own transactions. Never hold
a database transaction across media processing, HTTP, or object storage calls.
All schema changes are Alembic revisions; never use create_all in production.

Use UTC aware timestamps and injected clocks; activity calendar is Africa/Accra.
Scores derive from accepted, nonremoved posts. Capture consumption and post
acceptance are atomic. PostgreSQL uniqueness is the concurrency authority.
Preserve original fingerprints and grace history after deletion. All group
resources require active membership. Never log cookies, media, or signed URLs.

Python source/configuration lives in backend/. Run commands from the root with
`uv run --directory backend ...`; native Settings reads only backend/.env, with
process environment precedence. Root .env is Compose input. Never move runtime
data under .tools/, virtual environments, node_modules or builds with source.
Run `uv run --directory backend ruff check .`, `uv run --directory backend ruff format --check .`, `uv run --directory backend mypy app`,
and `uv run --directory backend pytest`. PostgreSQL/MinIO integration tests must run against real
services, never SQLite. Record actual verification and blockers in PROGRESS.md.
Keep SPEC.md, API documentation and implementation consistent. Do not deploy,
purchase services or expand product scope.

Frontend is authorized in frontend/: React/TypeScript/Vite/Tailwind. Generate API
types from OpenAPI; preserve cookie/CSRF and authoritative backend values. No mock
fallback, tokens in localStorage, unsupported social features or invented fields.
Run frontend lint, typecheck, unit tests, production build and real-backend browser
tests. Distinguish synthetic browser capture from physical device verification.

Captions are now part of the upload contract: normalize multipart CRLF/CR, enforce
280 Unicode code points, render plain text, include normalized caption digest in
idempotency checks, and clear post caption text on removal. Never let a caption
change evade original-media duplicate protection.
