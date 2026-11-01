# Verification environment used on this Windows host

The cross-platform setup is Compose in README. This host had no Docker. Verification
used the existing PostgreSQL 18 installation and portable binaries under ignored
`.tools/`. No system service or production data was changed. The test cluster uses
local trust authentication **only on loopback**; never use that in production.

Tools: FFmpeg/FFprobe 9.0.2 (Gyan essentials), Go 1.25.5, MinIO built with:

```powershell
$env:GOBIN=(Resolve-Path .tools).Path
& .tools/go/bin/go.exe install github.com/minio/minio@RELEASE.2025-10-15T17-29-55Z
```

To repeat with retained tools, start the isolated PostgreSQL cluster:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D .tools/pgdata -l .tools/postgres.log -o '-h 127.0.0.1 -p 55432' start
```

In a separate terminal, run MinIO in the foreground:

```powershell
$env:MINIO_ROOT_USER='mustard-local'
$env:MINIO_ROOT_PASSWORD='mustard-local-password'
& .tools/minio.exe server .tools/minio-data --address 127.0.0.1:59000 --console-address 127.0.0.1:59001
```

Initialize storage, migrate the dedicated test DB, and run checks in another shell:

```powershell
$env:S3_ENDPOINT='http://127.0.0.1:59000'
$env:DATABASE_URL='postgresql+psycopg://mustard@127.0.0.1:55432/mustard_test'
$env:TEST_DATABASE_URL=$env:DATABASE_URL
$env:TEST_S3_ENDPOINT=$env:S3_ENDPOINT
$env:FFMPEG=(Resolve-Path '.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe').Path
$env:FFPROBE=(Resolve-Path '.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe').Path
uv run --directory backend python -m scripts.init_storage
uv run --directory backend alembic upgrade head
uv run --directory backend pytest -q
uv run --directory backend ruff check .
uv run --directory backend ruff format --check .
uv run --directory backend mypy app
```

After testing, Ctrl+C in MinIO's terminal, then stop this isolated cluster:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D .tools/pgdata stop -m fast
```

Downloaded tools/data are excluded from Git/Docker build context and retained for
repeat verification. They are not source deliverables. No production credentials
are stored in this repository.
