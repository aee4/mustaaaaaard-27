import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.errors import Problem
from app.main import create_app
from app.models.entities import Group, Membership, Post
from app.services.identity import login as service_login
from app.services.media import video_demuxer
from app.services.uploads import UploadService
from tests.conftest import photo, upload


@pytest.mark.integration
def test_group_duplicate_constraint_between_different_users(
    admin, factory, storage, clock, config, monkeypatch
):
    admin_id, group = admin
    other, _, _ = service_login(factory, "dev:other", "other", clock.now(), 600)
    with factory.begin() as db:
        db.add(Membership(user_id=other.id, group_id=group))
    # Force both workers beyond prechecks/storage before either can accept.
    barrier = Barrier(2)
    original = storage.put

    def put(key, path, content_type):
        original(key, path, content_type)
        barrier.wait(timeout=10)

    monkeypatch.setattr(storage, "put", put)
    service = UploadService(factory, storage, clock, config)

    def attempt(user):
        try:
            service.accept(user, group, "photo", None, "same", io.BytesIO(photo()))
            return "accepted"
        except Problem as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, [admin_id, other.id])) == ["accepted", "duplicate_media"]
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(Post)) == 1
    assert len(storage.objects) == 2


@pytest.mark.integration
def test_duplicate_is_scoped_to_group_and_resources_do_not_cross(client, admin, factory):
    user, group = admin
    post = upload(client, group, photo()).json()["id"]
    with factory.begin() as db:
        other = Group(name="Other")
        db.add(other)
        db.flush()
        db.add(Membership(user_id=user, group_id=other.id))
        other_id = other.id
    assert upload(client, other_id, photo(), gallery=True).status_code == 200
    assert client.get(f"/groups/{other_id}/posts/{post}/media").status_code == 404
    assert client.delete(f"/groups/{other_id}/posts/{post}").status_code == 404
    page = client.get(f"/groups/{group}/feed?limit=1").json()
    assert page["items"][0]["id"] == post


@pytest.mark.integration
def test_replay_removed_post_during_failed_cleanup(client, admin, factory, storage, clock, config):
    _, group = admin
    result = upload(client, group, photo(), gallery=True, key="cleanup").json()
    client.delete(f"/groups/{group}/posts/{result['id']}")
    storage.fail_delete = True
    assert UploadService(factory, storage, clock, config).cleanup() == 0
    replay = upload(client, group, photo(), gallery=True, key="cleanup")
    assert replay.status_code == 200 and replay.json()["removed"]


def test_hard_body_limit_handles_parser_error():
    app = create_app(Settings(video_max_bytes=1, image_max_bytes=1))
    with TestClient(app) as client:
        response = client.post(
            f"/groups/{uuid.uuid4()}/gallery?kind=video",
            files={"file": ("video", b"x" * (1024 * 1024 + 100))},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "media_too_large"


def test_video_container_gate_rejects_playlists_quicktime_and_matroska(tmp_path):
    source = tmp_path / "input"
    for data in [
        b"#EXTM3U\nfile:///etc/passwd",
        b"\x00\x00\x00\x18ftypqt  \x00" * 2,
        bytes.fromhex("1a45dfa38b428288") + b"matroska",
    ]:
        source.write_bytes(data)
        with pytest.raises(Problem):
            video_demuxer(source)


def test_production_disables_dev_login_and_uses_secure_cookie():
    config = Settings(
        environment="production",
        cookie_secure=True,
        secret_key="x" * 40,
        base_url="https://app.example",
        allowed_origins=["https://app.example"],
        google_client_id="id",
        google_client_secret="secret",
        s3_access_key="service",
        s3_secret_key="service-secret",
        s3_endpoint="https://s3.example",
        database_url="postgresql+psycopg://service:secret@db/app",
    )
    with TestClient(create_app(config)) as client:
        response = client.post("/auth/dev", json={"subject": "me", "display_name": "Me"})
        assert response.status_code == 404
