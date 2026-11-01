import tempfile
import unicodedata
import uuid
from datetime import timedelta
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock, activity_date
from app.core.config import Settings
from app.core.errors import Problem, require
from app.integrations.storage import Storage
from app.models.entities import Capture, Post, Upload
from app.schemas.api import PostOut
from app.services.identity import digest, member
from app.services.media import copy_bounded, sanitize
from app.services.resources import media_gate, reserve_storage


def representation(post: Post) -> PostOut:
    points = (
        (1 if post.kind == "photo" else 3)
        if post.source == "capture" and post.removed_at is None
        else 0
    )
    return PostOut(
        id=post.id,
        user_id=post.user_id,
        group_id=post.group_id,
        kind=post.kind,
        source=post.source,
        points=points,
        accepted_at=post.accepted_at,
        removed=post.removed_at is not None,
        caption=post.caption if post.removed_at is None else None,
    )


def normalize_caption(value: str | None) -> str | None:
    if value is None:
        return None
    # Browser multipart encoders serialize textarea line endings as CRLF.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    require(
        len(value) <= 280
        and all(unicodedata.category(ch) not in {"Cs", "Cc"} or ch in "\n\t" for ch in value),
        422,
        "invalid_caption",
        "Caption must be at most 280 characters of plain text",
    )
    return value.strip() or None


def check_capture(
    db: Session, capture_id: uuid.UUID, user: uuid.UUID, group: uuid.UUID, kind: str, clock: Clock
) -> Capture:
    capture = db.get(Capture, capture_id, with_for_update=True)
    require(
        capture is not None and capture.user_id == user and capture.group_id == group,
        404,
        "capture_not_found",
        "Capture session not found",
    )
    assert capture is not None
    require(capture.kind == kind, 409, "capture_kind_mismatch", "Capture media kind differs")
    require(capture.consumed_at is None, 409, "capture_consumed", "Capture session already used")
    require(capture.expires_at > clock.now(), 409, "capture_expired", "Capture session expired")
    return capture


