import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.errors import Problem
from app.models.entities import Audit, Group, Membership
from app.services.identity import bootstrap, create_group
from tests.conftest import login

pytestmark = pytest.mark.integration


def test_creation_requires_session_csrf_and_rejects_privilege_fields(client):
    assert client.post("/groups", json={"name": "Our people"}).status_code == 401
    login(client, "creator")
    assert (
        client.post(
            "/groups", json={"name": "Our people"}, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    for extra in [
        {"role": "admin"},
        {"user_id": str(uuid.uuid4())},
        {"group_id": str(uuid.uuid4())},
    ]:
        assert client.post("/groups", json={"name": "Our people", **extra}).status_code == 422
    assert client.get("/groups").json() == []


@pytest.mark.parametrize("name", ["", "   ", "x" * 101, "bad\nname", "bad\x00name", "\u0344" * 100])
def test_invalid_group_names_are_rejected(client, name):
    login(client, "creator")
    assert client.post("/groups", json={"name": name}).status_code == 422
    assert client.get("/groups").json() == []


def test_create_join_and_group_permissions(client, application, factory):
    user = login(client, "owner")["user"]["id"]
    assert client.get("/groups").json() == []
    first = client.post("/groups", json={"name": "  The   final season 🌼  "})
    assert first.status_code == 201, first.text
    first = first.json()
    assert first["name"] == "The final season 🌼" and first["role"] == "admin"
    second = client.post("/groups", json={"name": "Study people"}).json()
    assert {g["id"] for g in client.get("/groups").json()} == {first["id"], second["id"]}
    assert client.get(f"/groups/{first['id']}/feed").status_code == 200
    with factory.begin() as db:
        memberships = db.scalars(
            select(Membership).where(Membership.user_id == uuid.UUID(user))
        ).all()
        assert len(memberships) == 2 and all(m.role == "admin" for m in memberships)
        assert (
            db.scalar(
                select(func.count()).select_from(Audit).where(Audit.action == "group.created")
            )
            == 2
        )
    token = client.post(f"/groups/{first['id']}/invites", json={}).json()["token"]
    with TestClient(application) as friend:
        login(friend, "friend")
        assert friend.get("/groups").json() == []
        assert friend.get(f"/groups/{first['id']}/feed").status_code == 403
        joined = friend.post("/groups/join", json={"token": token}).json()
        assert joined["id"] == first["id"] and joined["role"] == "member"
        assert friend.post(f"/groups/{first['id']}/invites", json={}).status_code == 403
        assert friend.get(f"/groups/{second['id']}/feed").status_code == 403
        own = friend.post("/groups", json={"name": "Friend-owned group"}).json()
        assert own["role"] == "admin"
        assert client.get(f"/groups/{own['id']}/feed").status_code == 403
        assert {g["role"] for g in friend.get("/groups").json()} == {"admin", "member"}


def test_bootstrap_alice_is_admin_without_promoting_other_visitors(client, factory, clock):
    login(client, "alice")
    with factory.begin() as db:
        bootstrap(db, "dev:alice", "Alice", clock.now())
        bootstrap(db, "dev:alice", "Alice", clock.now())
    groups = client.get("/groups").json()
    assert (
        len(groups) == 1
        and groups[0]["name"] == "Mustaaaaaard ’27"
        and groups[0]["role"] == "admin"
    )
    assert client.post(f"/groups/{groups[0]['id']}/invites", json={}).status_code == 201
    login(client, "other")
    assert client.get("/groups").json() == []
    assert (
        client.post("/groups", json={"name": "mustaaaaaard '27"}).json()["error"]["code"]
        == "group_name_reserved"
    )
    assert client.get("/groups").json() == []


def test_duplicate_name_returns_conflict_without_partial_membership(client, factory):
    login(client, "owner")
    assert client.post("/groups", json={"name": "The same name"}).status_code == 201
    response = client.post("/groups", json={"name": "  The same name  "})
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "group_name_unavailable"
    )
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(Group)) == 1
        assert db.scalar(select(func.count()).select_from(Membership)) == 1


def test_concurrent_creation_has_one_atomic_group_and_admin(client, factory, clock):
    user = uuid.UUID(login(client, "owner")["user"]["id"])
    barrier = Barrier(2)

    def attempt(_):
        barrier.wait()
        try:
            with factory.begin() as db:
                create_group(db, "Concurrent group", user, clock.now())
            return 201
        except Problem as error:
            return error.status

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [201, 409]
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(Group)) == 1
        memberships = db.scalars(select(Membership)).all()
        assert len(memberships) == 1 and memberships[0].role == "admin"
