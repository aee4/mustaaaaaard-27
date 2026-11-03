import io
import os
import uuid

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.errors import Problem
from app.integrations.storage import S3Storage
from app.models.entities import Post, Upload
from app.services.thumbnails import backfill
from app.services.uploads import UploadService
from tests.conftest import login, upload


@pytest.mark.integration
def test_private_thumbnail_dimensions_original_and_cleanup(
    client, admin, factory, storage, clock, config
):
    user, group = admin
    source = io.BytesIO()
    Image.new("RGB", (1600, 2400), "gold").save(source, "JPEG")
    post = upload(client, group, source.getvalue(), gallery=True).json()
    assert (post["media_width"], post["media_height"]) == (1600, 2400)
    endpoint = f"/groups/{group}/posts/{post['id']}/media"
    thumb = client.get(endpoint + "?variant=thumbnail")
    assert thumb.status_code == 200 and "no-store" in thumb.headers["cache-control"]
    assert (thumb.json()["width"], thumb.json()["height"]) == (1600, 2400)
    assert client.get(endpoint).json()["url"] != thumb.json()["url"]
    with factory.begin() as db:
        row = db.get(Upload, db.get(Post, uuid.UUID(post["id"])).upload_id)
        assert row.storage_bytes == sum(map(len, storage.objects.values()))
        assert row.thumbnail_ready
        with Image.open(io.BytesIO(storage.objects[row.object_key])) as original:
            assert original.size == (1600, 2400) and not original.getexif()
        with Image.open(io.BytesIO(storage.objects[row.thumbnail_key])) as small:
            assert small.size == (640, 960) and not small.getexif()
    login(client, "outsider")
    assert client.get(endpoint + "?variant=thumbnail").status_code == 403
    login(client, "admin")
    assert client.delete(f"/groups/{group}/posts/{post['id']}").status_code == 200
    assert client.get(endpoint + "?variant=thumbnail").status_code == 404
    assert UploadService(factory, storage, clock, config).cleanup() == 1
    assert not storage.objects


@pytest.mark.integration
def test_real_storage_legacy_backfill_quota_failure_resume_and_preservation(
    admin, factory, config, clock, monkeypatch
):
    user, group = admin
    config.s3_endpoint = os.environ["TEST_S3_ENDPOINT"]
    config.s3_bucket = "thumbnail-test-" + uuid.uuid4().hex
    storage = S3Storage(config)
    storage.client.create_bucket(Bucket=storage.bucket)
    service = UploadService(factory, storage, clock, config)
    source = io.BytesIO()
    Image.new("RGB", (1440, 1920), "green").save(source, "JPEG")
    try:
        post = service.accept(user, group, "photo", None, "legacy", io.BytesIO(source.getvalue()))
        with factory.begin() as db:
            row = db.scalar(select(Upload))
            original_key, old_thumbnail = row.object_key, row.thumbnail_key
            row.thumbnail_key = None
            row.thumbnail_ready = False
            db.get(Post, post.id).media_width = db.get(Post, post.id).media_height = None
        storage.delete(old_thumbnail)
        original = storage.client.get_object(Bucket=storage.bucket, Key=original_key)["Body"].read()
        config.storage_object_quota = 1
        with pytest.raises(Problem, match="storage_quota_exceeded"):
            backfill(factory, storage, config)
        config.storage_object_quota = 2
        put = storage.put

        def partial(key, path, content_type):
            put(key, path, content_type)
            raise OSError("Synthetic lost storage response")

        monkeypatch.setattr(storage, "put", partial)
        with pytest.raises(OSError):
            backfill(factory, storage, config)
        with factory.begin() as db:
            row = db.scalar(select(Upload))
            assert row.thumbnail_key and not row.thumbnail_ready and row.state == "accepted"
        monkeypatch.setattr(storage, "put", put)
        assert backfill(factory, storage, config) == 1
        assert backfill(factory, storage, config) == 0
        assert (
            storage.client.get_object(Bucket=storage.bucket, Key=original_key)["Body"].read()
            == original
        )
        with factory.begin() as db:
            row = db.scalar(select(Upload))
            saved = db.get(Post, post.id)
            assert saved.id == post.id and saved.fingerprint == row.fingerprint
            assert (saved.media_width, saved.media_height) == (1440, 1920)
            size = sum(
                obj["Size"]
                for obj in storage.client.list_objects_v2(Bucket=storage.bucket)["Contents"]
            )
            assert row.storage_bytes == size
    finally:
        for item in storage.client.list_objects_v2(Bucket=storage.bucket).get("Contents", []):
            storage.delete(item["Key"])
        storage.client.delete_bucket(Bucket=storage.bucket)
