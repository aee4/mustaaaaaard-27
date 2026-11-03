"""Operator backfill for legacy private photos. No original is rewritten."""

import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.integrations.storage import S3Storage
from app.models.entities import Post, Upload
from app.services.media import photo_thumbnail
from app.services.resources import media_gate, reserve_storage


def backfill(factory: sessionmaker[Session], storage: S3Storage, config: Settings) -> int:
    with factory.begin() as db:
        ids = list(
            db.scalars(
                select(Upload.id)
                .join(Post)
                .where(
                    Upload.state == "accepted",
                    Upload.kind == "photo",
                    Upload.object_key.is_not(None),
                    Upload.thumbnail_ready.is_(False),
                    Post.removed_at.is_(None),
                )
            )
        )
    count = 0
    for upload_id in ids:
        with (
            media_gate(config.media_concurrency),
            tempfile.TemporaryDirectory(prefix="mustard-thumb-") as tmp,
        ):
            directory = Path(tmp)
            with factory.begin() as db:
                row = db.get(Upload, upload_id)
                if not row or row.state != "accepted" or not row.object_key or row.thumbnail_ready:
                    continue
                key, lease = row.object_key, row.lease
            source = directory / "original.png"
            # Sanitized originals are bounded by the existing pixel policy.
            storage.client.download_file(storage.bucket, key, str(source))
            thumbnail, width, height = photo_thumbnail(source, directory)
            thumbnail_key = key + "-thumb.webp"
            reserve_storage(
                factory,
                config,
                upload_id,
                lease,
                source.stat().st_size + thumbnail.stat().st_size,
                thumbnail_key,
                backfill=True,
            )
            # Reservation precedes IO; failure retains tracked cleanup debt and can resume.
            storage.put(thumbnail_key, thumbnail, "image/webp")
            with factory.begin() as db:
                row = db.get(Upload, upload_id, with_for_update=True)
                post = db.scalar(select(Post).where(Post.upload_id == upload_id))
                if (
                    row
                    and post
                    and row.state == "accepted"
                    and row.object_key == key
                    and row.thumbnail_key == thumbnail_key
                    and post.removed_at is None
                ):
                    row.thumbnail_ready = True
                    post.media_width, post.media_height = width, height
                    count += 1
    return count
