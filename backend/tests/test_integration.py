import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.errors import Problem
from app.models.entities import (
    Capture,
    Grace,
    Group,
    Post,
)
from app.services.identity import login as service_login
from app.services.identity import rate_limit
from app.services.uploads import UploadService
from tests.conftest import login, photo, upload

pytestmark = pytest.mark.integration


def test_auth_csrf_expiry_logout_and_errors(client, clock):
    assert client.get("/auth/session").status_code == 401
    data = login(client, "friend")
    response = client.patch("/me", json={"display_name": "new"}, headers={"X-CSRF-Token": "wrong"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "csrf_invalid"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert (
        client.patch(
            "/me", json={"display_name": "new"}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert client.patch("/me", json={"display_name": "New Friend"}).status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/session").status_code == 401
    login(client, "friend")
    clock.value = datetime.fromisoformat(data["expires_at"]) + timedelta(seconds=1)
    assert client.get("/auth/session").status_code == 401


def test_invite_limits_revocation_expiry_and_no_self_admin(client, admin, application, clock):
    _, group = admin
    path = f"/groups/{group}/invites"
    first = client.post(path, json={"max_uses": 1}).json()
    expired = client.post(path, json={"expires_in_hours": 1}).json()
    revoked = client.post(path, json={}).json()
    assert client.delete(path + "/" + revoked["id"]).status_code == 200
    with TestClient(application) as friend:
        login(friend, "friend")
        assert friend.get(f"/groups/{group}/feed").status_code == 403
        assert (
            friend.post("/groups/join", json={"token": first["token"], "role": "admin"}).status_code
            == 422
        )
        assert (
            friend.post("/groups/join", json={"token": first["token"]}).json()["role"] == "member"
        )
        assert friend.post(path, json={}).status_code == 403
    with TestClient(application) as stranger:
        login(stranger, "stranger")
        assert stranger.post("/groups/join", json={"token": first["token"]}).status_code == 409
        assert stranger.post("/groups/join", json={"token": revoked["token"]}).status_code == 409
        clock.value += timedelta(hours=1)
        assert stranger.post("/groups/join", json={"token": expired["token"]}).status_code == 409


def test_invite_concurrent_last_use(factory, client, admin, clock):
    from app.services.identity import join

    _, group = admin
    token = client.post(f"/groups/{group}/invites", json={"max_uses": 1}).json()["token"]
    users = [service_login(factory, f"dev:{i}", str(i), clock.now(), 600)[0] for i in range(2)]
    barrier = Barrier(2)

    def attempt(user):
        barrier.wait()
        try:
            with factory.begin() as db:
                join(db, token, user.id, clock.now())
            return 200
        except Problem as exc:
            return exc.status

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, users)) == [200, 409]


def test_capture_gallery_points_feed_delete_and_private_access(
    client, admin, factory, storage, clock
):
    user, group = admin
    capture = upload(client, group, photo("yellow"))
    gallery = upload(client, group, photo("blue"), gallery=True)
    assert capture.status_code == gallery.status_code == 200
    assert (capture.json()["points"], gallery.json()["points"]) == (1, 0)
    ranking = client.get(f"/groups/{group}/leaderboard").json()
    assert ranking["items"][0]["points"] == 1
    assert ranking["items"][0]["capture_photos"] == ranking["items"][0]["gallery_photos"] == 1
    assert ranking["items"][0]["streak"]["current"] == 1
    page = client.get(f"/groups/{group}/feed?limit=1").json()
    assert page["next_cursor"]
    second = client.get(
        f"/groups/{group}/feed", params={"limit": 1, "cursor": page["next_cursor"]}
    ).json()
    assert second["items"][0]["id"] != page["items"][0]["id"]
    assert not second["next_cursor"]
    post = capture.json()["id"]
    assert client.get(f"/groups/{group}/posts/{post}/media").status_code == 200
    assert client.delete(f"/groups/{group}/posts/{post}").status_code == 200
    assert client.get(f"/groups/{group}/posts/{post}/media").status_code == 404
    assert client.get(f"/groups/{group}/leaderboard").json()["items"][0]["points"] == 0
    assert upload(client, group, photo("yellow")).status_code == 409
    service = UploadService(factory, storage, clock, client.app.state.settings)
    assert service.cleanup() == 1
    assert service.cleanup() == 0
    assert len(storage.objects) == 1
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(Post)) == 2


def test_idempotency_replay_conflict_and_consumption(client, admin, factory):
    _, group = admin
    cap = client.post(f"/groups/{group}/captures", json={"kind": "photo"}).json()["id"]
    first = upload(client, group, photo(), key="same", capture=cap)
    replay = upload(client, group, photo(), key="same", capture=cap)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert (
        upload(client, group, photo("green"), key="same", capture=cap).json()["error"]["code"]
        == "idempotency_conflict"
    )
    assert (
        upload(client, group, photo("green"), key="other", capture=cap).json()["error"]["code"]
        == "capture_consumed"
    )
    with factory.begin() as db:
        assert db.get(Capture, uuid.UUID(cap)).consumed_at is not None
    client.delete(f"/groups/{group}/posts/{first.json()['id']}")
    assert upload(client, group, photo(), key="same", capture=cap).json()["removed"] is True


def test_foreign_expired_kind_and_cross_group_capture(client, admin, factory, clock, application):
    _, group = admin
    cap = client.post(f"/groups/{group}/captures", json={"kind": "photo"}).json()["id"]
    token = client.post(f"/groups/{group}/invites", json={}).json()["token"]
    with TestClient(application) as friend:
        login(friend, "friend")
        friend.post("/groups/join", json={"token": token})
        assert (
            upload(friend, group, photo(), capture=cap).json()["error"]["code"]
            == "capture_not_found"
        )
    assert (
        upload(client, group, photo(), capture=cap, kind="video").json()["error"]["code"]
        == "capture_kind_mismatch"
    )
    clock.value += timedelta(minutes=10)
    assert upload(client, group, photo(), capture=cap).json()["error"]["code"] == "capture_expired"
    with factory.begin() as db:
        other = Group(name="Other")
        db.add(other)
        db.flush()
        other_id = other.id
    assert client.get(f"/groups/{other_id}/feed").status_code == 403
    assert client.get(f"/groups/{other_id}/leaderboard").status_code == 403


def test_rejected_validation_does_not_consume_and_retry_same_key(client, admin, factory):
    _, group = admin
    cap = client.post(f"/groups/{group}/captures", json={"kind": "photo"}).json()["id"]
    for _ in range(2):
        assert upload(client, group, b"invalid", key="invalid", capture=cap).status_code == 422
    with factory.begin() as db:
        assert db.get(Capture, uuid.UUID(cap)).consumed_at is None
        assert db.scalar(select(func.count()).select_from(Post)) == 0
    assert upload(client, group, photo(), key="valid", capture=cap).status_code == 200


def test_storage_partial_failure_retry_and_cleanup(client, admin, factory, storage, clock):
    _, group = admin
    service = UploadService(factory, storage, clock, client.app.state.settings)
    storage.fail_put = storage.fail_delete = True
    failed = upload(client, group, photo(), gallery=True, key="partial")
    assert failed.status_code == 503
    assert len(storage.objects) == 1
    assert upload(client, group, photo(), gallery=True, key="partial").status_code == 409
    clock.value += timedelta(seconds=1)
    assert service.cleanup() == 0
    storage.fail_put = storage.fail_delete = False
    clock.value += timedelta(minutes=6)
    assert service.cleanup() == 1
    assert upload(client, group, photo(), gallery=True, key="partial").status_code == 200
    assert len(storage.objects) == 1


def test_capture_expires_during_storage_io(client, admin, storage, clock, monkeypatch, factory):
    _, group = admin
    original = storage.put

    def slow_put(key, path, content_type):
        original(key, path, content_type)
        clock.value += timedelta(minutes=11)

    monkeypatch.setattr(storage, "put", slow_put)
    response = upload(client, group, photo())
    assert response.status_code == 409
    assert response.json()["error"]["code"] in {"capture_expired", "upload_lease_lost"}
    assert not storage.objects
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(Post)) == 0


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_duplicate_and_idempotency(factory, storage, clock, config, admin, same_key):
    user, group = admin
    barrier = Barrier(2)
    service = UploadService(factory, storage, clock, config)

    def attempt(i):
        barrier.wait()
        try:
            return service.accept(
                user, group, "photo", None, "same" if same_key else str(i), io.BytesIO(photo())
            ).id
        except Problem as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert any(isinstance(result, uuid.UUID) for result in results)
    assert all(
        isinstance(result, uuid.UUID) or result in {"upload_in_progress", "duplicate_media"}
        for result in results
    )
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(Post)) == 1
    assert len(storage.objects) == 1


