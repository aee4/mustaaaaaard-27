import uuid
from datetime import timedelta
from typing import Annotated, Literal

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Form, Header, Query, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BeforeValidator
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import Identity, check_origin, identity
from app.core.errors import Problem, require
from app.models.entities import (
    Capture,
    Group,
    Invite,
    LoginSession,
    Membership,
    Post,
    TourProgress,
    Upload,
    User,
)
from app.schemas.api import (
    CaptureIn,
    CaptureOut,
    CommentIn,
    CommentOut,
    CommentsOut,
    DevLogin,
    EngagementOut,
    FeedOut,
    GroupCreate,
    GroupOut,
    InviteIn,
    InviteOut,
    JoinIn,
    Kind,
    LeaderboardOut,
    MediaOut,
    Ok,
    PinIn,
    PostOut,
    ProfileEdit,
    ProfileOut,
    SessionOut,
    TourOut,
    UserOut,
)
from app.services import engagement
from app.services import identity as accounts
from app.services.social import feed, leaderboard, remove_post
from app.services.streaks import calculate
from app.services.uploads import UploadService, normalize_caption

router = APIRouter()
Auth = Annotated[Identity, Depends(identity)]
Idempotency = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def uploads(request: Request) -> UploadService:
    return UploadService(
        request.app.state.factory,
        request.app.state.storage,
        request.app.state.clock,
        request.app.state.settings,
    )


def limit(request: Request, key: str, maximum: int) -> None:
    accounts.rate_limit(request.app.state.factory, key, maximum, request.app.state.clock.now())


