import uuid
from datetime import datetime
from typing import Literal

from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.clock import week_bounds
from app.core.errors import Problem, require
from app.models.entities import Membership, Post, User
from app.schemas.api import FeedOut, LeaderboardOut, RankOut, UserOut
from app.services.identity import audit, member
from app.services.streaks import calculate
from app.services.uploads import representation


def feed(
    db: Session,
    group: uuid.UUID,
    user: uuid.UUID,
    now: datetime,
    limit: int,
    cursor: str | None,
    secret: str,
) -> FeedOut:
    member(db, group, user)
    stmt = select(Post).where(Post.group_id == group, Post.removed_at.is_(None))
    signer = URLSafeSerializer(secret, salt="feed")
    if cursor:
        try:
            data = signer.loads(cursor)
            require(
                data["group"] == str(group),
                422,
                "invalid_cursor",
                "Cursor belongs to a different group",
            )
            at, uid = datetime.fromisoformat(data["at"]), uuid.UUID(data["id"])
            stmt = stmt.where(
                or_(Post.accepted_at < at, and_(Post.accepted_at == at, Post.id < uid))
            )
        except (BadSignature, ValueError, KeyError, TypeError) as exc:
            raise Problem(422, "invalid_cursor", "Invalid feed cursor") from exc
    rows = db.scalars(stmt.order_by(Post.accepted_at.desc(), Post.id.desc()).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = signer.dumps(
            {"group": str(group), "at": last.accepted_at.isoformat(), "id": str(last.id)}
        )
    return FeedOut(
        items=[representation(p) for p in rows[:limit]], next_cursor=next_cursor, server_time=now
    )


def leaderboard(
    db: Session,
    group: uuid.UUID,
    actor: uuid.UUID,
    period: Literal["weekly", "all"],
    now: datetime,
    offset: int,
    limit: int,
) -> LeaderboardOut:
    member(db, group, actor)
    # Lock all membership rows in UUID order so simultaneous leaderboard/profile/removal
    # recalculations cannot race grace inserts or deadlock on differing member order.
    db.scalars(
        select(Membership)
        .where(Membership.group_id == group, Membership.removed_at.is_(None))
        .order_by(Membership.user_id)
        .with_for_update()
    ).all()
    start, end = week_bounds(now)
    filters = [Post.group_id == group, Post.removed_at.is_(None)]
    if period == "weekly":
        filters += [Post.accepted_at >= start, Post.accepted_at < end]
    scores = select(
        Post.user_id.label("user_id"),
        func.sum(case((Post.source == "gallery", 0), (Post.kind == "photo", 1), else_=3)).label(
            "points"
        ),
        *[
            func.sum(case((and_(Post.source == source, Post.kind == kind), 1), else_=0)).label(
                label
            )
            for source, kind, label in [
                ("capture", "photo", "cp"),
                ("capture", "video", "cv"),
                ("gallery", "photo", "gp"),
                ("gallery", "video", "gv"),
            ]
        ],
    )
    aggregate = scores.where(*filters).group_by(Post.user_id).subquery()
    points = func.coalesce(aggregate.c.points, 0)
    stmt = (
        select(
            User,
            points.label("points"),
            func.rank().over(order_by=points.desc()).label("rank"),
            *[func.coalesce(aggregate.c[c], 0) for c in ("cp", "cv", "gp", "gv")],
        )
        .join(Membership, Membership.user_id == User.id)
        .outerjoin(aggregate, aggregate.c.user_id == User.id)
        .where(Membership.group_id == group, Membership.removed_at.is_(None))
        .order_by(points.desc(), User.display_name, User.id)
    )
    rows = db.execute(stmt.offset(offset).limit(limit)).all()
    total = (
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.group_id == group, Membership.removed_at.is_(None))
        )
        or 0
    )
    items = [
        RankOut(
            user=UserOut.model_validate(r[0]),
            points=r[1],
            rank=r[2],
            capture_photos=r[3],
            capture_videos=r[4],
            gallery_photos=r[5],
            gallery_videos=r[6],
            streak=calculate(db, group, r[0].id, now),
        )
        for r in rows
    ]
    return LeaderboardOut(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
        period_start=start if period == "weekly" else None,
        period_end=end if period == "weekly" else None,
        server_time=now,
    )


def remove_post(
    db: Session, group: uuid.UUID, actor: uuid.UUID, post_id: uuid.UUID, now: datetime
) -> None:
    # Use uniform membership lock order for multi-user operations.
    db.scalars(
        select(Membership)
        .where(Membership.group_id == group)
        .order_by(Membership.user_id)
        .with_for_update()
    ).all()
    membership = member(db, group, actor)
    post = db.get(Post, post_id, with_for_update=True)
    require(post is not None and post.group_id == group, 404, "post_not_found", "Post not found")
    assert post is not None
    require(
        post.user_id == actor or membership.role == "admin",
        403,
        "post_forbidden",
        "Only owner or admin may remove post",
    )
    if post.removed_at is None:
        # Record elapsed grace before deletion; never erase or move history.
        target = db.get(Membership, (group, post.user_id))
        if target and target.removed_at is None:
            calculate(db, group, post.user_id, now)
        post.removed_at = now
        post.caption = None
        db.flush()
        audit(db, group, actor, "post.removed", str(post.id), now)
        if target and target.removed_at is None:
            calculate(db, group, post.user_id, now)
