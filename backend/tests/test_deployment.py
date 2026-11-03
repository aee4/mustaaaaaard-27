import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import app.cli as commands
from app.core.config import Settings
from app.main import create_app
from app.services.identity import login
from app.web import create_web_app


def production_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="production",
        cookie_secure=True,
        dev_auth=False,
        secret_key="test-only-production-configuration-1234567890",
        base_url="https://mustard-test.onrender.com",
        allowed_origins=["https://mustard-test.onrender.com"],
        google_client_id="test-client",
        google_client_secret="test-secret",
        s3_endpoint="https://s3.example.test",
        s3_access_key="test-key",
        s3_secret_key="test-storage-secret",
        database_url="postgresql://user:pass@localhost/test",
    )


@pytest.fixture
def web_files(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text("<html>real build marker</html>")
    (tmp_path / "asset.js").write_text("export const built = true")
    return tmp_path


def test_production_driver_and_origin_validation():
    config = production_settings()
    assert config.database_url.startswith("postgresql+psycopg://")
    for value in ["https://app.test/path", "https://user@app.test", "https://app.test?x=y"]:
        with pytest.raises(ValueError):
            Settings(**{**config.model_dump(), "base_url": value})
    for host in ["*", "https://backend.test", "backend.test:443", "*.onrender.com"]:
        with pytest.raises(ValueError):
            Settings(**{**config.model_dump(), "backend_hosts": [host]})


def test_production_r2_requires_explicit_acknowledgement_and_quotas():
    config = production_settings().model_dump()
    config["s3_endpoint"] = "https://account.r2.cloudflarestorage.com"
    with pytest.raises(ValueError, match="acknowledgement"):
        Settings(**config)
    config.update(
        r2_billing_acknowledged=True, storage_quota_bytes=8000000000, storage_object_quota=10000
    )
    assert Settings(**config).r2_billing_acknowledged


def test_configuration_errors_hide_secret_values():
    config = production_settings().model_dump()
    config.update(dev_auth=True, google_client_secret="do-not-print-this-secret")
    with pytest.raises(ValueError) as failure:
        Settings(**config)
    assert "do-not-print-this-secret" not in str(failure.value)


@pytest.mark.integration
def test_same_origin_artifact_routes_and_host_guard(web_files, factory, storage, clock):
    config = production_settings()
    config.backend_hosts = ["fallback.onrender.com"]
    web = create_web_app(config, web_files, create_app(config, factory, storage, clock))
    with TestClient(web, base_url=config.base_url) as client:
        for path in ["/", "/capture", "/leaderboard", "/profile"]:
            result = client.get(path)
            assert result.status_code == 200 and "real build marker" in result.text
            assert result.headers["strict-transport-security"] == "max-age=31536000"
        assert client.get("/asset.js").status_code == 200
        assert client.get("/missing.js").status_code == 404
        assert client.get("/.env").status_code == 404
        assert client.get("/api/no-such-endpoint").status_code == 404
        assert client.get("/api/auth/session").status_code == 401
        assert (
            client.post(
                "/api/auth/dev", json={"subject": "alice", "display_name": "Alice"}
            ).status_code
            == 404
        )
        assert client.get("/", headers={"host": "evil.example"}).status_code == 400
        assert client.get("/health", headers={"host": "fallback.onrender.com"}).status_code == 200


@pytest.mark.integration
def test_mounted_session_cookie_csrf_and_group_creation(web_files, config, factory, storage, clock):
    config.base_url = "https://localhost"
    config.cookie_secure = True
    config.allowed_origins = [config.base_url]
    api = create_app(config, factory, storage, clock)
    with TestClient(create_web_app(config, web_files, api), base_url=config.base_url) as client:
        response = client.post(
            "/api/auth/dev",
            json={"subject": "mounted", "display_name": "Owner"},
            headers={"Origin": config.base_url},
        )
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert (
            "secure" in cookie
            and "httponly" in cookie
            and "samesite=lax" in cookie
            and "path=/" in cookie
        )
        session = client.get("/api/auth/session").json()
        headers = {"Origin": config.base_url, "X-CSRF-Token": session["csrf_token"]}
        assert client.post("/api/groups", json={"name": "Mounted group"}).status_code == 403
        assert (
            client.post(
                "/api/groups",
                json={"name": "Mounted group"},
                headers={**headers, "Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        assert (
            client.post("/api/groups", json={"name": "Mounted group"}, headers=headers).status_code
            == 201
        )
        assert client.get("/api/groups").json()[0]["role"] == "admin"
        assert client.post("/api/auth/logout", headers=headers).status_code == 200
        assert client.get("/api/auth/session").status_code == 401


@pytest.mark.integration
def test_operator_bootstrap_requires_existing_google_user(factory, clock, monkeypatch):
    google, _, _ = login(factory, "google:verified-owner", "Owner", clock.now(), 600)
    dev, _, _ = login(factory, "dev:alice", "Alice", clock.now(), 600)
    monkeypatch.setattr(commands, "SessionLocal", factory)
    monkeypatch.setattr(commands, "get_settings", production_settings)
    runner = CliRunner()
    assert (
        runner.invoke(commands.cli, ["bootstrap-user", "--user-id", str(uuid.uuid4())]).exit_code
        != 0
    )
    assert runner.invoke(commands.cli, ["bootstrap-user", "--user-id", str(dev.id)]).exit_code != 0
    assert (
        runner.invoke(commands.cli, ["bootstrap-user", "--user-id", str(google.id)]).exit_code == 0
    )