def session_response(request: Request, response: Response, subject: str, name: str) -> SessionOut:
    config = request.app.state.settings
    user, session, token = accounts.login(
        request.app.state.factory,
        subject,
        name,
        request.app.state.clock.now(),
        config.session_seconds,
    )
    response.set_cookie(
        "mustard_session",
        token,
        max_age=config.session_seconds,
        secure=config.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return SessionOut(
        user=UserOut.model_validate(user), csrf_token=session.csrf, expires_at=session.expires_at
    )


@router.get("/health", response_model=Ok)
def health() -> Ok:
    return Ok()


@router.get("/ready", response_model=Ok)
def ready(request: Request) -> Ok:
    try:
        with request.app.state.factory.begin() as db:
            revision = db.scalar(text("SELECT version_num FROM alembic_version"))
            require(revision == "0004", 503, "not_ready", "Schema migration required")
        request.app.state.storage.ready()
    except Exception as exc:
        raise Problem(503, "not_ready", "Database/schema/storage unavailable") from exc
    return Ok()


@router.post("/auth/dev", response_model=SessionOut)
def dev_login(body: DevLogin, request: Request, response: Response) -> SessionOut:
    config = request.app.state.settings
    require(config.dev_auth and config.environment != "production", 404, "not_found", "Not found")
    check_origin(request)
    limit(request, f"auth:{request.client.host if request.client else 'unknown'}", config.auth_rate)
    return session_response(request, response, f"dev:{body.subject}", body.display_name)


@router.get("/auth/google")
async def google_login(request: Request) -> Response:
    config = request.app.state.settings
    require(
        bool(config.google_client_id), 503, "google_unconfigured", "Google login is not configured"
    )
    await run_in_threadpool(
        limit,
        request,
        f"auth:{request.client.host if request.client else 'unknown'}",
        config.auth_rate,
    )
    oauth: OAuth = request.app.state.oauth
    return await oauth.google.authorize_redirect(request, config.base_url + "/auth/google/callback")  # type: ignore[no-any-return]


@router.get("/auth/google/callback")
async def google_callback(request: Request) -> Response:
    try:
        token = await request.app.state.oauth.google.authorize_access_token(request)
        info = token["userinfo"]  # Authlib validates signed ID token, issuer/aud/exp/nonce.
        subject = str(info["sub"])
        require(bool(subject), 401, "oauth_invalid", "Invalid Google identity")
    except Exception as exc:
        raise Problem(401, "oauth_invalid", "Google authentication failed") from exc
    response = RedirectResponse(request.app.state.settings.base_url + "/", status_code=303)
    await run_in_threadpool(
        session_response, request, response, f"google:{subject}", str(info.get("name", "Friend"))
    )
    # Provider access/refresh/ID tokens are deliberately not persisted.
    return response


@router.get("/auth/session", response_model=SessionOut)
def session_info(auth: Auth, response: Response) -> SessionOut:
    response.headers["Cache-Control"] = "no-store"
    return SessionOut(
        user=UserOut.model_validate(auth.user),
        csrf_token=auth.session.csrf,
        expires_at=auth.session.expires_at,
    )


@router.post("/auth/logout", response_model=Ok)
def logout(request: Request, response: Response, auth: Auth) -> Ok:
    with request.app.state.factory.begin() as db:
        session = db.get(LoginSession, auth.session.token_hash)
        assert session is not None
        session.revoked_at = request.app.state.clock.now()
    response.delete_cookie(
        "mustard_session",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return Ok()


@router.patch("/me", response_model=UserOut)
def edit_profile(body: ProfileEdit, request: Request, auth: Auth) -> UserOut:
    with request.app.state.factory.begin() as db:
        user = db.get(User, auth.user.id, with_for_update=True)
        assert user is not None
        user.display_name = body.display_name
        return UserOut.model_validate(user)


@router.get("/groups", response_model=list[GroupOut])
def groups(request: Request, auth: Auth) -> list[GroupOut]:
    with request.app.state.factory.begin() as db:
        rows = db.execute(
            select(Group, Membership.role)
            .join(Membership, Group.id == Membership.group_id)
            .where(Membership.user_id == auth.user.id, Membership.removed_at.is_(None))
            .order_by(Group.id)
        ).all()
        return [GroupOut(id=g.id, name=g.name, role=role) for g, role in rows]


@router.post("/groups/join", response_model=GroupOut)
def join_group(body: JoinIn, request: Request, auth: Auth) -> GroupOut:
    limit(request, f"invite:{auth.user.id}", request.app.state.settings.invite_rate)
    with request.app.state.factory.begin() as db:
        group = accounts.join(db, body.token, auth.user.id, request.app.state.clock.now())
        membership = accounts.member(db, group.id, auth.user.id)
        return GroupOut(id=group.id, name=group.name, role=membership.role)


@router.post("/groups", response_model=GroupOut, status_code=201)
def create_group(body: GroupCreate, request: Request, auth: Auth) -> GroupOut:
    limit(request, f"group-create:{auth.user.id}", request.app.state.settings.group_rate)
    with request.app.state.factory.begin() as db:
        group = accounts.create_group(db, body.name, auth.user.id, request.app.state.clock.now())
        return GroupOut(id=group.id, name=group.name, role="admin")


@router.post("/groups/{group_id}/invites", response_model=InviteOut, status_code=201)
def invite(group_id: uuid.UUID, body: InviteIn, request: Request, auth: Auth) -> InviteOut:
    limit(request, f"invite:{auth.user.id}", request.app.state.settings.invite_rate)
    with request.app.state.factory.begin() as db:
        row, token = accounts.create_invite(
            db,
            group_id,
            auth.user.id,
            request.app.state.clock.now(),
            body.max_uses,
            body.expires_in_hours,
        )
        return InviteOut(id=row.id, token=token, expires_at=row.expires_at, max_uses=row.max_uses)


@router.delete("/groups/{group_id}/invites/{invite_id}", response_model=Ok)
def revoke_invite(group_id: uuid.UUID, invite_id: uuid.UUID, request: Request, auth: Auth) -> Ok:
    with request.app.state.factory.begin() as db:
        accounts.member(db, group_id, auth.user.id, admin=True)
        row = db.get(Invite, invite_id, with_for_update=True)
        require(
            row is not None and row.group_id == group_id,
            404,
            "invite_not_found",
            "Invite not found",
        )
        assert row is not None
        accounts.member(db, group_id, auth.user.id, admin=True, lock=True)
        row.revoked_at = request.app.state.clock.now()
        accounts.audit(db, group_id, auth.user.id, "invite.revoked", str(invite_id), row.revoked_at)
    return Ok()


@router.delete("/groups/{group_id}/members/{user_id}", response_model=Ok)
def remove_member(group_id: uuid.UUID, user_id: uuid.UUID, request: Request, auth: Auth) -> Ok:
    with request.app.state.factory.begin() as db:
        # Uniform order with leaderboard and moderation paths.
        db.scalars(
            select(Membership)
            .where(Membership.group_id == group_id)
            .order_by(Membership.user_id)
            .with_for_update()
        ).all()
        accounts.member(db, group_id, auth.user.id, admin=True)
        target = accounts.member(db, group_id, user_id)
        require(
            target.role != "admin",
            409,
            "admin_removal_forbidden",
            "Use operator bootstrap to manage admins",
        )
        calculate(db, group_id, user_id, request.app.state.clock.now())
        target.removed_at = request.app.state.clock.now()
        accounts.audit(
            db, group_id, auth.user.id, "membership.removed", str(user_id), target.removed_at
        )
    return Ok()


@router.post("/groups/{group_id}/captures", response_model=CaptureOut, status_code=201)
def capture(group_id: uuid.UUID, body: CaptureIn, request: Request, auth: Auth) -> CaptureOut:
    limit(request, f"upload:{auth.user.id}", request.app.state.settings.upload_rate)
    with request.app.state.factory.begin() as db:
        accounts.member(db, group_id, auth.user.id, lock=True)
        row = Capture(
            user_id=auth.user.id,
            group_id=group_id,
            kind=body.kind,
            expires_at=request.app.state.clock.now()
            + timedelta(seconds=request.app.state.settings.capture_seconds),
        )
        db.add(row)
        db.flush()
        return CaptureOut.model_validate(row)


@router.post("/groups/{group_id}/captures/{capture_id}/upload", response_model=PostOut)
def capture_upload(
    group_id: uuid.UUID,
    capture_id: uuid.UUID,
    kind: Kind,
    file: UploadFile,
    request: Request,
    auth: Auth,
    idempotency_key: Idempotency,
    caption: Annotated[str | None, Form(max_length=280), BeforeValidator(normalize_caption)] = None,
) -> PostOut:
    limit(request, f"upload:{auth.user.id}", request.app.state.settings.upload_rate)
    return uploads(request).accept(
        auth.user.id, group_id, kind, capture_id, idempotency_key, file.file, caption
    )


@router.post("/groups/{group_id}/gallery", response_model=PostOut)
def gallery_upload(
    group_id: uuid.UUID,
    kind: Kind,
    file: UploadFile,
    request: Request,
    auth: Auth,
    idempotency_key: Idempotency,
    caption: Annotated[str | None, Form(max_length=280), BeforeValidator(normalize_caption)] = None,
) -> PostOut:
    limit(request, f"upload:{auth.user.id}", request.app.state.settings.upload_rate)
    return uploads(request).accept(
        auth.user.id, group_id, kind, None, idempotency_key, file.file, caption
    )


@router.get("/groups/{group_id}/feed", response_model=FeedOut)
def group_feed(
    group_id: uuid.UUID,
    request: Request,
    auth: Auth,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=1000),
) -> FeedOut:
    with request.app.state.factory.begin() as db:
        return feed(
            db,
            group_id,
            auth.user.id,
            request.app.state.clock.now(),
            limit,
            cursor,
            request.app.state.settings.secret_key,
        )


@router.get("/groups/{group_id}/leaderboard", response_model=LeaderboardOut)
def group_leaderboard(
    group_id: uuid.UUID,
    request: Request,
    auth: Auth,
    period: Literal["weekly", "all"] = "weekly",
    offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(20, ge=1, le=100),
) -> LeaderboardOut:
    with request.app.state.factory.begin() as db:
        return leaderboard(
            db, group_id, auth.user.id, period, request.app.state.clock.now(), offset, limit
        )


@router.get("/groups/{group_id}/members/{user_id}", response_model=ProfileOut)
def profile(group_id: uuid.UUID, user_id: uuid.UUID, request: Request, auth: Auth) -> ProfileOut:
    with request.app.state.factory.begin() as db:
        accounts.member(db, group_id, auth.user.id)
        accounts.member(db, group_id, user_id)
        user = db.get(User, user_id)
        assert user is not None
        return ProfileOut(
            user=UserOut.model_validate(user),
            streak=calculate(db, group_id, user_id, request.app.state.clock.now()),
        )


@router.get("/groups/{group_id}/posts/{post_id}/media", response_model=MediaOut)
def media(
    group_id: uuid.UUID, post_id: uuid.UUID, request: Request, response: Response, auth: Auth
) -> MediaOut:
    with request.app.state.factory.begin() as db:
        accounts.member(db, group_id, auth.user.id)
        post = db.get(Post, post_id)
        require(
            post is not None and post.group_id == group_id and post.removed_at is None,
            404,
            "post_not_found",
            "Post not found",
        )
        assert post is not None
        if post.parent_id:
            parent = db.get(Post, post.parent_id)
            require(
                parent is not None and parent.group_id == group_id and parent.removed_at is None,
                404,
                "post_not_found",
                "Post not found",
            )
        row = db.get(Upload, post.upload_id)
        require(
            row is not None and row.object_key is not None,
            404,
            "media_unavailable",
            "Media unavailable",
        )
        assert row is not None and row.object_key is not None
        key = row.object_key
    seconds = request.app.state.settings.media_url_seconds
    response.headers["Cache-Control"] = "no-store"
    return MediaOut(
        url=request.app.state.storage.sign(key, seconds),
        expires_at=request.app.state.clock.now() + timedelta(seconds=seconds),
    )


@router.delete("/groups/{group_id}/posts/{post_id}", response_model=Ok)
def delete_post(group_id: uuid.UUID, post_id: uuid.UUID, request: Request, auth: Auth) -> Ok:
    with request.app.state.factory.begin() as db:
        remove_post(db, group_id, auth.user.id, post_id, request.app.state.clock.now())
    return Ok()


@router.put("/groups/{group_id}/posts/{post_id}/like", response_model=EngagementOut)
def like_post(
    group_id: uuid.UUID, post_id: uuid.UUID, request: Request, auth: Auth
) -> EngagementOut:
    limit(request, f"social:{auth.user.id}", 120)
    with request.app.state.factory.begin() as db:
        return engagement.set_like(
            db, group_id, auth.user.id, post_id, request.app.state.clock.now(), True
        )


@router.delete("/groups/{group_id}/posts/{post_id}/like", response_model=EngagementOut)
def unlike_post(
    group_id: uuid.UUID, post_id: uuid.UUID, request: Request, auth: Auth
) -> EngagementOut:
    limit(request, f"social:{auth.user.id}", 120)
    with request.app.state.factory.begin() as db:
        return engagement.set_like(
            db, group_id, auth.user.id, post_id, request.app.state.clock.now(), False
        )


@router.get("/groups/{group_id}/posts/{post_id}/comments", response_model=CommentsOut)
def list_comments(
    group_id: uuid.UUID,
    post_id: uuid.UUID,
    request: Request,
    auth: Auth,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=1000),
) -> CommentsOut:
    with request.app.state.factory.begin() as db:
        return engagement.comments(
            db,
            group_id,
            auth.user.id,
            post_id,
            limit,
            cursor,
            request.app.state.settings.secret_key,
        )


