import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Kind = Literal["photo", "video"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DevLogin(Input):
    subject: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,80}$")]
    display_name: Name


class ProfileEdit(Input):
    display_name: Name


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    display_name: str


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
    expires_at: datetime


class GroupOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str


class GroupCreate(Input):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if any(unicodedata.category(char).startswith("C") for char in value):
            raise ValueError("Group name cannot contain control characters")
        normalized = " ".join(unicodedata.normalize("NFC", value).split())
        if not normalized or len(normalized) > 100:
            raise ValueError("Group name must contain 1–100 characters")
        return normalized


class InviteIn(Input):
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class InviteOut(BaseModel):
    id: uuid.UUID
    token: str
    expires_at: datetime
    max_uses: int


class JoinIn(Input):
    token: str = Field(min_length=20, max_length=200)


class CaptureIn(Input):
    kind: Kind


class CaptureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    expires_at: datetime


class PostOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    group_id: uuid.UUID
    kind: str
    source: str
    points: int
    accepted_at: datetime
    removed: bool
    caption: str | None = Field(default=None, max_length=280)
    title: str | None = None
    pinned: bool = False
    author_name: str | None = None
    like_count: int = 0
    liked: bool = False
    comment_count: int = 0
    media_width: int | None = None
    media_height: int | None = None
    album: list[uuid.UUID] = Field(default_factory=list)


class CommentIn(Input):
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not 1 <= len(value) <= 500 or any(
            unicodedata.category(ch) in {"Cs", "Cc"} and ch not in "\n\t" for ch in value
        ):
            raise ValueError("Comment must contain 1–500 plain text characters")
        return value


class CommentOut(BaseModel):
    id: uuid.UUID
    author: UserOut
    text: str | None
    created_at: datetime
    removed: bool


class CommentsOut(BaseModel):
    items: list[CommentOut]
    next_cursor: str | None


class EngagementOut(BaseModel):
    liked: bool
    like_count: int
    comment_count: int


class PinIn(Input):
    pinned: bool


class TourOut(BaseModel):
    version: int
    completed: bool


class FeedOut(BaseModel):
    items: list[PostOut]
    next_cursor: str | None
    server_time: datetime
    pinned: PostOut | None = None


class StreakOut(BaseModel):
    current: int
    longest: int
    grace_used_this_week: bool


class ProfileOut(BaseModel):
    user: UserOut
    streak: StreakOut


class RankOut(BaseModel):
    user: UserOut
    rank: int
    points: int
    capture_photos: int
    capture_videos: int
    gallery_photos: int
    gallery_videos: int
    streak: StreakOut


class LeaderboardOut(BaseModel):
    items: list[RankOut]
    total: int
    offset: int
    limit: int
    period_start: datetime | None
    period_end: datetime | None
    server_time: datetime


class MediaOut(BaseModel):
    url: str
    expires_at: datetime
    width: int | None = None
    height: int | None = None


class Ok(BaseModel):
    ok: bool = True


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorOut(BaseModel):
    error: ErrorDetail
