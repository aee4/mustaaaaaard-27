import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from authlib.integrations.starlette_client import OAuth
from joserfc import jwt
from joserfc.jwk import RSAKey

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("fault", [None, "state", "nonce", "iss", "aud", "exp", "signature"])
def test_oidc_state_nonce_pkce_and_signed_identity(application, client, factory, fault):
    key = RSAKey.generate_key(2048, parameters={"kid": "test-signing-key"})
    public = key.as_dict(private=False)
    nonce = ""
    exchanged = []

    def provider(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://issuer.test/token"
        params = parse_qs(request.content.decode())
        assert len(params["code_verifier"][0]) >= 43
        assert params["code"] == ["test-code"]
        exchanged.append(True)
        claims = dict(
            iss="https://issuer.test",
            sub="stable-subject",
            aud="test-client",
            iat=int(time.time()),
            exp=int(time.time()) + 600,
            nonce=nonce,
            name="Google Friend",
        )
        if fault == "nonce":
            claims["nonce"] = "wrong-nonce"
        elif fault == "iss":
            claims["iss"] = "https://attacker.test"
        elif fault == "aud":
            claims["aud"] = "different-client"
        elif fault == "exp":
            claims["exp"] = int(time.time()) - 600
        signing_key = (
            RSAKey.generate_key(2048, parameters={"kid": "test-signing-key"})
            if fault == "signature"
            else key
        )
        token = jwt.encode({"alg": "RS256", "kid": "test-signing-key"}, claims, signing_key)
        return httpx.Response(
            200,
            json={
                "access_token": "provider-access-token",
                "token_type": "Bearer",
                "id_token": token,
            },
        )

    application.state.settings.google_client_id = "test-client"
    application.state.oauth = OAuth()
    application.state.oauth.register(
        name="google",
        overwrite=True,
        client_id="test-client",
        client_secret="test-secret",
        authorize_url="https://issuer.test/authorize",
        access_token_url="https://issuer.test/token",
        issuer="https://issuer.test",
        jwks={"keys": [public]},
        id_token_signing_alg_values_supported=["RS256"],
        client_kwargs={
            "scope": "openid profile",
            "code_challenge_method": "S256",
            "transport": httpx.MockTransport(provider),
        },
    )
    start = client.get(
        "/auth/google", params={"return_to": "/profile?invite=synthetic"}, follow_redirects=False
    )
    assert start.status_code == 302
    query = parse_qs(urlsplit(start.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) == 43
    nonce = query["nonce"][0]
    callback = client.get(
        "/auth/google/callback",
        params={"code": "test-code", "state": "wrong" if fault == "state" else query["state"][0]},
        follow_redirects=False,
    )
    if fault:
        assert callback.status_code == 401, callback.text
        assert client.get("/auth/session").status_code == 401
    else:
        assert callback.status_code == 303
        assert callback.headers["location"].endswith("/profile?invite=synthetic")
        assert "HttpOnly" in callback.headers["set-cookie"]
        session = client.get("/auth/session").json()
        assert session["user"]["display_name"] == "Google Friend"
        from sqlalchemy import select

        from app.models.entities import User

        with factory.begin() as db:
            user = db.scalar(select(User))
            assert user.subject == "google:stable-subject"
        assert "provider-access-token" not in str(callback.headers)
    assert bool(exchanged) == (fault != "state")


@pytest.mark.parametrize("destination", ["//evil.test", "https://evil.test", "/\\evil.test", "/\n"])
def test_oauth_destination_cannot_escape_app(application, client, destination):
    class Provider:
        async def authorize_redirect(self, request, callback):
            from starlette.responses import JSONResponse

            return JSONResponse({"destination": request.session["return_to"], "callback": callback})

    class Registry:
        google = Provider()

    application.state.settings.google_client_id = "test-client"
    application.state.oauth = Registry()
    result = client.get("/auth/google", params={"return_to": destination})
    assert result.json()["destination"] == "/"