def test_two_simultaneous_posts_cannot_consume_one_capture(
    factory, storage, clock, config, admin, client
):
    user, group = admin
    cap = uuid.UUID(client.post(f"/groups/{group}/captures", json={"kind": "photo"}).json()["id"])
    barrier = Barrier(2)
    service = UploadService(factory, storage, clock, config)

    def attempt(color):
        barrier.wait()
        try:
            service.accept(user, group, "photo", cap, color, io.BytesIO(photo(color)))
            return "accepted"
        except Problem as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, ["blue", "red"]))
    assert sorted(results) == ["accepted", "capture_consumed"]
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(Post)) == 1


def test_member_removal_blocks_media_and_upload(client, admin, application):
    _, group = admin
    post = upload(client, group, photo()).json()["id"]
    token = client.post(f"/groups/{group}/invites", json={}).json()["token"]
    with TestClient(application) as friend:
        user = login(friend, "friend")["user"]["id"]
        friend.post("/groups/join", json={"token": token})
        assert friend.get(f"/groups/{group}/posts/{post}/media").status_code == 200
        assert friend.delete(f"/groups/{group}/posts/{post}").status_code == 403
        assert client.delete(f"/groups/{group}/members/{user}").status_code == 200
        assert friend.get(f"/groups/{group}/posts/{post}/media").status_code == 403
        assert friend.post(f"/groups/{group}/captures", json={"kind": "photo"}).status_code == 403


