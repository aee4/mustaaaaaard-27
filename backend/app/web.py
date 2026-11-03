"""Same-origin production entrypoint: static React, /api and Google callbacks."""

from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings, get_settings
from app.main import create_app


class Frontend(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        if path.strip("/") in {"", ".", "capture", "leaderboard", "profile"}:
            path = "index.html"
        return await super().get_response(path, scope)


class WebHeaders:
    def __init__(self, app: ASGIApp, secure: bool):
        self.app, self.secure = app, secure

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend(
                    [
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
                if self.secure:
                    message["headers"].append((b"strict-transport-security", b"max-age=31536000"))
            await send(message)

        await self.app(scope, receive, headers)


def create_web_app(settings: Settings, directory: Path, api: FastAPI | None = None) -> Starlette:
    api = api or create_app(settings)
    if not (directory / "index.html").is_file():
        raise RuntimeError("Build frontend/dist before starting the web entrypoint")
    return Starlette(
        routes=[
            Mount("/api", app=api),
            Route("/auth/google", endpoint=api),
            Route("/auth/google/callback", endpoint=api),
            Route("/ready", endpoint=api),
            Route("/health", endpoint=api),
            Mount("/", app=Frontend(directory=directory)),
        ],
        middleware=[
            Middleware(
                TrustedHostMiddleware,
                allowed_hosts=[
                    urlsplit(settings.base_url).hostname or "invalid",
                    *settings.backend_hosts,
                ]
                if settings.environment == "production"
                else ["*"],
            ),
            Middleware(WebHeaders, secure=settings.environment == "production"),
        ],
    )


def production_app() -> Starlette:
    # Fixed artifact location inside the image. Local preview uses frontend/dist.
    import os

    return create_web_app(get_settings(), Path(os.environ.get("WEB_DIST", "/srv/web")))
