# Manual Linux container verification

## Repository publication update

The intended repository is https://github.com/aee4/mustaaaaaard-27 (public).
Access as aee4 and Actions enabled were confirmed on 2026-11-01. Standard public
GitHub-hosted runner compute is free under the current official billing policy.
Artifact quota could not be read, so `publish_artifacts` defaults false: sanitized
JSON is retained in job logs/summary without artifact upload. Enable artifact
publishing only after confirming included storage. No billing settings are changed.
Earlier access limitations below describe the preparation session.

**Status on 2026-11-01: prepared and locally checked, not run on Linux.**
This is verification only: no deployment, image registry push, hosting resources,
R2 subscription or paid usage is configured. No WSL installation/system change is
needed on the Windows workstation. The existing push/PR workflows are unchanged.

## What the job checks

`.github/workflows/linux-container.yaml` runs only through `workflow_dispatch` on
the standard `ubuntu-24.04` GitHub-hosted runner. It requires the free-allowance
confirmation described below; unchecked means the job is skipped, **not verified**.
There is one job, a 45-minute timeout, read-only repository permission, no saved
checkout credentials, no dependency cache publication, and 3-day artifact retention.

1. Install locked tools, FFmpeg/FFprobe and Playwright Chromium on the ephemeral
   runner. Build the **root production Dockerfile**, including compiled React and
   the real FastAPI entrypoint, plus the existing source-built MinIO image.
2. Start isolated PostgreSQL 18 and private MinIO. Use a separate `mustard_linux_test`
   database/bucket for the full backend suite and its real-service/video integration
   tests. Apply/check migrations. Missing/skipped tests fail the sanitized results
   gate. Nothing contacts the workstation's database or uploads.
3. Generate existing synthetic 30s/exactly 50 MiB 720p landscape, portrait and H.264
   High/B-frame fixtures plus VP8/Opus and VP9/Vorbis WebM. These are synthetic,
   not recordings from Android/iPhone hardware.
4. Run the production **image** with one application process, one media job and
   one FFmpeg thread, **512 MiB RAM, no swap, 0.1 CPU**. The CI-only runtime overrides
   enable test authentication with insecure cookies strictly on runner loopback;
   the image's production defaults remain dev-auth=false/secure-cookie=true, and
   its compiled frontend has no development login form. This is not production
   Google consent, HTTPS or cookie verification.
5. Require readiness within 180 seconds. Upload each maximum-size video with real
   capture/session/CSRF/idempotency flows and require HTTP acceptance within 180s
   per video. Verify video=3, gallery=0, feed/rankings and signed media playback in
   real Chromium; verify unsigned GET=403. Check exact maximum-fixture dimensions
   and 30s playback metadata, plus VP8/VP9 playback. No mock storage/playback.
6. Probe `/api/ready` every two seconds throughout workloads with a six-second
   request timeout; unexpected non-200 results fail. Invalid-media requests must
   remain retryable without consuming a capture. A valid upload/replay must create
   exactly one post.
7. Observe an actual FFmpeg child in the disposable app container; assert a
   concurrent small upload returns retryable `503 media_busy`. Kill only that
   FFmpeg child, require `503 media_resources_exhausted`, then retry identical
   video bytes/capture/key successfully. Retry the busy photo with its original key.
   Verify replay uniqueness and gallery=0. This is injected SIGKILL, **not an OOM
   experiment**. OOM events remain a failure, not a success claim.
8. Save kernel counters before restart, restart the app container, recheck readiness
   and valid/idempotent upload recovery. Collect fresh counters separately so a
   restart cannot erase the earlier measured peak or OOM evidence.

The two-file Compose stack is `compose.resource.yaml` plus
`compose.linux-verification.yaml`. Only app port 58001, Postgres 55432 and MinIO
59000 bind to **127.0.0.1 on the disposable runner**. Internal PUT/HEAD use Docker
networking; signed URLs use the runner-reachable MinIO endpoint. Buckets have no
anonymous policy. The cleanup step removes only this job's isolated Compose project
and its synthetic volumes; it never runs against the native working stack.

## Whole-container measurements and limitations

Require cgroup v2 and read `memory.max`, `memory.swap.max`, `memory.current`,
`memory.peak`, `memory.events`, `cpu.max` and `cpu.stat` inside the application
container. Assert 536,870,912-byte limit, zero swap, CPU quota/period=0.1, bounded
peak, zero OOM/oom_kill events and a live container. Preserve selected Docker
running/exit/OOM/restart state. Missing counters or unenforced limits fail closed.

Kernel accounting covers the **entire application cgroup**: uv launcher, Python,
FFprobe/FFmpeg descendants, temporary-file page cache and tiny diagnostic processes.
It does not measure only FFmpeg. CPU usage/throttling counters are retained, not
inferred from the requested Compose setting. Browser/load generation and external
Postgres/MinIO run outside that cgroup, as managed services would on the target.
Readiness timings are waits from each probe phase, not a precise Render cold-start
measurement. Primary HTTP times exclude the subsequent browser playback check.