def test_leaderboard_competition_ties_and_pagination(client, admin, application):
    _, group = admin
    upload(client, group, photo("yellow"))
    token = client.post(f"/groups/{group}/invites", json={"max_uses": 2}).json()["token"]
    with TestClient(application) as friend:
        login(friend, "zfriend")
        friend.post("/groups/join", json={"token": token})
        upload(friend, group, photo("blue"))
    with TestClient(application) as third:
        login(third, "third")
        third.post("/groups/join", json={"token": token})
    rows = client.get(f"/groups/{group}/leaderboard").json()["items"]
    assert [r["rank"] for r in rows] == [1, 1, 3]
    assert [r["user"]["display_name"] for r in rows] == ["admin", "zfriend", "third"]
    page = client.get(f"/groups/{group}/leaderboard?offset=1&limit=1").json()
    assert page["total"] == 3 and page["items"][0] == rows[1]


def test_acceptance_midnight_and_week_rollover(client, admin, clock):
    _, group = admin
    clock.value = datetime(2026, 11, 1, 23, 59, 59, tzinfo=UTC)
    upload(client, group, photo("yellow"))
    clock.value += timedelta(seconds=1)
    upload(client, group, photo("blue"))
    weekly = client.get(f"/groups/{group}/leaderboard").json()
    overall = client.get(f"/groups/{group}/leaderboard?period=all").json()
    assert weekly["items"][0]["points"] == 1
    assert overall["items"][0]["points"] == 2
    assert weekly["items"][0]["streak"]["current"] == 2


def test_historical_deletion_keeps_grace_and_recomputes(client, admin, clock, factory):
    user, group = admin
    monday = upload(client, group, photo("yellow")).json()["id"]
    clock.value += timedelta(days=2)
    upload(client, group, photo("blue"))
    profile = f"/groups/{group}/members/{user}"
    assert client.get(profile).json()["streak"]["current"] == 2
    assert client.delete(f"/groups/{group}/posts/{monday}").status_code == 200
    assert client.get(profile).json()["streak"] == {
        "current": 1,
        "longest": 1,
        "grace_used_this_week": True,
    }
    with factory.begin() as db:
        rows = db.scalars(select(Grace)).all()
        assert len(rows) == 1 and rows[0].day.day == 3


def test_shared_database_rate_limit(factory, clock):
    rate_limit(factory, "user:test", 1, clock.now())
    with pytest.raises(Problem) as exc:
        rate_limit(factory, "user:test", 1, clock.now())
    assert exc.value.status == 429
    rate_limit(factory, "user:test", 1, clock.now() + timedelta(minutes=1))


def test_no_transaction_held_during_storage(client, admin, factory, storage, monkeypatch):
    _, group = admin
    original = storage.put

    def checked_put(key, path, content_type):
        assert factory.kw["bind"].pool.checkedout() == 0
        original(key, path, content_type)

    monkeypatch.setattr(storage, "put", checked_put)
    assert upload(client, group, photo()).status_code == 200


def test_request_and_image_byte_limits(client, admin, application):
    _, group = admin
    application.state.settings.image_max_bytes = 10
    assert upload(client, group, photo()).status_code == 413


def test_readiness(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
