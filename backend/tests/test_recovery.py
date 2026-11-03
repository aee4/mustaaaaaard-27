import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Event

import pytest
from sqlalchemy import func, select

from app.core.errors import Problem
from app.models.entities import Capture, Post, Upload
from app.services.uploads import UploadService
from tests.conftest import photo

pytestmark = pytest.mark.integration


class CommitFailureFactory:
    """Fail the acceptance commit, either before or after the real commit."""

    def __init__(self, factory, after=False, unavailable_after=False):
        self.factory, self.after, self.unavailable_after = factory, after, unavailable_after
        self.failed = False

    @contextmanager
    def begin(self):
        if self.failed and self.unavailable_after:
            raise OSError("database unreachable")
        with self.factory() as db:
            with db.begin():
                yield db
                accepting = (
                    bool(db.scalar(select(func.count()).select_from(Post))) and not self.failed
                )
                if accepting:
                    self.failed = True
                    if self.after:
                        db.commit()
                    raise OSError("lost database connection at commit")


@pytest.mark.parametrize("after", [False, True])
def test_storage_success_database_commit_failure_and_ambiguous_commit(
    admin, factory, storage, clock, config, after
):
    user, group = admin
    faulty = CommitFailureFactory(factory, after=after)
    service = UploadService(faulty, storage, clock, config)
    with pytest.raises(Problem) as failure:
        service.accept(user, group, "photo", None, "commit", io.BytesIO(photo()))
    assert failure.value.status == 503
    with factory.begin() as db:
        assert db.scalar(select(func.count()).select_from(Post)) == int(after)
    assert len(storage.objects) == 2 * int(after)
    recovered = UploadService(factory, storage, clock, config).accept(
        user, group, "photo", None, "commit", io.BytesIO(photo())
    )
    assert recovered.id and len(storage.objects) == 2


def test_database_outage_leaves_tracked_object_for_cleanup(admin, factory, storage, clock, config):
    user, group = admin
    faulty = CommitFailureFactory(factory, unavailable_after=True)
    with pytest.raises(Problem):
        UploadService(faulty, storage, clock, config).accept(
            user, group, "photo", None, "outage", io.BytesIO(photo())
        )
    assert len(storage.objects) == 2
    with factory.begin() as db:
        row = db.scalar(select(Upload))
        assert row.state == "processing" and row.object_key in storage.objects
    clock.value += timedelta(minutes=6)
    service = UploadService(factory, storage, clock, config)
    assert service.cleanup() == 1 and not storage.objects
    assert service.cleanup() == 0
    assert service.accept(user, group, "photo", None, "outage", io.BytesIO(photo())).id


def test_orphan_inventory_reconciliation_preserves_live_objects(
    admin, factory, storage, clock, config, monkeypatch
):
    user, group = admin
    service = UploadService(factory, storage, clock, config)
    service.accept(user, group, "photo", None, "live", io.BytesIO(photo()))
    live_keys = set(storage.objects)
    storage.objects["media/late-stale-write"] = b"orphan"
    monkeypatch.setattr(storage, "old_keys", lambda before: iter(list(storage.objects)))
    assert service.cleanup() == 1
    assert set(storage.objects) == live_keys
    assert service.cleanup() == 0


def test_capture_consumption_rolls_back_with_post_commit(admin, factory, storage, clock, config):
    user, group = admin
    cap_id = uuid.uuid4()
    with factory.begin() as db:
        db.add(
            Capture(
                id=cap_id,
                user_id=user,
                group_id=group,
                kind="photo",
                expires_at=clock.now() + timedelta(minutes=10),
            )
        )
    with pytest.raises(Problem):
        UploadService(CommitFailureFactory(factory), storage, clock, config).accept(
            user, group, "photo", cap_id, "atomic", io.BytesIO(photo())
        )
    with factory.begin() as db:
        assert db.get(Capture, cap_id).consumed_at is None
        assert db.scalar(select(func.count()).select_from(Post)) == 0
    assert not storage.objects
    assert (
        UploadService(factory, storage, clock, config)
        .accept(user, group, "photo", cap_id, "atomic", io.BytesIO(photo()))
        .points
        == 1
    )


def test_capture_expiry_after_put_before_lease_expiry(
    admin, factory, storage, clock, config, monkeypatch
):
    user, group = admin
    cap_id = uuid.uuid4()
    with factory.begin() as db:
        db.add(
            Capture(
                id=cap_id,
                user_id=user,
                group_id=group,
                kind="photo",
                expires_at=clock.now() + timedelta(seconds=1),
            )
        )
    original = storage.put

    def put(key, path, content_type):
        original(key, path, content_type)
        clock.value += timedelta(seconds=2)

    monkeypatch.setattr(storage, "put", put)
    with pytest.raises(Problem) as exc:
        UploadService(factory, storage, clock, config).accept(
            user, group, "photo", cap_id, "expiry", io.BytesIO(photo())
        )
    assert exc.value.code == "capture_expired" and not storage.objects
    with factory.begin() as db:
        assert db.get(Capture, cap_id).consumed_at is None


def test_removal_while_storage_processing_prevents_acceptance(
    client, admin, factory, storage, clock, config, application, monkeypatch
):
    from fastapi.testclient import TestClient

    from tests.conftest import login

    _, group = admin
    token = client.post(f"/groups/{group}/invites", json={}).json()["token"]
    entered, release = Event(), Event()
    original = storage.put

    def put(key, path, content_type):
        original(key, path, content_type)
        entered.set()
        assert release.wait(10)

    monkeypatch.setattr(storage, "put", put)
    with TestClient(application) as friend:
        user = uuid.UUID(login(friend, "friend")["user"]["id"])
        friend.post("/groups/join", json={"token": token})
        service = UploadService(factory, storage, clock, config)
        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(
                service.accept, user, group, "photo", None, "removed", io.BytesIO(photo())
            )
            assert entered.wait(10)
            try:
                assert client.delete(f"/groups/{group}/members/{user}").status_code == 200
            finally:
                release.set()
            with pytest.raises(Problem) as exc:
                pending.result()
            assert exc.value.code == "membership_required"
    assert not storage.objects
