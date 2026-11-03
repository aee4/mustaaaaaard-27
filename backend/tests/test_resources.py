import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import select

from app.core.errors import Problem
from app.models.entities import Post, Upload
from app.services import uploads
from app.services.resources import media_gate
from app.services.social import remove_post
from app.services.uploads import UploadService
from tests.conftest import photo

pytestmark = pytest.mark.integration


def test_storage_full_preserves_memories_replay_and_cleanup_debt(
    admin, factory, storage, clock, config
):
    user, group = admin
    config.storage_object_quota = 2
    service = UploadService(factory, storage, clock, config)
    content = photo()
    first = service.accept(user, group, "photo", None, "first", io.BytesIO(content))
    assert service.accept(user, group, "photo", None, "first", io.BytesIO(content)).id == first.id
    with pytest.raises(Problem) as rejected:
        service.accept(user, group, "photo", None, "second", io.BytesIO(photo("red")))
    assert rejected.value.code == "storage_quota_exceeded"
    assert len(storage.objects) == 2
    with factory.begin() as db:
        remove_post(db, group, user, first.id, clock.now())
    # Removal changes scores, but bytes count until storage deletion is confirmed.
    storage.fail_delete = True
    assert service.cleanup() == 0
    with pytest.raises(Problem):
        service.accept(user, group, "photo", None, "second", io.BytesIO(photo("red")))
    storage.fail_delete = False
    clock.value += timedelta(minutes=6)
    service.cleanup()
    assert (
        service.accept(user, group, "photo", None, "second", io.BytesIO(photo("red"))).points == 0
    )


def test_byte_quota_and_unknown_legacy_usage_fail_before_put(
    admin, factory, storage, clock, config
):
    user, group = admin
    config.storage_quota_bytes = 1
    service = UploadService(factory, storage, clock, config)
    with pytest.raises(Problem) as rejected:
        service.accept(user, group, "photo", None, "too-large", io.BytesIO(photo()))
    assert rejected.value.code == "storage_quota_exceeded" and not storage.objects
    config.storage_quota_bytes = 10000
    service.accept(user, group, "photo", None, "fits", io.BytesIO(photo()))
    with factory.begin() as db:
        row = db.scalar(select(Upload).where(Upload.state == "accepted"))
        row.storage_bytes = None
    with pytest.raises(Problem) as rejected:
        service.accept(user, group, "photo", None, "unknown", io.BytesIO(photo("red")))
    assert rejected.value.code == "storage_usage_unknown" and len(storage.objects) == 2


@pytest.mark.parametrize("quota", ["objects", "bytes"])
def test_concurrent_reservations_cannot_overfill(
    admin, factory, storage, clock, config, monkeypatch, quota
):
    user, group = admin
    config.storage_object_quota = 2 if quota == "objects" else 0
    config.storage_quota_bytes = 200 if quota == "bytes" else 0
    service = UploadService(factory, storage, clock, config)
    barrier = Barrier(2)
    sanitized = Barrier(2)
    original = uploads.sanitize

    def both_claimed(*args):
        result = original(*args)
        sanitized.wait(timeout=10)
        return result

    monkeypatch.setattr(uploads, "sanitize", both_claimed)

    def accept(color):
        barrier.wait()
        try:
            service.accept(user, group, "photo", None, str(uuid.uuid4()), io.BytesIO(photo(color)))
            return "accepted"
        except Problem as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(accept, ["red", "blue"]))
    assert results.count("accepted") == 1
    assert len(storage.objects) == 2
    with factory.begin() as db:
        assert len(db.scalars(select(Post)).all()) == 1


def test_busy_processor_is_retryable_and_releases_claim(admin, factory, storage, clock, config):
    user, group = admin
    config.media_concurrency = 1
    gate = media_gate(1)
    gate.acquire()
    service = UploadService(factory, storage, clock, config)
    try:
        with pytest.raises(Problem) as busy:
            service.accept(user, group, "photo", None, "retry", io.BytesIO(photo()))
        assert busy.value.status == 503 and busy.value.code == "media_busy"
        assert not storage.objects
    finally:
        gate.release()
    assert service.accept(user, group, "photo", None, "retry", io.BytesIO(photo())).id
