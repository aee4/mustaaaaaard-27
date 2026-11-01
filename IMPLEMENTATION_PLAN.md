# Implementation plan and acceptance checklist

1. **Foundation — implemented and locally verified**
   - [x] Architecture/product rules before code; modular Python application.
   - [x] Safe configuration, UTC/calendar helpers, explicit schema and constraints.
   - [x] PostgreSQL upgrade/downgrade/upgrade/drift check; health/readiness.
   - [x] Compose, source-build MinIO, lockfile, CI and structured errors.
2. **Identity/groups — implemented and locally verified**
   - [x] Hashed opaque sessions, expiry/logout, cookies and CSRF/Origin enforcement.
   - [x] Authlib OIDC state/nonce/PKCE/signed identity validation and dev isolation.
   - [x] Profiles, explicit admin CLI, expiring/revocable/usage-limited invites.
   - [x] Membership checks/audits; concurrent invite and signed mock-provider tests.
3. **Media/points — implemented and locally verified**
   - [x] Capture sessions, gallery path, authoritative acceptance time/scoring.
   - [x] Request/file limits; real decoder validation and metadata sanitation.
   - [x] Actual JPEG/MP4/WebM, duration/codec tests and real private MinIO roundtrip.
   - [x] Leased staging/idempotency; concurrent duplicates and atomic capture/post.
   - [x] Partial failures, commit ambiguity, DB outage and orphan cleanup recovery.
4. **Feed/rankings — implemented and locally verified**
   - [x] Group-scoped keyset feed and member-authorized signed media access.
   - [x] Weekly/all-time live scores/counts; competition ranks and stable tie order.
   - [x] Own/admin removal, immediate exclusion, pagination and cross-group tests.
5. **Streaks/grace — implemented and locally verified**
   - [x] Distinct scoring dates/current/longest; persisted immutable weekly grace.
   - [x] Deletion policy specified first; serialized replay and gallery exclusion.
   - [x] Midnight/Monday, unfinished today, one/two misses, Sunday/Monday tests.
6. **Hardening/handoff — implemented and locally verified**
   - [x] Full suite: 65 passed, no skips; Ruff/format/mypy/lock/migration checks.
   - [x] Real two-user MinIO photo/video/gallery/feed/rankings smoke integration.
   - [x] Configuration/authorization/failure review and bounded external IO.
   - [x] Setup, backup/retention/recovery and frontend integration documentation.
   - [x] OpenAPI export with cookie security and explicit error-envelope schemas.

Environment-dependent handoff checks (not claimed passed):
- [ ] Docker image builds and Compose startup on a Docker-enabled machine.
- [ ] Remote GitHub Actions run after repository publication.
- [ ] Real Google consent/callback using registered credentials.
- [ ] Production HTTPS proxy/IAM/bucket CORS/backup-restore verification.

These need an external runtime or operator configuration. No deployment or paid
service was requested or performed. Actual evidence and limits are in PROGRESS.md.

## Frontend phases (authorized 2026-11-01)

7. Foundation/contract
   - [x] React + TypeScript + Vite + Tailwind in frontend/, npm lock, generated API types.
   - [x] Central cookie/CSRF client, TanStack Query, dev proxy and auth error states.
8. Main experience
   - [x] Mobile/desktop brand, group/invite flows, cursor feed, refreshing private media.
   - [x] Weekly/all-time rankings, authoritative profile stats, countdowns and moderation.
9. Capture/upload
   - [x] Capability-checked camera photo/video, server session before capture, previews/retake.
   - [x] Gallery=0, progress, validation, stable retry keys, expiry and track/navigation cleanup.
10. Verification/handoff
   - [x] Session/CSRF/error/pagination/retry/scoring tests; lint/type/build.
   - [x] Real-backend browser two-user smoke and synthetic camera checks.
   - [x] Permission/network states, responsive QA, README startup and private HTTPS phone checklist.

Historical limitation: captions were absent from the original backend contract.
Optional caption support is now explicitly authorized for local acceptance.

