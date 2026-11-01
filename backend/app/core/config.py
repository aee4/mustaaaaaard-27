from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        extra="ignore",
        hide_input_in_errors=True,
    )
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://mustard:mustard@localhost:5432/mustard"
    secret_key: str = "development-only-change-this-secret-key"
    dev_auth: bool = False
    base_url: str = "http://localhost:8000"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    cookie_secure: bool = False
    session_seconds: int = 604800
    capture_seconds: int = 600
    google_client_id: str = ""
    google_client_secret: str = ""
    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str | None = None
    s3_access_key: str = "mustard-local"
    s3_secret_key: str = "mustard-local-password"
    s3_bucket: str = "mustard-private"
    s3_region: str = "us-east-1"
    media_url_seconds: int = 120
    image_max_bytes: int = 15 * 1024 * 1024
    video_max_bytes: int = 50 * 1024 * 1024
    image_max_pixels: int = 40_000_000
    image_max_dimension: int = 12_000
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    lease_seconds: int = 300
    auth_rate: int = 30
    invite_rate: int = 30
    group_rate: int = 5
    upload_rate: int = 60
    media_concurrency: int = 1
    ffmpeg_threads: int = 1
    storage_quota_bytes: int = 0
    storage_object_quota: int = 0
    r2_billing_acknowledged: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def postgres_driver(cls, value: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        for value in (
            self.session_seconds,
            self.capture_seconds,
            self.image_max_bytes,
            self.video_max_bytes,
            self.image_max_pixels,
            self.image_max_dimension,
            self.auth_rate,
            self.invite_rate,
            self.group_rate,
            self.upload_rate,
            self.media_concurrency,
            self.ffmpeg_threads,
        ):
            if value <= 0:
                raise ValueError("limits must be positive")
        if self.storage_quota_bytes < 0 or self.storage_object_quota < 0:
            raise ValueError("storage quotas must be nonnegative; zero disables a quota")
        if not 1 <= self.media_url_seconds <= 300 or self.lease_seconds < 300:
            raise ValueError("signed URL lifetime must be 1..300s and lease at least 300s")
        if make_url(self.database_url).get_backend_name() != "postgresql":
            raise ValueError("PostgreSQL is required")
        for origin in self.allowed_origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
            ):
                raise ValueError("Origins must be exact http(s) origins without paths")
        if self.environment == "production":
            base = urlsplit(self.base_url)
            if (urlsplit(self.s3_endpoint).hostname or "").endswith(".r2.cloudflarestorage.com"):
                if (
                    not self.r2_billing_acknowledged
                    or not self.storage_quota_bytes
                    or not self.storage_object_quota
                ):
                    raise ValueError(
                        "R2 requires explicit billing acknowledgement and positive storage quotas"
                    )
            if (
                self.dev_auth
                or not self.cookie_secure
                or len(self.secret_key) < 32
                or "development" in self.secret_key
                or not self.google_client_id
                or not self.google_client_secret
                or not self.base_url.startswith("https://")
                or not base.hostname
                or base.path
                or base.query
                or base.fragment
                or base.username
                or not self.allowed_origins
                or not (self.s3_public_endpoint or self.s3_endpoint).startswith("https://")
                or any(not x.startswith("https://") for x in self.allowed_origins)
                or self.s3_access_key == "mustard-local"
                or self.s3_secret_key == "mustard-local-password"
                or "mustard:mustard@" in self.database_url
                or not self.s3_access_key
                or not self.s3_secret_key
            ):
                raise ValueError("unsafe or incomplete production configuration")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
