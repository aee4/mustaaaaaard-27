import secrets
from dataclasses import dataclass

from fastapi import Header, Request, Security
from fastapi.security import APIKeyCookie

from app.core.errors import require
from app.models.entities import LoginSession, User
from app.services.identity import digest


@dataclass
class Identity:
    user: User
    session: LoginSession


cookie_auth = APIKeyCookie(name="mustard_session", auto_error=False)


def check_origin(request: Request) -> None:
    require(
        request.headers.get("origin") in request.app.state.settings.allowed_origins,
        403,
        "origin_forbidden",
        "Allowed Origin header required",
    )


def identity(
    request: Request,
    token: str | None = Security(cookie_auth),
    csrf_header: str | None = Header(None, alias="X-CSRF-Token"),
) -> Identity:
    with request.app.state.factory.begin() as db:
        session = db.get(LoginSession, digest(token or ""))
        require(
            session is not None
            and session.revoked_at is None
            and session.expires_at > request.app.state.clock.now(),
            401,
            "authentication_required",
            "Valid session required",
        )
        assert session is not None
        user = db.get(User, session.user_id)
        assert user is not None
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            check_origin(request)
            supplied = csrf_header or ""
            require(
                secrets.compare_digest(supplied, session.csrf),
                403,
                "csrf_invalid",
                "Valid CSRF token required",
            )
        return Identity(user, session)
