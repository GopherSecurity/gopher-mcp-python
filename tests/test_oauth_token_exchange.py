"""Tests for OAuth token exchange helpers."""

import urllib.parse

import pytest

from tests.test_oauth_discovery import _json, _start_server

from gopher_mcp_python.oauth_token_exchange import (
    exchange_oauth_code_for_token,
    refresh_oauth_token,
)


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
