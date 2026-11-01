import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    subject: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class Membership(Base):
    __tablename__ = "memberships"
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(10), default="member")
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("role IN ('admin','member')", name="membership_role"),)


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_uses: Mapped[int] = mapped_column(Integer)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("uses >= 0 AND uses <= max_uses AND max_uses > 0", name="invite_usage"),
    )


class Capture(Base):
    __tablename__ = "captures"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), index=True)
    kind: Mapped[str] = mapped_column(String(5))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("kind IN ('photo','video')", name="capture_kind"),)


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"))
    operation: Mapped[str] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    caption_hash: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(5))
    capture_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("captures.id"))
    state: Mapped[str] = mapped_column(String(12))
    object_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    storage_bytes: Mapped[int | None] = mapped_column(BigInteger)
    lease: Mapped[uuid.UUID] = mapped_column(Uuid, default=new_id)
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("user_id", "operation", "idempotency_key", name="uq_upload_idempotency"),
        CheckConstraint(
            "state IN ('processing','failed','accepted','cleaning')", name="upload_state"
        ),
        CheckConstraint("kind IN ('photo','video')", name="upload_kind"),
        CheckConstraint("storage_bytes >= 0", name="upload_storage_bytes"),
    )


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("uploads.id"), unique=True)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    capture_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("captures.id"), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    caption: Mapped[str | None] = mapped_column(String(280))
    kind: Mapped[str] = mapped_column(String(5))
    source: Mapped[str] = mapped_column(String(7))
    content_type: Mapped[str] = mapped_column(String(40))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activity_date: Mapped[date] = mapped_column(Date)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("group_id", "fingerprint", name="uq_group_fingerprint"),
        CheckConstraint("kind IN ('photo','video')", name="post_kind"),
        CheckConstraint(
            "(source = 'capture' AND capture_id IS NOT NULL) OR (source = 'gallery' AND capture_id IS NULL)",
            name="post_source",
        ),
        Index("ix_posts_feed", "group_id", "accepted_at", "id"),
        Index("ix_posts_activity", "group_id", "user_id", "activity_date"),
    )


class Grace(Base):
    __tablename__ = "graces"
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    week: Mapped[date] = mapped_column(Date, primary_key=True)
    day: Mapped[date] = mapped_column(Date)


class Audit(Base):
    __tablename__ = "audits"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id"), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)
    hits: Mapped[int] = mapped_column(Integer)
