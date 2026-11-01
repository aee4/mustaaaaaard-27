# Backend handoff verification — 2026-11-01

**Verdict:** ready for local frontend API integration using development login and
the verified native service setup. Container-based setup is not yet verified.
This is not production readiness or approval to deploy. No frontend implementation
or deployment was started during this verification.

## Documents and provenance reviewed

Read README.md, PROGRESS.md, docs/frontend-integration.md, AGENTS.md,
docs/local-verification.md, Compose/Dockerfiles and the smoke fixtures.

The original reported tests did not use Docker:

| Dependency | Provision used originally and repeated here |
|---|---|
| PostgreSQL | Existing `C:\Program Files\PostgreSQL\18\bin` installation. Separate cluster `.tools/pgdata`, initialized with local trust authentication, started through pg_ctl; loopback 127.0.0.1:55432. Dedicated `mustard_test` DB for pytest. No SQLite or existing system DB service used. |
| MinIO | Real Windows executable `.tools/minio.exe`, built from pinned upstream source `RELEASE.2025-10-15T17-29-55Z` using portable Go 1.25.5 after upstream binary download returned 410. Foreground process, loopback 127.0.0.1:59000; private local bucket `mustard-private`. Reports DEVELOPMENT.GOGET because built via go install. |
| FFmpeg/FFprobe | Portable Gyan essentials 9.0.2 Windows executables under `.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin`; explicit FFMPEG/FFPROBE paths, real child processes for validation/transcoding. Not mocked for media integration/smoke checks. |

Most failure/unit tests use in-memory storage simulations; the named MinIO tests
and both smoke runs use real S3 calls. The pytest application is exercised via
FastAPI TestClient with an injected clock. The additional HTTP smoke below uses
an actual Uvicorn socket, application clock, cookie jars and server configuration.

## Docker limitation precisely stated

`docker --version` returned CommandNotFoundException. `Get-Command docker` returned
no executable. Both standard Docker Desktop resource paths checked for docker.exe
and docker-compose.exe were absent. Docker was not installed as part of this task.

Accordingly **none** of the following is claimed verified:

- Docker image pulls/builds, including the Linux MinIO source-build stage.
- Linux container dependencies, filesystem ownership and unprivileged-user access.
- Compose volume initialization/persistence, networking/service DNS and dependency
  startup sequencing.
- Migrations or admin bootstrap executed inside a container.
- API readiness or signed browser-accessible media URLs through the Compose topology.

Parsing compose.yaml or running corresponding native binaries does not verify
these properties. Documented Compose startup was not run because the runtime is
unavailable. Run it on a Docker-enabled machine before treating that setup path
as tested. Remote GitHub Actions has also not been run here.

## Commands actually run and results

Restarted the retained loopback PostgreSQL cluster and MinIO, then used the
environment from docs/local-verification.md:

```text
uv run --directory backend python -m scripts.init_storage                     private bucket ready
uv run --directory backend alembic upgrade head                               success
uv run --directory backend alembic check                                      no schema drift
uv run --directory backend pytest tests/test_storage_video.py -k two_user -v   1 passed, 8 deselected
uv run --directory backend pytest -q                                          65 passed, no skips
```

Full-suite runtime was 10.15s. Two existing upstream Starlette/Authlib httpx adapter
deprecation warnings remain visible. They are not suppressed or test failures.

For the independent HTTP check, created a new disposable database
`mustard_handoff_test` on the isolated PostgreSQL cluster (no real data reset), then:

```powershell
$env:DATABASE_URL='postgresql+psycopg://mustard@127.0.0.1:55432/mustard_handoff_test'
$env:S3_ENDPOINT='http://127.0.0.1:59000'
$env:DEV_AUTH='true'
$env:FFMPEG=(Resolve-Path '.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe').Path
$env:FFPROBE=(Resolve-Path '.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe').Path
uv run --directory backend alembic upgrade head
uv run --directory backend python -m app.cli bootstrap-admin --subject dev:handoff-admin --display-name 'Handoff Alice'
uv run --directory backend uvicorn app.main:app --host 127.0.0.1 --port 58000 --no-access-log
```

With that server running, and FFMPEG set in the invoking shell:

```powershell
uv run --directory backend python -m scripts.smoke
```

Observed and asserted:

| Check | Result |
|---|---|
| Readiness using actual DB schema/private bucket | HTTP 200 |
| Users/group | 2 users, 1 private group; admin CLI + invite join |
| Accepted capture photo | 1 point |
| Accepted five-second capture video | 3 points |
| Accepted gallery photo | 0 points |
| Feed | Exactly the three accepted posts |
| Weekly/all-time leaderboard | Bob 3 points, Alice 1 point; counts match |
| Gallery/streak | Bob has one active day from capture; gallery adds none |
| Signed media read | HTTP 200 |
| Same object without signature | HTTP 403 |

Smoke removes posts, revokes its invite, removes the temporary member and logs out
both sessions; fingerprints/tombstones remain as designed. Run the cleanup CLI to
delete removed media objects. Fixtures use distinct original bytes on each run.

The HTTP smoke was run twice successfully, including rank order assertions on the
second run. Cleanup then reported `objects_cleaned=6`. Final Ruff check/format
(44 files), mypy (23 app files), lockfile check and Alembic drift check all passed.
Uvicorn, MinIO and the isolated PostgreSQL cluster were stopped after verification;
the disposable databases/tool files remain for repeat verification.

## Fixes and remaining gates

No application failure was found in the repeated integration/smoke runs. Added
backend/scripts/smoke.py to make the actual HTTP workflow reproducible without importing
test fixtures. Added readiness command and clarified container verification scope
in README and frontend integration docs.

Real Google account consent/discovery/callback still requires registered credentials.
Mocked signed-OIDC protocol tests do not replace that check. Production HTTPS,
cookies/origins, S3 IAM/CORS, backups and restore remain operator verification gates.
Browser camera permission/codec behaviour must be tested once an actual frontend
exists; a valid server capture session cannot prove original camera provenance.

Next infrastructure check: on a Docker-enabled machine follow README's fresh
Compose startup, explicit admin bootstrap and readiness command, then run the HTTP
smoke against port 8000. Frontend work remains intentionally unstarted.
