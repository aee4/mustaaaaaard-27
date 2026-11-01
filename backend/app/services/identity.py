import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import require
from app.models.entities import Audit, Group, Invite, LoginSession, Membership, RateBucket, User

INITIAL_GROUP_NAME = "Mustaaaaaard ’27"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def rate_limit(factory: sessionmaker[Session], key: str, limit: int, now: datetime) -> None:
    window = int(now.timestamp()) // 60
    stmt = insert(RateBucket).values(key=digest(key), window=window, hits=1)
    returning = stmt.on_conflict_do_update(
        index_elements=[RateBucket.key, RateBucket.window], set_={"hits": RateBucket.hits + 1}
    ).returning(RateBucket.hits)
    with factory.begin() as db:
        hits = db.scalar(returning)
    require(hits is not None and hits <= limit, 429, "rate_limited", "Try again next minute")


def member(
    db: Session, group_id: uuid.UUID, user_id: uuid.UUID, *, admin: bool = False, lock: bool = False
) -> Membership:
    stmt = select(Membership).where(Membership.group_id == group_id, Membership.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalar(stmt)
    require(
        row is not None and row.removed_at is None,
        403,
        "membership_required",
        "Active group membership required",
    )
    assert row is not None
    require(not admin or row.role == "admin", 403, "admin_required", "Group admin required")
    return row


def audit(
    db: Session, group: uuid.UUID, actor: uuid.UUID, action: str, target: str, now: datetime
) -> None:
    db.add(Audit(group_id=group, actor_id=actor, action=action, target=target, created_at=now))


def login(
    factory: sessionmaker[Session], subject: str, display_name: str, now: datetime, lifetime: int
) -> tuple[User, LoginSession, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with factory.begin() as db:
        stmt = (
            insert(User)
            .values(subject=subject, display_name=display_name[:80] or "Friend", created_at=now)
            .on_conflict_do_nothing(index_elements=[User.subject])
        )
        db.execute(stmt)
        user = db.scalar(select(User).where(User.subject == subject))
        assert user is not None
        session = LoginSession(
            token_hash=digest(token),
            user_id=user.id,
            csrf=csrf,
            expires_at=now + timedelta(seconds=lifetime),
        )
        db.add(session)
    return user, session, token


def create_invite(
    db: Session, group: uuid.UUID, user: uuid.UUID, now: datetime, uses: int, hours: int
) -> tuple[Invite, str]:
    member(db, group, user, admin=True, lock=True)
    token = secrets.token_urlsafe(32)
    row = Invite(
        group_id=group,
        token_hash=digest(token),
        max_uses=uses,
        expires_at=now + timedelta(hours=hours),
    )
    db.add(row)
    db.flush()
    audit(db, group, user, "invite.created", str(row.id), now)
    return row, token


def create_group(db: Session, name: str, creator: uuid.UUID, now: datetime) -> Group:
    # Only operator bootstrap can create the named initial group. Creating a
    # different group never grants access to any preexisting group.
    reserved = name.replace("'", "’").casefold()
    require(
        reserved != INITIAL_GROUP_NAME.casefold(),
        409,
        "group_name_reserved",
        "This group name is reserved for operator bootstrap",
    )
    group = db.scalar(
        insert(Group)
        .values(name=name)
        .on_conflict_do_nothing(index_elements=[Group.name])
        .returning(Group)
    )
    require(group is not None, 409, "group_name_unavailable", "That group name is unavailable")
    assert group is not None
    db.add(Membership(group_id=group.id, user_id=creator, role="admin"))
    audit(db, group.id, creator, "group.created", str(group.id), now)
    db.flush()
    return group


def join(db: Session, token: str, user: uuid.UUID, now: datetime) -> Group:
    inv = db.scalar(select(Invite).where(Invite.token_hash == digest(token)).with_for_update())
    require(inv is not None, 404, "invalid_invite", "Invite is invalid or unavailable")
    assert inv is not None
    require(
        inv.revoked_at is None and inv.expires_at > now and inv.uses < inv.max_uses,
        409,
        "invalid_invite",
        "Invite is expired, revoked or exhausted",
    )
    inserted = db.scalar(
        insert(Membership)
        .values(group_id=inv.group_id, user_id=user, role="member")
        .on_conflict_do_nothing(index_elements=[Membership.group_id, Membership.user_id])
        .returning(Membership.user_id)
    )
    row = db.get(Membership, (inv.group_id, user), with_for_update=True)
    assert row is not None
    if inserted is not None or row.removed_at is not None:
        row.removed_at = None
        row.role = "member"
        inv.uses += 1
        audit(db, inv.group_id, user, "membership.joined", str(user), now)
    group = db.get(Group, inv.group_id)
    assert group is not None
    return group


def bootstrap(db: Session, subject: str, display_name: str, now: datetime) -> tuple[User, Group]:
    # Explicit operator action; never invoked by login.
    db.execute(
        insert(User)
        .values(subject=subject, display_name=display_name, created_at=now)
        .on_conflict_do_nothing(index_elements=[User.subject])
    )
    db.execute(
        insert(Group)
        .values(name=INITIAL_GROUP_NAME)
        .on_conflict_do_nothing(index_elements=[Group.name])
    )
    user = db.scalar(select(User).where(User.subject == subject))
    group = db.scalar(select(Group).where(Group.name == INITIAL_GROUP_NAME))
    assert user is not None and group is not None
    stmt = insert(Membership).values(group_id=group.id, user_id=user.id, role="admin")
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=[Membership.group_id, Membership.user_id],
            set_={"role": "admin", "removed_at": None},
        )
    )
    audit(db, group.id, user.id, "admin.bootstrapped", str(user.id), now)
    return user, group