@router.post(
    "/groups/{group_id}/posts/{post_id}/comments", response_model=CommentOut, status_code=201
)
def create_comment(
    group_id: uuid.UUID,
    post_id: uuid.UUID,
    body: CommentIn,
    request: Request,
    auth: Auth,
    idempotency_key: Idempotency,
) -> CommentOut:
    limit(request, f"comments:{auth.user.id}", 30)
    with request.app.state.factory.begin() as db:
        return engagement.add_comment(
            db,
            group_id,
            auth.user.id,
            post_id,
            body.text,
            idempotency_key,
            request.app.state.clock.now(),
        )


@router.delete("/groups/{group_id}/posts/{post_id}/comments/{comment_id}", response_model=Ok)
def delete_comment(
    group_id: uuid.UUID, post_id: uuid.UUID, comment_id: uuid.UUID, request: Request, auth: Auth
) -> Ok:
    limit(request, f"comments:{auth.user.id}", 30)
    with request.app.state.factory.begin() as db:
        engagement.remove_comment(
            db, group_id, auth.user.id, post_id, comment_id, request.app.state.clock.now()
        )
    return Ok()


@router.patch("/groups/{group_id}/posts/{post_id}/pin", response_model=Ok)
def pin_post(
    group_id: uuid.UUID, post_id: uuid.UUID, body: PinIn, request: Request, auth: Auth
) -> Ok:
    with request.app.state.factory.begin() as db:
        accounts.member(db, group_id, auth.user.id, admin=True, lock=True)
        post = engagement.accessible(db, group_id, auth.user.id, post_id, lock=True)
        require(
            post.source == "system", 422, "not_welcome", "Only group welcome content can be pinned"
        )
        post.pinned = body.pinned
        accounts.audit(
            db,
            group_id,
            auth.user.id,
            "welcome.pinned" if body.pinned else "welcome.unpinned",
            str(post_id),
            request.app.state.clock.now(),
        )
    return Ok()


@router.get("/me/tour/{version}", response_model=TourOut)
def tour_status(version: int, request: Request, auth: Auth) -> TourOut:
    require(1 <= version <= 1000, 422, "invalid_version", "Invalid tour version")
    with request.app.state.factory.begin() as db:
        return TourOut(
            version=version, completed=db.get(TourProgress, (auth.user.id, version)) is not None
        )


@router.put("/me/tour/{version}", response_model=TourOut)
def complete_tour(version: int, request: Request, auth: Auth) -> TourOut:
    require(1 <= version <= 1000, 422, "invalid_version", "Invalid tour version")
    with request.app.state.factory.begin() as db:
        db.execute(
            insert(TourProgress)
            .values(
                user_id=auth.user.id, version=version, completed_at=request.app.state.clock.now()
            )
            .on_conflict_do_nothing()
        )
    return TourOut(version=version, completed=True)
