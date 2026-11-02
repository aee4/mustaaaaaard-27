import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.core.errors import Problem
from app.models.entities import Comment, Membership, Post, PostLike
from app.services.engagement import set_like
from app.services.welcome import seed_welcome
from tests.conftest import login, photo, upload


def test_likes_concurrency_idempotency_and_scoring(client, admin, factory, clock):
    actor, group = admin
    post = upload(client, group, photo()).json()

    def like(_):
        with factory.begin() as db:
            return set_like(db, group, actor, uuid.UUID(post["id"]), clock.now(), True)

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert all(item.like_count == 1 for item in pool.map(like, range(12)))
    endpoint = f"/groups/{group}/posts/{post['id']}/like"
    assert client.put(endpoint).json()["like_count"] == 1
    assert client.delete(endpoint).json()["like_count"] == 0
    assert client.delete(endpoint).json()["like_count"] == 0
    feed = client.get(f"/groups/{group}/feed").json()["items"][0]
    assert feed["author_name"] == "admin" and feed["liked"] is False
    assert client.get(f"/groups/{group}/leaderboard").json()["items"][0]["points"] == 1
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(PostLike)) == 0


def test_comment_retries_pagination_deletion_and_validation(client, admin):
    _, group = admin
    post = upload(client, group, photo(), gallery=True).json()
    endpoint = f"/groups/{group}/posts/{post['id']}/comments"
    response = client.post(
        endpoint,
        json={"text": "  hello\r\n<b>friends</b> 💛  "},
        headers={"Idempotency-Key": "same"},
    )
    assert response.status_code == 201
    comment = response.json()
    assert comment["text"] == "hello\n<b>friends</b> 💛"
    assert (
        client.post(
            endpoint, json={"text": comment["text"]}, headers={"Idempotency-Key": "same"}
        ).json()["id"]
        == comment["id"]
    )
    assert (
        client.post(
            endpoint, json={"text": "changed"}, headers={"Idempotency-Key": "same"}
        ).status_code
        == 409
    )
    for value in ("", "  ", "x" * 501, "bad\x00"):
        assert (
            client.post(
                endpoint, json={"text": value}, headers={"Idempotency-Key": "bad"}
            ).status_code
            == 422
        )
    for index in range(4):
        assert (
            client.post(
                endpoint, json={"text": str(index)}, headers={"Idempotency-Key": str(index)}
            ).status_code
            == 201
        )
    first = client.get(endpoint, params={"limit": 2}).json()
    second = client.get(endpoint, params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    assert client.get(endpoint, params={"cursor": "invalid"}).status_code == 422
    assert client.delete(endpoint + "/" + comment["id"]).status_code == 200
    assert client.delete(endpoint + "/" + comment["id"]).status_code == 200
    retry = client.post(
        endpoint, json={"text": comment["text"]}, headers={"Idempotency-Key": "same"}
    ).json()
    assert retry["removed"] and retry["text"] is None
    assert client.get(f"/groups/{group}/feed").json()["items"][0]["comment_count"] == 4
    assert client.get(f"/groups/{group}/leaderboard").json()["items"][0]["points"] == 0


def test_social_membership_scope_moderation_removed_post_and_csrf(client, admin, factory):
    actor, group = admin
    post = upload(client, group, photo()).json()
    base = f"/groups/{group}/posts/{post['id']}"
    own = client.post(
        base + "/comments", json={"text": "own"}, headers={"Idempotency-Key": "own"}
    ).json()
    invite = client.post(f"/groups/{group}/invites", json={"max_uses": 2}).json()["token"]
    outsider = login(client, "outsider")["user"]["id"]
    assert client.put(base + "/like").status_code == 403
    assert client.get(base + "/comments").status_code == 403
    assert client.post("/groups/join", json={"token": invite}).status_code == 200
    assert client.delete(base + "/comments/" + own["id"]).status_code == 403
    stranger = client.post(
        base + "/comments", json={"text": "stranger"}, headers={"Idempotency-Key": "stranger"}
    ).json()
    with factory.begin() as db:
        membership = db.get(Membership, (group, uuid.UUID(outsider)))
        membership.removed_at = db.get(Post, uuid.UUID(post["id"])).accepted_at
    assert client.get(base + "/comments").status_code == 403
    assert client.put(base + "/like").status_code == 403
    login(client, "admin")
    assert client.delete(base + "/comments/" + stranger["id"]).status_code == 200
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.put(base + "/like").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    wrong = f"/groups/{uuid.uuid4()}/posts/{post['id']}"
    assert client.get(wrong + "/comments").status_code == 403
    assert client.delete(base).status_code == 200
    assert client.get(base + "/comments").status_code == 404
    assert client.put(base + "/like").status_code == 404
    assert (
        client.post(
            base + "/comments", json={"text": "hidden"}, headers={"Idempotency-Key": "new"}
        ).status_code
        == 404
    )
    with factory.begin() as db:
        assert db.scalar(select(Comment).where(Comment.id == uuid.UUID(own["id"]))).text is None


def test_comment_rate_limit(client, admin):
    _, group = admin
    post = upload(client, group, photo()).json()
    endpoint = f"/groups/{group}/posts/{post['id']}/comments"
    for index in range(30):
        assert (
            client.post(
                endpoint, json={"text": "hi"}, headers={"Idempotency-Key": str(index)}
            ).status_code
            == 201
        )
    assert (
        client.post(endpoint, json={"text": "hi"}, headers={"Idempotency-Key": "last"}).status_code
        == 429
    )


def test_tour_per_account_and_version(client, admin):
    assert client.get("/me/tour/1").json()["completed"] is False
    assert client.put("/me/tour/1").json()["completed"] is True
    assert client.put("/me/tour/1").json()["completed"] is True
    assert client.get("/me/tour/2").json()["completed"] is False
    login(client, "other")
    assert client.get("/me/tour/1").json()["completed"] is False


def test_welcome_private_album_idempotent_unpin_remove(
    client, admin, factory, storage, config, clock, tmp_path
):
    actor, group = admin
    photos = []
    for index, color in enumerate(("red", "green", "blue")):
        path = tmp_path / f"{index}.jpg"
        path.write_bytes(photo(color, exif=True))
        photos.append(path)
    post = seed_welcome(factory, storage, config, clock, group, actor, photos)
    assert seed_welcome(factory, storage, config, clock, group, actor, photos) == post
    assert len(storage.objects) == 3
    feed = client.get(f"/groups/{group}/feed").json()
    assert feed["items"] == []
    welcome = feed["pinned"]
    assert welcome["user_id"] is None and welcome["source"] == "system"
    assert welcome["title"] == "The Final Season 💛" and welcome["points"] == 0
    assert len(welcome["album"]) == 2
    for child in welcome["album"]:
        assert client.get(f"/groups/{group}/posts/{child}/media").status_code == 200
        assert client.put(f"/groups/{group}/posts/{child}/like").status_code == 404
    base = f"/groups/{group}/posts/{post}"
    assert client.put(base + "/like").json()["like_count"] == 1
    assert (
        client.post(
            base + "/comments", json={"text": "welcome"}, headers={"Idempotency-Key": "welcome"}
        ).status_code
        == 201
    )
    assert client.get(f"/groups/{group}/leaderboard").json()["items"][0]["points"] == 0
    invite = client.post(f"/groups/{group}/invites", json={}).json()["token"]
    login(client, "new-member")
    client.post("/groups/join", json={"token": invite})
    assert client.get(f"/groups/{group}/feed").json()["pinned"]["id"] == str(post)
    assert client.patch(base + "/pin", json={"pinned": False}).status_code == 403
    login(client, "admin")
    client.patch(base + "/pin", json={"pinned": False})
    assert seed_welcome(factory, storage, config, clock, group, actor, photos) == post
    feed = client.get(f"/groups/{group}/feed").json()
    assert feed["pinned"] is None and len(feed["items"]) == 1
    assert client.delete(base).status_code == 200
    assert seed_welcome(factory, storage, config, clock, group, actor, photos) == post
    for child in welcome["album"]:
        assert client.get(f"/groups/{group}/posts/{child}/media").status_code == 404
    with pytest.raises(Problem):
        seed_welcome(factory, storage, config, clock, uuid.uuid4(), actor, photos)
