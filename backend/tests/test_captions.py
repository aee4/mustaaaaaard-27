import io

import pytest
from sqlalchemy import select

from app.core.errors import Problem
from app.models.entities import Post, Upload
from app.services.uploads import UploadService, normalize_caption
from tests.conftest import photo, upload


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        (" \n\t", None),
        ("  Final year, same people.  ", "Final year, same people."),
        ("Akwaaba 🌼\nOur season.", "Akwaaba 🌼\nOur season."),
        ("First\r\nSecond\rThird", "First\nSecond\nThird"),
    ],
)
def test_caption_normalization(value, expected):
    assert normalize_caption(value) == expected


@pytest.mark.parametrize("value", ["a" * 281, "bad\x00text", "bad\x1btext", "\ud800"])
def test_caption_validation(value):
    with pytest.raises(Problem) as error:
        normalize_caption(value)
    assert error.value.code == "invalid_caption"


@pytest.mark.integration
@pytest.mark.parametrize("gallery", [False, True])
def test_caption_upload_feed_retry_and_deletion(client, admin, factory, gallery):
    _, group = admin
    cap = (
        None
        if gallery
        else client.post(f"/groups/{group}/captures", json={"kind": "photo"}).json()["id"]
    )
    text = '<script>alert("no HTML")</script>\nFinal year, same people. 🌼'
    first = upload(
        client, group, photo(), gallery=gallery, capture=cap, key="caption", caption=f"  {text}  "
    )
    assert first.status_code == 200, first.text
    assert first.json()["caption"] == text
    replay = upload(
        client, group, photo(), gallery=gallery, capture=cap, key="caption", caption=text
    )
    assert replay.json() == first.json()
    conflict = upload(
        client,
        group,
        photo(),
        gallery=gallery,
        capture=cap,
        key="caption",
        caption="Changed caption",
    )
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
    )
    assert client.get(f"/groups/{group}/feed").json()["items"][0]["caption"] == text
    assert first.json()["points"] == (0 if gallery else 1)
    assert client.delete(f"/groups/{group}/posts/{first.json()['id']}").status_code == 200
    replay = upload(
        client, group, photo(), gallery=gallery, capture=cap, key="caption", caption=text
    )
    assert replay.json()["removed"] and replay.json()["caption"] is None
    with factory.begin() as db:
        assert db.scalar(select(Post)).caption is None
        assert db.scalar(select(Upload)).caption_hash is not None


@pytest.mark.integration
def test_invalid_caption_never_accepts_media_and_duplicate_hash_ignores_caption(client, admin):
    _, group = admin
    invalid = upload(client, group, photo(), gallery=True, caption="a" * 281)
    assert invalid.status_code == 422
    assert upload(client, group, photo(), gallery=True, caption="bad\x00text").status_code == 422
    assert client.get(f"/groups/{group}/feed").json()["items"] == []
    assert upload(client, group, photo(), gallery=True, caption="a" * 280).status_code == 200
    duplicate = upload(
        client, group, photo(), gallery=True, caption="Different caption, same original bytes"
    )
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "duplicate_media"


@pytest.mark.integration
def test_multiline_form_limit_and_blank_replay(client, admin):
    _, group = admin
    # Browser multipart CRLF must normalize before the 280-character constraint.
    value = "a\r\n" * 139 + "ab"
    result = upload(client, group, photo(), gallery=True, key="lines", caption=value)
    assert result.status_code == 200, result.text
    assert result.json()["caption"] == "a\n" * 139 + "ab"
    first = upload(client, group, photo("red"), gallery=True, key="blank")
    replay = upload(client, group, photo("red"), gallery=True, key="blank", caption=" \r\n\t")
    assert replay.status_code == 200 and replay.json() == first.json()
    assert replay.json()["caption"] is None


@pytest.mark.integration
def test_caption_survives_storage_failure_retry(admin, factory, storage, clock, config):
    user, group = admin
    service = UploadService(factory, storage, clock, config)
    storage.fail_put = True
    with pytest.raises(Problem):
        service.accept(
            user, group, "photo", None, "failed-caption", io.BytesIO(photo()), "Our last year"
        )
    storage.fail_put = False
    with pytest.raises(Problem) as conflict:
        service.accept(
            user, group, "photo", None, "failed-caption", io.BytesIO(photo()), "Different"
        )
    assert conflict.value.code == "idempotency_conflict"
    assert (
        service.accept(
            user, group, "photo", None, "failed-caption", io.BytesIO(photo()), "Our last year"
        ).caption
        == "Our last year"
    )