GitHub's CPU, kernel, image layers/cache, disk, scheduler, network and neighbouring
workloads differ from Render. Local Docker networking is faster than remote
Neon/R2; this test does not model their TLS, quotas, latency or cold starts. A
successful run is evidence for Linux container operation under **approximate target
resource constraints**, not proof of actual Render performance or availability.
Physical Android/iPhone/Safari, real Google login and actual production services
remain separate checks. Do not provision simply because a workflow was added.
[Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/),
[Linux cgroup v2 accounting](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html).

## Trigger without paid usage

Repository access is currently missing: this working folder has no `.git` metadata
or remote, `gh auth status` reports signed out, and the connected GitHub app exposes
only an unrelated repository. No workflow was uploaded/dispatched, no billing
settings were changed, and no free account quota could be inspected.

1. **Before pushing or running**, use the intended repository owner's GitHub
   **Settings → Billing and licensing → Usage / Budgets and alerts** (labels may
   vary by account). Confirm remaining included Actions compute and artifact storage
   cover this job (allow up to 45 standard Linux runner minutes, plus the existing
   push/PR workflows that a push will trigger). Do not select a larger runner,
   raise any paid budget, enable overage, or add a paid plan. Confirm the owner's
   stop-usage policy blocks paid excess. If quotas/policy are unclear, do not run.
   Standard hosted runners have free compute for public repositories; private
   repositories draw from owner-plan included allowances. Artifact/storage usage
   is separate. Do **not** make private source public to obtain free execution.
   The confirmation checkbox and timeout are not a billing hard cap.
   [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
2. Put this project and the new/modified files into the **intended Mustaaaaaard
   repository**, preserving `.gitignore` and excluding `.env`, `.tools`, databases,
   media, virtual environments and node_modules. Use your existing repository
   workflow; do not push this project into the unrelated connected repository.
   No repository was created automatically. Commit/merge the verification workflow
   to the default branch; it must be there for the manual trigger to appear.
   [GitHub manual trigger requirements](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
3. In that repository, open **Actions → Linux container verification (manual, no
   deployment) → Run workflow**. Select the branch containing the complete change.
   Check `free_allowance_confirmed` only after step 1, then run once. No repository
   secrets, Render/Neon/Cloudflare keys or Google credentials are needed.
4. Alternative CLI, from an authenticated workstation (web/device login; never
   paste tokens into chat), replacing `OWNER/REPO` and branch with the real values:

   ```powershell
   gh auth login --web
   gh workflow run linux-container.yaml --repo OWNER/REPO --ref main -f free_allowance_confirmed=true
   gh run list --repo OWNER/REPO --workflow linux-container.yaml --limit 1
   gh run watch RUN_ID --repo OWNER/REPO --exit-status
   gh run download RUN_ID --repo OWNER/REPO --name linux-container-verification --dir .tools/linux-verify/download
   ```

5. Require the **job** to complete successfully, not be skipped. Download the
   `linux-container-verification` artifact. Both `container.json` and
   `integration.json` must say `passed: true`; inspect cgroup peaks/OOM, HTTP timings,
   every playback/recovery result and all integration test outcomes. A placeholder
   `workflow_not_completed` report or missing evidence is not a pass. Record the run
   URL, commit SHA, image ID, counters and timings in PROGRESS.md before changing
   the Linux gate. Do not claim Render or physical-phone verification from this run.

Artifacts contain only an explicit JSON allowlist: sanitized test names/outcomes,
image ID/FFmpeg version, counters, timings, status codes and limited lifecycle
messages. Raw pytest XML/captures, Docker environment dumps/full logs, signed URLs,
cookies, credentials, DB dumps, screenshots, traces and synthetic/private media
are excluded. Reports expire after three days; download the small evidence if
needed. The job publishes no container image and deploys nothing.

## Actual local checks

Workflow syntax passed actionlint 1.7.12 (official Windows release, checksum checked,
kept under ignored `.tools`; no system installation). Shellcheck/pyflakes were not
available for actionlint; Ruff checks Python and actionlint checks Actions syntax.
Both Compose files validated against the official Compose JSON schema; actual
Compose merging/building is pending Linux execution.

Ten verification-helper tests passed on Windows. They test fail-closed resource
checks and artifact redaction, not real Linux limits. The real native local backend
also passed the new invalid-media/replay helper, both WebM browser playback helpers,
and all three maximum-size MP4 upload/playback helpers with unsigned storage denial.
Those HTTP/browser checks used native PostgreSQL/MinIO/Chrome **without resource
limits**; they do not satisfy the Linux gate. Docker metrics, child fault injection
and container restart recovery have not been executed here. No CI run URL exists.

The full native backend suite passed **126 tests**, no skips (89.59s; two existing
httpx deprecation warnings). Ruff check/format, mypy, frontend ESLint/TypeScript,
20 unit tests and production build passed. These are local checks, not Linux CI.
