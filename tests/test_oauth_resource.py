"""Automatic OAuth must bind every token request to the advertised resource."""

import asyncio
import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from gopher_mcp_python import oauth_resolver as resolver
from gopher_mcp_python.oauth_discovery import (
    McpOAuthChallenge,
    OAuthAuthorizationServerMetadata,
    OAuthProtectedResourceMetadata,
)
from gopher_mcp_python.oauth_token_store import (
    InMemoryGopherAgentTokenStore,
    create_oauth_token_cache_key,
)
from gopher_mcp_python.runtime_options import (
    GopherAgentOAuthOptions,
    GopherAgentTokenRecord,
)


@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize(
    "transport,resource",
    [
        ("https://mcp.example/servers/123/mcp", "https://mcp.example/servers/123"),
        ("https://mcp.example/gateways/123/mcp", "https://mcp.example/gateways/123/mcp"),
    ],
)
def test_automatic_oauth_uses_advertised_target(monkeypatch, refresh, transport, resource):
    resource_metadata = OAuthProtectedResourceMetadata(
        resource=resource, authorization_servers=["https://auth.example"],
        scopes_supported=["mcp:read"], raw_json="{}",
    )
    metadata = OAuthAuthorizationServerMetadata(
        issuer="https://auth.example",
        authorization_endpoint="https://auth.example/authorize",
        token_endpoint="https://auth.example/token",
        registration_endpoint="https://auth.example/register",
        scopes_supported=[], raw_json="{}",
    )
    opened = []
    token_requests = []
    closed = []

    class Response(io.BytesIO):
        def getcode(self):
            return 200

    def urlopen(request, **kwargs):
        if request.full_url == metadata.registration_endpoint:
            return Response(b'{"client_id":"test-client"}')
        assert request.full_url == metadata.token_endpoint
        params = parse_qs(request.data.decode())
        if params.get("resource") != [resource]:
            raise HTTPError(
                request.full_url, 400, "Bad Request", {},
                io.BytesIO(b'{"error":"invalid_target"}'),
            )
        token_requests.append(params)
        return Response(json.dumps({
            "access_token": "new-token", "token_type": "Bearer",
            "refresh_token": "refresh-token", "expires_in": 3600,
        }).encode())

    async def callback():
        return SimpleNamespace(code="test-code")

    async def close():
        closed.append(True)

    async def loopback(**kwargs):
        return SimpleNamespace(
            redirect_uri="http://127.0.0.1/callback", wait_for_callback=callback, close=close
        )

    def open_url(url, **kwargs):
        opened.append(url)
        return {"opened": True, "url": url}

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr(resolver, "fetch_oauth_protected_resource_metadata", lambda url: resource_metadata)
    monkeypatch.setattr(resolver, "fetch_oauth_authorization_server_metadata", lambda url: metadata)
    monkeypatch.setattr(resolver, "create_oauth_loopback_callback_server", loopback)
    monkeypatch.setattr(resolver, "open_authorization_url", open_url)
    store = InMemoryGopherAgentTokenStore()
    key = create_oauth_token_cache_key(
        resource=resource, issuer=metadata.issuer, client_id="test-client", scopes=["mcp:read"]
    )
    if refresh:
        asyncio.run(store.set(key, GopherAgentTokenRecord(
            access_token="expired", token_type="Bearer",
            refresh_token="refresh-token", expires_at=0,
        )))
    result = asyncio.run(resolver._default_acquire_token(
        [McpOAuthChallenge(
            url=transport, requires_oauth=True, http_status=401,
            resource_metadata_url="https://mcp.example/metadata",
        )],
        GopherAgentOAuthOptions(token_store=store),
    ))

    assert result.access_token == "new-token"
    assert len(token_requests) == 1
    assert token_requests[0]["grant_type"] == [
        "refresh_token" if refresh else "authorization_code"
    ]
    if refresh:
        assert opened == []
    else:
        assert parse_qs(urlparse(opened[0]).query)["resource"] == [resource]
    assert closed == [True]
    assert asyncio.run(store.get(key)).access_token == "new-token"
