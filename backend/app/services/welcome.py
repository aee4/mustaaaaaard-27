"""Explicit, resumable operator import into the named initial group only."""

import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock, activity_date
from app.core.config import Settings
from app.core.errors import require
from app.integrations.storage import Storage
from app.models.entities import Group, Post, Upload
from app.services.identity import INITIAL_GROUP_NAME, member
from app.services.media import copy_bounded, sanitize
from app.services.resources import reserve_storage


def seed_welcome(
    factory: sessionmaker[Session],
    storage: Storage,
    config: Settings,
    clock: Clock,
    group_id: uuid.UUID,
    operator: uuid.UUID,
    photos: list[Path],
) -> uuid.UUID:
    require(
        1 <= len(photos) <= 20,
        422,
        "invalid_album",
        "Provide a cover and at most 19 additional photos",
    )
    # Session advisory lock, committed before media IO: no open DB transaction across IO.
    with factory() as session:
        engine = session.get_bind()
    assert isinstance(engine, Engine)
    with engine.connect() as guard:
        lock_id = int.from_bytes(group_id.bytes[:8], "big", signed=True)
        guard.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
        guard.commit()
        try:
            with factory.begin() as db:
                group = db.get(Group, group_id)
                require(
                    group is not None and group.name == INITIAL_GROUP_NAME,
                    422,
                    "wrong_group",
                    "Only the explicit initial Mustaaaaaard group may receive this album",
                )
                member(db, group_id, operator, admin=True)
                existing = db.scalar(
                    select(Post).where(Post.group_id == group_id, Post.seed_key == "welcome-v1")
                )
                if existing and existing.removed_at is not None:
                    return existing.id  # Never resurrect removed welcome content.
            parent = None
            for index, path in enumerate(photos):
                seed_key = "welcome-v1" if index == 0 else f"welcome-v1-photo-{index}"
                with factory.begin() as db:
                    existing = db.scalar(
                        select(Post).where(Post.group_id == group_id, Post.seed_key == seed_key)
                    )
                    if existing:
                        if index == 0:
                            parent = existing.id
                        continue
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    source = directory / "original"
                    with path.open("rb") as input_file:
                        fingerprint = copy_bounded(input_file, source, config.image_max_bytes)
                    clean, content_type = sanitize(source, directory, "photo", config)
                    now, lease = clock.now(), uuid.uuid4()
                    with factory.begin() as db:
                        member(db, group_id, operator, admin=True, lock=True)
                        row = db.scalar(
                            select(Upload)
                            .where(
                                Upload.group_id == group_id,
                                Upload.operation == "welcome-v1",
                                Upload.idempotency_key == seed_key,
                            )
                            .with_for_update()
                        )
                        if row is None:
                            row = Upload(
                                user_id=operator,
                                group_id=group_id,
                                operation="welcome-v1",
                                idempotency_key=seed_key,
                                fingerprint=fingerprint,
                                kind="photo",
                                state="processing",
                                created_at=now,
                                lease=lease,
                                lease_until=now + timedelta(seconds=config.lease_seconds),
                                object_key=f"media/{uuid.uuid4()}.png",
                                storage_bytes=0,
                            )
                            db.add(row)
                        else:
                            require(
                                row.fingerprint == fingerprint,
                                409,
                                "welcome_changed",
                                "Keep the same ordered album when resuming this import",
                            )
                            row.state, row.lease = "processing", lease
                            if row.object_key is None:
                                row.object_key = f"media/{uuid.uuid4()}.png"
                                row.storage_bytes = 0
                            row.lease_until = now + timedelta(seconds=config.lease_seconds)
                        db.flush()
                        upload_id, key = row.id, row.object_key
                    assert key is not None
                    reserve_storage(factory, config, upload_id, lease, clean.stat().st_size)
                    storage.put(key, clean, content_type)
                    with factory.begin() as db:
                        member(db, group_id, operator, admin=True, lock=True)
                        row = db.get(Upload, upload_id, with_for_update=True)
                        require(
                            row is not None and row.lease == lease and row.state == "processing",
                            409,
                            "upload_lease_lost",
                            "Retry import",
                        )
                        assert row is not None
                        post = Post(
                            upload_id=upload_id,
                            group_id=group_id,
                            user_id=None,
                            parent_id=parent,
                            fingerprint=fingerprint,
                            caption="Our people. Our everyday moments." if index == 0 else None,
                            title="The Final Season 💛" if index == 0 else None,
                            seed_key=seed_key,
                            pinned=index == 0,
                            kind="photo",
                            source="system",
                            content_type=content_type,
                            accepted_at=now,
                            activity_date=activity_date(now),
                        )
                        db.add(post)
                        row.state = "accepted"
                        db.flush()
                        if index == 0:
                            parent = post.id
            assert parent is not None
            return parent
        finally:
            guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
            guard.commit()