11. Local acceptance (2026-11-01)
   - [x] Start native services/frontend and compare all three key screens to reference.
   - [x] Nullable caption migration, 280-character validation, retry fingerprint and deletion privacy.
   - [x] Generated types, caption input/display, browser/unit/API coverage.
   - [x] Migration/data checks and all affected backend/frontend checks.
   - [x] Explicit Android/iPhone private HTTPS instructions, device-status separation.
   - [x] Leave loopback app running with readiness/URL evidence; no deployment.

12. Group onboarding (2026-11-01)
   - [x] Verify/bootstrap Alice's initial admin membership without automatic visitor privileges.
   - [x] Authenticated POST /groups: validated name, atomic creator-admin membership, audit and limits.
   - [x] Empty state with create/join actions; immediate selection/feed after success.
   - [x] Accessible multi-group switching and group-specific UI-state reset.
   - [x] Admin invite generation/copy; backend and real-browser creation/join/permission tests.
   - [x] Regenerate API types, affected checks, update documentation and leave local app ready.

13. Repository separation (2026-11-01; before typography)
   - [x] Inspect instructions/source; hash moved backend files; preserve data and dependencies in place.
   - [x] Separate backend source/config/tools; update Compose/CI/native commands and environment loading.
   - [x] Recreate backend environment; lint/format/type/tests/migration and real-browser regression checks.
   - [x] Native startup/readiness, source secret-pattern review; document Docker limitation.
14. Shared sans-serif typography
   - [x] Licensed local font, shared family/weight/spacing tokens, compact headings and tabular numerals.
   - [x] Inspect every screen/state at mobile/desktop widths and capture before/after.
   - [x] Frontend and real-backend browser checks; final docs and local readiness.

15. Conditional free-tier deployment preparation
   - [x] Verify published Render/Neon/R2 terms; identify missing account-specific access and R2 exposure.
   - [x] Same-origin image, favicon, production auth/secret guards, startup migration/cleanup for Free.
   - [x] Atomic storage-byte/object quotas, processing admission, bounded FFmpeg, safe resource failures.
   - [x] Maximum-size 1080p/4K Windows process-tree stress, including approximate 0.1 CPU.
   - [ ] Reliable maximum-video proof on Linux at 512 MiB/0.1 CPU (Linux unavailable; original encoder failures superseded by phase 16).
   - [ ] Account eligibility/quota verification and explicit R2 overage approval.
   - [ ] Actual production Google/media/group/device verification after deployment gates pass.

16. Approved 720p video processing before provisioning
   - [x] Inspect universal encoder cost; preserve validation and switch compatible inputs to remux.
   - [x] Server-side 720p/profile/container checks, metadata/SEI removal, independent decoded timing.
   - [x] Best-effort 720p/30fps/2.5Mbps capture, preview validation and actionable guidance.
   - [x] Synthetic codec/portrait/rotation/metadata tests, real signed browser playback and regression checks.
   - [x] Three maximum-size landscape/portrait Windows process-tree runs at 512 MiB/approximate 0.1 CPU, including H.264 High/B-frames.
   - [x] Update specification, frontend contract, phone checklist and deployment evidence.
   - [x] Linux cgroup/image gate: [manual CI run 41355405807](https://github.com/aee4/mustaaaaaard-27/actions/runs/41355405807) passed under the approximate target limit; Render remains a separate deployment gate.

17. Manual Linux container gate without local Docker
   - [x] Inspect existing Actions and repository access; preserve existing push/PR workflows.
   - [x] Add separate manual Ubuntu production-image build, isolated PG/MinIO integration tests.
   - [x] Whole-cgroup 512 MiB/no-swap/0.1 CPU limits, maximum 720p workload, browser playback and recovery assertions.
   - [x] Sanitized small artifacts, explicit free-allowance acknowledgement and exact trigger documentation.
   - [x] Local syntax/schema, helper and native HTTP/browser checks; no WSL/system changes.
   - [x] Dispatch and review the storage-free public-repository run: production image, PostgreSQL/MinIO integration, cgroup evidence, playback and recovery all passed (run 41355405807).
   - [ ] Dispatch/inspect actual Linux run after the intended repository and free allowances are available.
   - [ ] Record run URL/commit and real counters before marking Linux verified; actual Render remains separate.