class UploadService:
    def __init__(
        self, factory: sessionmaker[Session], storage: Storage, clock: Clock, config: Settings
    ):
        self.factory, self.storage, self.clock, self.config = factory, storage, clock, config

    def accept(
        self,
        user: uuid.UUID,
        group: uuid.UUID,
        kind: str,
        capture_id: uuid.UUID | None,
        key: str,
        body: BinaryIO,
        caption: str | None = None,
    ) -> PostOut:
        from pathlib import Path

        # Authorization precedes expensive work; repeat under lock during finalization.
        with self.factory.begin() as db:
            member(db, group, user)
        caption = normalize_caption(caption)
        with tempfile.TemporaryDirectory(prefix="mustard-") as tmp:
            directory = Path(tmp)
            original = directory / "original"
            limit = self.config.image_max_bytes if kind == "photo" else self.config.video_max_bytes
            fingerprint = copy_bounded(body, original, limit)
            operation = f"{group}:{capture_id or 'gallery'}"
            upload_id, lease, object_key, replay = self.claim(
                user,
                group,
                kind,
                capture_id,
                key,
                fingerprint,
                operation,
                digest(caption) if caption is not None else None,
            )
            if replay is not None:
                return replay
            assert object_key is not None
            gate = media_gate(self.config.media_concurrency)
            acquired = gate.acquire(blocking=False)
            try:
                require(
                    acquired,
                    503,
                    "media_busy",
                    "Another upload is processing. Retry this same upload shortly.",
                )
                clean, content_type = sanitize(original, directory, kind, self.config)
                reserve_storage(self.factory, self.config, upload_id, lease, clean.stat().st_size)
                self.storage.put(object_key, clean, content_type)
                with self.factory.begin() as db:
                    member(db, group, user, lock=True)
                    row = db.get(Upload, upload_id, with_for_update=True)
                    require(
                        row is not None
                        and row.lease == lease
                        and row.state == "processing"
                        and row.lease_until > self.clock.now(),
                        409,
                        "upload_lease_lost",
                        "Retry upload after cleanup",
                    )
                    assert row is not None
                    capture = (
                        check_capture(db, capture_id, user, group, kind, self.clock)
                        if capture_id
                        else None
                    )
                    now = self.clock.now()
                    # Read authoritative time after acquiring both locks.
                    require(
                        capture is None or capture.expires_at > now,
                        409,
                        "capture_expired",
                        "Capture session expired",
                    )
                    if capture:
                        capture.consumed_at = now
                    post = Post(
                        upload_id=upload_id,
                        user_id=user,
                        group_id=group,
                        capture_id=capture_id,
                        kind=kind,
                        source="capture" if capture else "gallery",
                        content_type=content_type,
                        fingerprint=fingerprint,
                        accepted_at=now,
                        activity_date=activity_date(now),
                        caption=caption,
                    )
                    db.add(post)
                    row.state = "accepted"
                    db.flush()
                    result = representation(post)
                return result
            except Exception as exc:
                self.fail(upload_id, lease, object_key)
                if isinstance(exc, IntegrityError):
                    raise Problem(
                        409,
                        "duplicate_media",
                        "These original bytes were already accepted in this group",
                    ) from exc
                if isinstance(exc, Problem):
                    raise
                raise Problem(
                    503, "upload_unavailable", "Upload failed; retry the same key and input"
                ) from exc
            finally:
                if acquired:
                    gate.release()

    def claim(
        self,
        user: uuid.UUID,
        group: uuid.UUID,
        kind: str,
        capture_id: uuid.UUID | None,
        key: str,
        fingerprint: str,
        operation: str,
        caption_hash: str | None = None,
    ) -> tuple[uuid.UUID, uuid.UUID, str | None, PostOut | None]:
        now = self.clock.now()
        with self.factory.begin() as db:
            member(db, group, user, lock=True)
            stmt = insert(Upload).values(
                user_id=user,
                group_id=group,
                kind=kind,
                capture_id=capture_id,
                operation=operation,
                idempotency_key=key,
                fingerprint=fingerprint,
                caption_hash=caption_hash,
                state="failed",
                lease_until=now,
                created_at=now,
            )
            db.execute(stmt.on_conflict_do_nothing(constraint="uq_upload_idempotency"))
            row = db.scalar(
                select(Upload)
                .where(
                    Upload.user_id == user,
                    Upload.operation == operation,
                    Upload.idempotency_key == key,
                )
                .with_for_update()
            )
            assert row is not None
            require(
                row.fingerprint == fingerprint
                and row.kind == kind
                and row.caption_hash == caption_hash,
                409,
                "idempotency_conflict",
                "Key was used with different input",
            )
            if row.state in {"accepted", "cleaning"}:
                post = db.scalar(select(Post).where(Post.upload_id == row.id))
                if post is not None:
                    return row.id, row.lease, row.object_key, representation(post)
            require(
                row.state == "failed" and row.object_key is None,
                409,
                "upload_in_progress" if row.lease_until > now else "cleanup_pending",
                "Upload is processing or awaiting cleanup; retry with backoff",
            )
            if capture_id:
                check_capture(db, capture_id, user, group, kind, self.clock)
            require(
                db.scalar(
                    select(Post.id).where(Post.group_id == group, Post.fingerprint == fingerprint)
                )
                is None,
                409,
                "duplicate_media",
                "These original bytes were already accepted in this group",
            )
            row.state, row.lease = "processing", uuid.uuid4()
            row.lease_until = now + timedelta(seconds=self.config.lease_seconds)
            row.object_key = f"media/{uuid.uuid4().hex}"
            row.storage_bytes = 0
            return row.id, row.lease, row.object_key, None

    def fail(self, upload_id: uuid.UUID, lease: uuid.UUID, key: str) -> None:
        # Resolve ambiguous commit before deleting: accepted rows must keep their media.
        try:
            with self.factory.begin() as db:
                row = db.get(Upload, upload_id, with_for_update=True)
                if row is None or row.lease != lease or row.state != "processing":
                    return
                row.state = "failed"
                row.lease_until = self.clock.now()
            deleted = False
            try:
                self.storage.delete(key)
                deleted = True
            except Exception:
                pass  # Tracked key remains cleanup debt.
            if deleted:
                with self.factory.begin() as db:
                    row = db.get(Upload, upload_id, with_for_update=True)
                    if row and row.lease == lease and row.state == "failed":
                        row.object_key = None
                        row.storage_bytes = 0
        except Exception:
            # Database unavailable: reserved key and lease allow later recovery.
            return

    def cleanup(self, limit: int = 100) -> int:
        from sqlalchemy import and_, or_

        cleaned = 0
        # Claim one at a time; no transaction across delete IO.
        for _ in range(limit):
            now = self.clock.now()
            with self.factory.begin() as db:
                row = db.scalar(
                    select(Upload)
                    .outerjoin(Post, Post.upload_id == Upload.id)
                    .where(
                        Upload.object_key.is_not(None),
                        or_(
                            and_(
                                Upload.state.in_(["processing", "failed", "cleaning"]),
                                Upload.lease_until < now,
                            ),
                            and_(Upload.state == "accepted", Post.removed_at.is_not(None)),
                        ),
                    )
                    .order_by(Upload.created_at)
                    .with_for_update(of=Upload, skip_locked=True)
                    .limit(1)
                )
                if row is None:
                    break
                row.state, row.lease = "cleaning", uuid.uuid4()
                row.lease_until = now + timedelta(seconds=self.config.lease_seconds)
                upload_id, lease, key = row.id, row.lease, row.object_key
            assert key is not None
            try:
                self.storage.delete(key)
            except Exception:
                continue  # Lease expires and another cleanup can retry.
            with self.factory.begin() as db:
                row = db.get(Upload, upload_id, with_for_update=True)
                if row and row.lease == lease and row.state == "cleaning":
                    row.object_key = None
                    row.storage_bytes = 0
                    post = db.scalar(select(Post.id).where(Post.upload_id == row.id))
                    row.state = "accepted" if post else "failed"
                    cleaned += 1
        # A paused stale worker can finish its storage write after an earlier
        # cleanup deleted the reserved key. Reconcile old unreferenced keys too.
        # Keys are reserved before IO, random, and never reused.
        for key in self.storage.old_keys(self.clock.now() - timedelta(minutes=15)):
            if cleaned >= limit:
                break
            with self.factory.begin() as db:
                referenced = db.scalar(select(Upload.id).where(Upload.object_key == key))
            if referenced is None:
                try:
                    self.storage.delete(key)
                    cleaned += 1
                except Exception:
                    continue
        return cleaned
