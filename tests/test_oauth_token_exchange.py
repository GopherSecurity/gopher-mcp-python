"""Tests for OAuth token exchange helpers."""

import base64
import urllib.parse

import pytest

from tests.test_oauth_discovery import _json, _start_server

from gopher_mcp_python.oauth_token_exchange import (
    build_oauth_code_exchange_request,
    exchange_oauth_code_for_token,
    refresh_oauth_token,
)


def test_preparing_exchange_does_not_send_request(monkeypatch):
    def unexpected_network(*args, **kwargs):
        raise AssertionError("Request preparation must not perform network I/O")

    monkeypatch.setattr("urllib.request.urlopen", unexpected_network)
    request = build_oauth_code_exchange_request(
        code="code", redirect_uri="http://127.0.0.1/callback",
        code_verifier="verifier", token_endpoint="https://auth.example/token",
        client_id="cid", resource="https://mcp.example/servers/123",
    )
    assert request.data["resource"] == "https://mcp.example/servers/123"
    assert request.token_endpoint == "https://auth.example/token"


@pytest.mark.parametrize("method", [None, "client_secret_post", "client_secret_basic"])
def test_exchange_uses_registered_client_authentication(method):
    captured = {}

    def handle(handler):
        length = int(handler.headers.get("Content-Length", "0"))
        captured["form"] = urllib.parse.parse_qs(handler.rfile.read(length).decode())
        captured["authorization"] = handler.headers.get("Authorization")
        _json(handler, 200, {"access_token": "access", "token_type": "Bearer"})

    server = _start_server(handle)
    try:
        exchange_oauth_code_for_token(
            code="code", redirect_uri="http://127.0.0.1/callback",
            code_verifier="verifier", token_endpoint=f"{server.url}/token",
            client_id="cid", client_secret="secret",
            resource="https://mcp.example/servers/123",
            token_endpoint_auth_method=method,
        )
    finally:
        server.close()

    assert captured["form"]["resource"] == ["https://mcp.example/servers/123"]
    if method == "client_secret_basic":
        credentials = base64.b64encode(b"cid:secret").decode()
        assert captured["authorization"] == f"Basic {credentials}"
        assert "client_secret" not in captured["form"]
    else:
        assert captured["form"]["client_secret"] == ["secret"]
        assert captured["authorization"] is None


@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize(
    "resource",
    [None, "https://mcp.example/servers/123", "https://mcp.example/gateways/123/mcp"],
)
def test_token_request_resource_is_preserved(refresh, resource):
    captured = {}

    def handle(handler):
        length = int(handler.headers.get("Content-Length", "0"))
        captured.update(urllib.parse.parse_qs(handler.rfile.read(length).decode()))
        _json(handler, 200, {"access_token": "access", "token_type": "Bearer"})

    server = _start_server(handle)
    try:
        common = {
            "token_endpoint": f"{server.url}/token",
            "client_id": "cid",
            "resource": resource,
        }
        if refresh:
            refresh_oauth_token(refresh_token="refresh", **common)
        else:
            exchange_oauth_code_for_token(
                code="code", redirect_uri="http://127.0.0.1/callback",
                code_verifier="verifier", **common,
            )
    finally:
        server.close()

    assert captured.get("resource") == ([resource] if resource is not None else None)


def test_exchange_code_returns_token_record() -> None:
    captured = {}

    def handle(handler):
        length = int(handler.headers.get("Content-Length", "0"))
        body = handler.rfile.read(length).decode("utf-8")
        captured["params"] = urllib.parse.parse_qs(body)
        _json(
            handler,
            200,
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "token_type": "Bearer",
                "expires_in": 60,
                "scope": "openid",
            },
        )

    server = _start_server(handle)
    try:
        token = exchange_oauth_code_for_token(
            code="code",
            redirect_uri="http://127.0.0.1/callback",
            code_verifier="verifier",
            token_endpoint=f"{server.url}/token",
            client_id="cid",
            now_ms=1000,
        )
    finally:
        server.close()

    assert token.access_token == "access"
    assert token.refresh_token == "refresh"
    assert token.expires_at == 61000
    assert captured["params"]["code_verifier"] == ["verifier"]


def test_refresh_token_returns_token_record() -> None:
    server = _start_server(
        lambda handler: _json(
            handler,
            200,
            {"access_token": "new-access", "token_type": "Bearer"},
        )
    )
    try:
        token = refresh_oauth_token(
            refresh_token="refresh",
            token_endpoint=f"{server.url}/token",
            client_id="cid",
        )
    finally:
        server.close()

    assert token.access_token == "new-access"


def test_token_error_preserves_description() -> None:
    server = _start_server(
        lambda handler: _json(
            handler,
            400,
            {"error": "invalid_grant", "error_description": "bad code"},
        )
    )
    try:
        with pytest.raises(RuntimeError, match="bad code"):
            exchange_oauth_code_for_token(
                code="bad",
                redirect_uri="http://127.0.0.1/callback",
                code_verifier="verifier",
                token_endpoint=f"{server.url}/token",
                client_id="cid",
            )
    finally:
        server.close()
