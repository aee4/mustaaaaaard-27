"""Membership-scoped interactions. Call inside the caller's transaction."""

import uuid
from datetime import datetime

from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import Problem, require
from app.models.entities import Comment, Post, PostLike, User
from app.schemas.api import CommentOut, CommentsOut, EngagementOut, UserOut
from app.services.identity import audit, digest, member


def accessible(
    db: Session, group: uuid.UUID, actor: uuid.UUID, post_id: uuid.UUID, *, lock: bool = False
) -> Post:
    member(db, group, actor, lock=lock)
    post = db.get(Post, post_id, with_for_update=lock)
    require(
        post is not None
        and post.group_id == group
        and post.removed_at is None
        and post.parent_id is None,
        404,
        "post_not_found",
        "Post not found",
    )
    assert post is not None
    return post


def counts(db: Session, post: uuid.UUID, actor: uuid.UUID) -> EngagementOut:
    return EngagementOut(
        liked=db.get(PostLike, (post, actor)) is not None,
        like_count=db.scalar(
            select(func.count()).select_from(PostLike).where(PostLike.post_id == post)
        )
        or 0,
        comment_count=db.scalar(
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post, Comment.removed_at.is_(None))
        )
        or 0,
    )


def set_like(
    db: Session, group: uuid.UUID, actor: uuid.UUID, post_id: uuid.UUID, now: datetime, liked: bool
) -> EngagementOut:
    accessible(db, group, actor, post_id, lock=True)
    if liked:
        db.execute(
            insert(PostLike)
            .values(post_id=post_id, user_id=actor, created_at=now)
            .on_conflict_do_nothing()
        )
    else:
        db.execute(delete(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == actor))
    return counts(db, post_id, actor)


def comment_out(db: Session, row: Comment) -> CommentOut:
    author = db.get(User, row.user_id)
    assert author is not None
    return CommentOut(
        id=row.id,
        author=UserOut.model_validate(author),
        text=row.text,
        created_at=row.created_at,
        removed=row.removed_at is not None,
    )


def add_comment(
    db: Session,
    group: uuid.UUID,
    actor: uuid.UUID,
    post_id: uuid.UUID,
    text: str,
    key: str,
    now: datetime,
) -> CommentOut:
    accessible(db, group, actor, post_id, lock=True)
    fingerprint = digest(text)
    row = db.scalar(
        select(Comment).where(
            Comment.post_id == post_id, Comment.user_id == actor, Comment.idempotency_key == key
        )
    )
    if row:
        require(
            row.text_hash == fingerprint,
            409,
            "idempotency_conflict",
            "This retry key belongs to a different comment",
        )
        return comment_out(db, row)
    row = Comment(
        post_id=post_id,
        user_id=actor,
        text=text,
        text_hash=fingerprint,
        idempotency_key=key,
        created_at=now,
    )
    db.add(row)
    db.flush()
    return comment_out(db, row)


def comments(
    db: Session,
    group: uuid.UUID,
    actor: uuid.UUID,
    post_id: uuid.UUID,
    limit: int,
    cursor: str | None,
    secret: str,
) -> CommentsOut:
    accessible(db, group, actor, post_id)
    signer = URLSafeSerializer(secret, salt="comments-v1")
    stmt = select(Comment).where(Comment.post_id == post_id, Comment.removed_at.is_(None))
    if cursor:
        try:
            data = signer.loads(cursor)
            if data["group"] != str(group) or data["post"] != str(post_id):
                raise ValueError()
            at, uid = datetime.fromisoformat(data["at"]), uuid.UUID(data["id"])
            if at.tzinfo is None:
                raise ValueError()
            stmt = stmt.where(
                or_(Comment.created_at < at, and_(Comment.created_at == at, Comment.id < uid))
            )
        except (BadSignature, ValueError, KeyError, TypeError) as exc:
            raise Problem(422, "invalid_cursor", "Invalid comment cursor") from exc
    rows = db.scalars(
        stmt.order_by(Comment.created_at.desc(), Comment.id.desc()).limit(limit + 1)
    ).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = signer.dumps(
            {
                "group": str(group),
                "post": str(post_id),
                "at": last.created_at.isoformat(),
                "id": str(last.id),
            }
        )
    return CommentsOut(
        items=[comment_out(db, row) for row in rows[:limit]], next_cursor=next_cursor
    )


def remove_comment(
    db: Session,
    group: uuid.UUID,
    actor: uuid.UUID,
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    now: datetime,
) -> None:
    accessible(db, group, actor, post_id, lock=True)
    membership = member(db, group, actor)
    row = db.get(Comment, comment_id, with_for_update=True)
    require(
        row is not None and row.post_id == post_id, 404, "comment_not_found", "Comment not found"
    )
    assert row is not None
    require(
        row.user_id == actor or membership.role == "admin",
        403,
        "comment_forbidden",
        "Only the author or group admin may delete this comment",
    )
    if row.removed_at is None:
        row.text, row.removed_at = None, now
        audit(db, group, actor, "comment.removed", str(row.id), now)
