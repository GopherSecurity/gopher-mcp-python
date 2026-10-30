"""Shared scope policy and its use across an automatic authorization flow."""

import asyncio
from email.message import Message
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from gopher_mcp_python import select_oauth_scopes
from gopher_mcp_python import oauth_resolver as resolver
from gopher_mcp_python.oauth_discovery import (
    McpOAuthChallenge,
    OAuthAuthorizationServerMetadata,
    OAuthProtectedResourceMetadata,
    probe_mcp_oauth_challenge,
)
from gopher_mcp_python.oauth_registration import OAuthRegisteredClient
from gopher_mcp_python.oauth_token_store import InMemoryGopherAgentTokenStore
from gopher_mcp_python.runtime_options import GopherAgentOAuthOptions, GopherAgentTokenRecord


@pytest.mark.parametrize(
    "challenge,explicit,resource,expected",
    [
        (["mcp:required"], ["email"], ["mcp:other"], ["mcp:required"]),
        ([], ["email"], ["mcp:other"], []),
        (None, ["email"], ["mcp:other"], ["email"]),
        (None, [], ["mcp:other"], []),
        (None, None, ["mcp:read"], ["mcp:read"]),
        (None, None, [], []),
        (None, None, None, []),
    ],
)
def test_shared_scope_policy(challenge, explicit, resource, expected):
    assert select_oauth_scopes(
        challenge_scopes=challenge, scopes=explicit, resource_scopes=resource
    ) == expected


@pytest.mark.parametrize("scope", [None, "", "mcp:read mcp:write"])
def test_discovery_preserves_challenge_scope(monkeypatch, scope):
    headers = Message()
    challenge = 'Bearer resource_metadata="https://mcp.example/metadata"'
    if scope is not None:
        challenge += f', scope="{scope}"'
    headers["WWW-Authenticate"] = challenge

    def unauthorized(*args, **kwargs):
        raise HTTPError("https://mcp.example/mcp", 401, "Unauthorized", headers, None)

    monkeypatch.setattr("urllib.request.urlopen", unauthorized)
    result = probe_mcp_oauth_challenge("https://mcp.example/mcp")

    assert result.scopes == (scope.split() if scope is not None else None)


@pytest.mark.parametrize(
    "challenge_scopes,resource_scopes,expected",
    [
        (["mcp:challenged"], ["mcp:resource"], ["mcp:challenged"]),
        ([], ["mcp:resource"], []),
        (None, ["mcp:resource"], ["mcp:resource"]),
        (None, [], []),
    ],
)
def test_registration_and_authorization_use_same_scopes(
    monkeypatch, challenge_scopes, resource_scopes, expected
):
    resource = OAuthProtectedResourceMetadata(
        resource="https://mcp.example/mcp",
        authorization_servers=["https://auth.example"],
        scopes_supported=resource_scopes,
        raw_json="{}",
    )
    metadata = OAuthAuthorizationServerMetadata(
        issuer="https://auth.example",
        authorization_endpoint="https://auth.example/authorize?scope=realm-only:admin",
        token_endpoint="https://auth.example/token",
        scopes_supported=["realm-only:admin", "unrelated:server"],
        raw_json="{}",
    )
    registered = []
    opened = []

    async def callback():
        return SimpleNamespace(code="test-code")

    async def close():
        pass

    async def loopback(**kwargs):
        return SimpleNamespace(
            redirect_uri="http://127.0.0.1/callback", wait_for_callback=callback, close=close
        )

    def register(**kwargs):
        registered.append(kwargs["scopes"])
        return OAuthRegisteredClient(client_id="test-client")

    def open_url(url, **kwargs):
        opened.append(url)
        return {"opened": True, "url": url}

    monkeypatch.setattr(resolver, "fetch_oauth_protected_resource_metadata", lambda url: resource)
    monkeypatch.setattr(resolver, "fetch_oauth_authorization_server_metadata", lambda url: metadata)
    monkeypatch.setattr(resolver, "create_oauth_loopback_callback_server", loopback)
    monkeypatch.setattr(resolver, "register_oauth_client", register)
    monkeypatch.setattr(resolver, "open_authorization_url", open_url)
    monkeypatch.setattr(
        resolver, "exchange_oauth_code_for_token",
        lambda **kwargs: GopherAgentTokenRecord(access_token="test-token", token_type="Bearer"),
    )
    result = asyncio.run(resolver._default_acquire_token(
        [McpOAuthChallenge(
            url=resource.resource, requires_oauth=True, http_status=401,
            resource_metadata_url="https://mcp.example/metadata", scopes=challenge_scopes,
        )],
        GopherAgentOAuthOptions(token_store=InMemoryGopherAgentTokenStore()),
    ))

    assert result.access_token == "test-token"
    assert registered == [expected]
    assert parse_qs(urlparse(opened[0]).query).get("scope") == (
        [" ".join(expected)] if expected else None
    )
