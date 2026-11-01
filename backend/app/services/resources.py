"""Process-wide media admission and transactionally serialized storage reservations."""

from functools import lru_cache
from threading import BoundedSemaphore
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import require
from app.models.entities import Upload


@lru_cache(maxsize=8)
def media_gate(capacity: int) -> BoundedSemaphore:
    return BoundedSemaphore(capacity)


def reserve_storage(
    factory: sessionmaker[Session], config: Settings, upload_id: UUID, lease: UUID, size: int
) -> None:
    with factory.begin() as db:
        # All writers serialize the aggregate check; never hold this across S3 IO.
        db.execute(text("SELECT pg_advisory_xact_lock(270003)"))
        row = db.get(Upload, upload_id, with_for_update=True)
        require(
            row is not None and row.lease == lease and row.state == "processing",
            409,
            "upload_lease_lost",
            "Retry upload after cleanup",
        )
        assert row is not None
        if config.storage_quota_bytes or config.storage_object_quota:
            unknown = db.scalar(
                select(Upload.id)
                .where(Upload.object_key.is_not(None), Upload.storage_bytes.is_(None))
                .limit(1)
            )
            require(
                unknown is None,
                503,
                "storage_usage_unknown",
                "Uploads paused until an operator reconciles existing storage usage",
            )
            used, objects = db.execute(
                select(
                    func.coalesce(func.sum(Upload.storage_bytes), 0),
                    func.count(Upload.id).filter(Upload.storage_bytes > 0),
                ).where(Upload.object_key.is_not(None))
            ).one()
            used = int(used or 0)
            require(
                not config.storage_quota_bytes
                or used - (row.storage_bytes or 0) + size <= config.storage_quota_bytes,
                409,
                "storage_quota_exceeded",
                "Storage is full. No new memory was saved; existing memories are retained. Contact your group admin.",
            )
            require(
                not config.storage_object_quota
                or objects + (0 if row.storage_bytes else 1) <= config.storage_object_quota,
                409,
                "storage_quota_exceeded",
                "Storage object limit reached. Existing memories are retained. Contact your group admin.",
            )
        row.storage_bytes = size
