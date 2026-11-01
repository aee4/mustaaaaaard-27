import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import activity_date, week_start
from app.models.entities import Grace, Post
from app.schemas.api import StreakOut
from app.services.identity import member


def replay(
    active: set[date], today: date, reservations: dict[date, date]
) -> tuple[StreakOut, dict[date, date]]:
    """Existing week->day reservations are immutable, even if that day becomes active."""
    grace = dict(reservations)
    current = longest = 0
    if active:
        day = min(active)
        while day <= today:
            if day in active:
                current += 1
                longest = max(longest, current)
            elif day < today and current:
                week = week_start(day)
                if week not in grace:
                    grace[week] = day
                elif grace[week] != day:
                    current = 0
            day += timedelta(days=1)
    return StreakOut(
        current=current, longest=longest, grace_used_this_week=week_start(today) in grace
    ), grace


def calculate(db: Session, group_id: uuid.UUID, user_id: uuid.UUID, now: datetime) -> StreakOut:
    member(db, group_id, user_id, lock=True)
    active = set(
        db.scalars(
            select(Post.activity_date).where(
                Post.group_id == group_id,
                Post.user_id == user_id,
                Post.source == "capture",
                Post.removed_at.is_(None),
            )
        ).all()
    )
    rows = db.scalars(
        select(Grace).where(Grace.group_id == group_id, Grace.user_id == user_id)
    ).all()
    existing = {r.week: r.day for r in rows}
    result, consumed = replay(active, activity_date(now), existing)
    for week, day in consumed.items():
        if week not in existing:
            db.add(Grace(group_id=group_id, user_id=user_id, week=week, day=day))
    db.flush()
    return result
