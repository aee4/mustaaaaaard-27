import logging
import uuid

from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.routes import router
from app.core.clock import Clock
from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.core.errors import Problem
from app.integrations.storage import S3Storage, Storage
from app.schemas.api import ErrorOut


class RequestGuard:
    def __init__(self, app: ASGIApp, max_body: int):
        self.app, self.max_body = app, max_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        total = 0

        async def bounded_receive() -> Message:
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_body:
                    raise HTTPException(413, "Request exceeds upload limit")
            return message

        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend(
                    [
                        (b"x-request-id", request_id.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"cache-control", b"no-store"),
                    ]
                )
            await send(message)

        try:
            await self.app(scope, bounded_receive, wrapped_send)
        except Exception:
            # Do not log request values, provider tokens, signed URLs, media or traces.
            logging.getLogger("mustard").error("request_failed request_id=%s", request_id)
            result = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "Request failed",
                        "request_id": request_id,
                    }
                },
            )
            await result(scope, receive, wrapped_send)


def create_app(
    settings: Settings | None = None,
    factory: sessionmaker[Session] | None = None,
    storage: Storage | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    config = settings or get_settings()
    app = FastAPI(
        title="Mustaaaaaard ’27",
        description="The Final Season. Private backend.",
        version="0.1.0",
        responses={
            status: {"model": ErrorOut}
            for status in (400, 401, 403, 404, 409, 413, 422, 429, 500, 503)
        },
    )
    app.state.settings, app.state.factory = config, factory or SessionLocal
    app.state.storage, app.state.clock = storage or S3Storage(config), clock or Clock()
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=config.google_client_id,
        client_secret=config.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile email",
            "code_challenge_method": "S256",
            "timeout": 10,
        },
    )
    app.state.oauth = oauth
    app.add_middleware(
        SessionMiddleware,
        secret_key=config.secret_key,
        session_cookie="mustard_oauth",
        max_age=600,
        https_only=config.cookie_secure,
        same_site="lax",
    )
    app.add_middleware(
        RequestGuard, max_body=max(config.video_max_bytes, config.image_max_bytes) + 1024 * 1024
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )

    def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": getattr(request.state, "request_id", "unknown"),
                }
            },
        )

    @app.exception_handler(Problem)
    async def problem_handler(request: Request, exc: Problem) -> JSONResponse:
        return error_response(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            request, 422, "validation_error", "Request does not match the API schema"
        )

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 413:
            return error_response(request, 413, "media_too_large", "Request exceeds upload limit")
        return error_response(
            request, exc.status_code, "http_error", "Request could not be handled"
        )

    app.include_router(router)
    return app


app = create_app()
