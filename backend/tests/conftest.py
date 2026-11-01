import io
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.main import create_app
from app.services.identity import bootstrap


@pytest.fixture
def video_config(config):
    config.ffmpeg = os.getenv("FFMPEG", "ffmpeg")
    config.ffprobe = os.getenv("FFPROBE", "ffprobe")
    if not shutil.which(config.ffmpeg) or not shutil.which(config.ffprobe):
        pytest.skip("FFMPEG and FFPROBE executable paths required")
    return config


class FrozenClock(Clock):
    def __init__(self) -> None:
        self.value = datetime(2026, 11, 2, 12, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_put = self.fail_delete = False

    def put(self, key: str, path: Path, content_type: str) -> None:
        self.objects[key] = path.read_bytes()
        if self.fail_put:
            raise OSError("simulated partial write")

    def delete(self, key: str) -> None:
        if self.fail_delete:
            raise OSError("simulated delete failure")
        self.objects.pop(key, None)

    def sign(self, key: str, seconds: int) -> str:
        return f"https://private.test/{key}?signature=test"

    def ready(self) -> None:
        pass

    def old_keys(self, before):
        return iter(())


@pytest.fixture(autouse=True)
def isolate_dotenv(monkeypatch):
    # Developer .env must not change deterministic unit/service configuration.
    monkeypatch.setitem(Settings.model_config, "env_file", None)


def photo(color: str = "yellow", exif: bool = False) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (16, 16), color)
    metadata = Image.Exif()
    if exif:
        metadata[0x010E] = "Sensitive location"
    image.save(buffer, "JPEG", exif=metadata)
    return buffer.getvalue()


@pytest.fixture
def clock():
    return FrozenClock()


@pytest.fixture
def storage():
    return MemoryStorage()


@pytest.fixture
def factory():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required (PostgreSQL, dedicated *_test database)")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Refusing to reset anything except a dedicated PostgreSQL *_test database")
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as connection:
        tables = connection.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename != 'alembic_version'"
            )
        )
        names = [f'"{row[0]}"' for row in tables]
        if not names:
            pytest.fail("Run Alembic migrations against TEST_DATABASE_URL first")
        connection.execute(text("TRUNCATE " + ",".join(names) + " CASCADE"))
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def config():
    return Settings(
        environment="test",
        dev_auth=True,
        auth_rate=1000,
        invite_rate=1000,
        upload_rate=1000,
        media_concurrency=8,
    )


@pytest.fixture
def application(factory, storage, clock, config):
    return create_app(config, factory, storage, clock)


@pytest.fixture
def client(application):
    with TestClient(application) as connection:
        yield connection


def login(client: TestClient, name: str) -> dict:
    response = client.post(
        "/auth/dev",
        json={"subject": name, "display_name": name},
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    client.headers.update({"Origin": "http://localhost:3000", "X-CSRF-Token": body["csrf_token"]})
    return body


@pytest.fixture
def admin(client, factory, clock):
    user = login(client, "admin")
    with factory.begin() as db:
        _, group = bootstrap(db, "dev:admin", "admin", clock.now())
    return uuid.UUID(user["user"]["id"]), group.id


def upload(
    client: TestClient,
    group: object,
    data: bytes,
    *,
    gallery: bool = False,
    kind: str = "photo",
    key: str | None = None,
    capture: str | None = None,
    caption: str | None = None,
):
    if gallery:
        path = f"/groups/{group}/gallery"
    else:
        if capture is None:
            response = client.post(f"/groups/{group}/captures", json={"kind": kind})
            assert response.status_code == 201, response.text
            capture = response.json()["id"]
        path = f"/groups/{group}/captures/{capture}/upload"
    return client.post(
        path,
        params={"kind": kind},
        files={"file": ("untrusted.ext", data, "application/octet-stream")},
        data={"caption": caption} if caption is not None else {},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )
