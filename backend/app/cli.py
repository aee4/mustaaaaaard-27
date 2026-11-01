from datetime import timedelta
from uuid import UUID

import typer
from sqlalchemy import delete, select, text

from app.core.clock import Clock
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.integrations.storage import S3Storage
from app.models.entities import LoginSession, RateBucket, Upload, User
from app.services.identity import bootstrap
from app.services.uploads import UploadService

cli = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)


@cli.command("bootstrap-admin")
def bootstrap_admin(
    subject: str = typer.Option(..., "--subject"), display_name: str = "Admin"
) -> None:
    """Explicitly grant admin to google:SUB, or dev:NAME outside production."""
    config = get_settings()
    if not subject.partition(":")[2] or len(subject) > 255 or not display_name.strip():
        raise typer.BadParameter("A nonempty subject and display name are required")
    if not subject.startswith("google:") and not (
        config.environment != "production" and subject.startswith("dev:")
    ):
        raise typer.BadParameter("Use google:SUB, or dev:NAME outside production")
    with SessionLocal.begin() as db:
        user, group = bootstrap(db, subject, display_name[:80], Clock().now())
        typer.echo(f"user={user.id} group={group.id}")


@cli.command("bootstrap-user")
def bootstrap_user(user_id: UUID = typer.Option(..., "--user-id")) -> None:
    """Operator-only: promote an existing, verified Google user by their session user UUID."""
    get_settings()  # validate host configuration before granting privileges
    with SessionLocal.begin() as db:
        existing = db.get(User, user_id)
        if existing is None or not existing.subject.startswith("google:"):
            raise typer.BadParameter("An existing Google-authenticated user UUID is required")
        user, group = bootstrap(db, existing.subject, existing.display_name, Clock().now())
        typer.echo(f"user={user.id} group={group.id}")


@cli.command()
def cleanup(limit: int = typer.Option(100, min=1, max=10000)) -> None:
    """Delete removed/abandoned media, retain duplicate fingerprints and grace."""
    config, clock = get_settings(), Clock()
    service = UploadService(SessionLocal, S3Storage(config), clock, config)
    count = service.cleanup(limit)
    now = clock.now()
    with SessionLocal.begin() as db:
        db.execute(delete(RateBucket).where(RateBucket.window < int(now.timestamp()) // 60 - 2))
        db.execute(delete(LoginSession).where(LoginSession.expires_at < now - timedelta(days=7)))
        # Captures referenced by uploads/posts are retained. Unused rows are harmless;
        # retain them for diagnostics instead of risking foreign key deletion races.
    typer.echo(f"objects_cleaned={count}")


@cli.command("reconcile-storage")
def reconcile_storage() -> None:
    """Measure legacy object sizes before enabling quotas; never delete memories."""
    config = get_settings()
    storage = S3Storage(config)
    with SessionLocal.begin() as db:
        pending = list(
            db.execute(
                select(Upload.id, Upload.object_key).where(
                    Upload.object_key.is_not(None), Upload.storage_bytes.is_(None)
                )
            )
        )
    measured = 0
    for upload_id, key in pending:
        assert key is not None
        # No DB transaction across object-storage IO. Missing/unreadable objects
        # deliberately remain unknown so quota enforcement continues to fail closed.
        size = int(storage.client.head_object(Bucket=config.s3_bucket, Key=key)["ContentLength"])
        with SessionLocal.begin() as db:
            db.execute(text("SELECT pg_advisory_xact_lock(270003)"))
            row = db.get(Upload, upload_id, with_for_update=True)
            if row and row.object_key == key and row.storage_bytes is None:
                row.storage_bytes = size
                measured += 1
    typer.echo(f"objects_measured={measured}")


if __name__ == "__main__":
    cli()
