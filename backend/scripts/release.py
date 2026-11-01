"""Controlled schema-only release; never import local users, sessions or objects."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.integrations.storage import S3Storage


def release() -> None:
    settings = get_settings()  # fail closed before connecting if production settings are unsafe
    S3Storage(settings).ready()  # bucket must already exist and be operator-configured private
    engine = create_engine(settings.database_url)
    with engine.connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(270004)"))
        lock.commit()
        try:
            command.upgrade(
                Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head"
            )
            command.check(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")))
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(270004)"))
            lock.commit()
    engine.dispose()
    print("Release migrations applied; no development data imported")


if __name__ == "__main__":
    release()
