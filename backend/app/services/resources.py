"""Process-wide media admission and transactionally serialized storage reservations."""

from functools import lru_cache
from threading import BoundedSemaphore
from typing import Any, cast
from uuid import UUID

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import require
from app.models.entities import Upload


@lru_cache(maxsize=8)
def media_gate(capacity: int) -> BoundedSemaphore:
    return BoundedSemaphore(capacity)


def reserve_storage(
    factory: sessionmaker[Session],
    config: Settings,
    upload_id: UUID,
    lease: UUID,
    size: int,
    thumbnail_key: str | None = None,
    *,
    backfill: bool = False,
) -> None:
    with factory.begin() as db:
        # All writers serialize the aggregate check; never hold this across S3 IO.
        db.execute(text("SELECT pg_advisory_xact_lock(270003)"))
        row = db.get(Upload, upload_id, with_for_update=True)
        require(
            row is not None
            and row.lease == lease
            and row.state == ("accepted" if backfill else "processing"),
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
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    Upload.storage_bytes > 0,
                                    case((Upload.thumbnail_key.is_not(None), 2), else_=1),
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                ).where(Upload.object_key.is_not(None))
            ).one()
            used = int(cast(Any, used) or 0)
            objects = int(cast(Any, objects) or 0)
            require(
                not config.storage_quota_bytes
                or used - (row.storage_bytes or 0) + size <= config.storage_quota_bytes,
                409,
                "storage_quota_exceeded",
                "Storage is full. No new memory was saved; existing memories are retained. Contact your group admin.",
            )
            require(
                not config.storage_object_quota
                or objects
                - ((2 if row.thumbnail_key else 1) if row.storage_bytes else 0)
                + (2 if thumbnail_key else 1)
                <= config.storage_object_quota,
                409,
                "storage_quota_exceeded",
                "Storage object limit reached. Existing memories are retained. Contact your group admin.",
            )
        row.storage_bytes = size
        row.thumbnail_key = thumbnail_key
