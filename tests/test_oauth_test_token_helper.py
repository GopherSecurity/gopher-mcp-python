"""Tests for generic test OAuth token helper."""

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler

import pytest

from tests.helpers.oauth_test_token import refresh_test_oauth_token
from tests.test_oauth_discovery import _start_server


CLIENT_ID = "test-client"
CLIENT_SECRET = "test-secret"
REFRESH_TOKEN = "test-refresh-token"
ACCESS_TOKEN = "test-access-token"


def test_refresh_test_oauth_token_posts_refresh_grant() -> None:
    captured = {}

    def handle(handler: BaseHTTPRequestHandler) -> None:
        length = int(handler.headers.get("Content-Length", "0"))
        body = handler.rfile.read(length).decode("utf-8")
        captured["content_type"] = handler.headers.get("Content-Type")
        captured["params"] = urllib.parse.parse_qs(body)
        _json(
            handler,
            200,
            {
                "access_token": ACCESS_TOKEN,
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "openid profile email",
            },
        )

    server = _start_server(handle)
    try:
        token = refresh_test_oauth_token(
            token_endpoint=f"{server.url}/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            refresh_token=REFRESH_TOKEN,
        )
    finally:
        server.close()

    assert token.access_token == ACCESS_TOKEN
    assert token.token_type == "Bearer"
    assert token.expires_in == 3600
    assert token.scope == "openid profile email"
    assert captured["content_type"] == "application/x-www-form-urlencoded"
    assert captured["params"]["grant_type"] == ["refresh_token"]
    assert captured["params"]["client_id"] == [CLIENT_ID]
    assert captured["params"]["client_secret"] == [CLIENT_SECRET]
    assert captured["params"]["refresh_token"] == [REFRESH_TOKEN]


@pytest.mark.parametrize(
    ("error", "status"),
    [
        ("invalid_grant", 400),
        ("invalid_client", 401),
        ("unsupported_grant_type", 400),
    ],
)
def test_refresh_test_oauth_token_surfaces_oauth_errors_without_secrets(
    error: str, status: int
) -> None:
    server = _start_server(
        lambda handler: _json(
            handler,
            status,
            {
                "error": error,
                "error_description": (
                    f"{CLIENT_SECRET} {REFRESH_TOKEN} {ACCESS_TOKEN}"
                ),
            },
        )
    )
    try:
        with pytest.raises(RuntimeError) as exc_info:
            refresh_test_oauth_token(
                token_endpoint=f"{server.url}/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                refresh_token=REFRESH_TOKEN,
            )
    finally:
        server.close()

    message = str(exc_info.value)
    assert error in message
    assert CLIENT_SECRET not in message
    assert REFRESH_TOKEN not in message
    assert ACCESS_TOKEN not in message


def test_refresh_test_oauth_token_surfaces_non_oauth_http_error() -> None:
    server = _start_server(lambda handler: _json(handler, 500, {}))
    try:
        with pytest.raises(RuntimeError, match="HTTP 500"):
            refresh_test_oauth_token(
                token_endpoint=f"{server.url}/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                refresh_token=REFRESH_TOKEN,
            )
    finally:
        server.close()


def test_refresh_test_oauth_token_requires_access_token() -> None:
    server = _start_server(
        lambda handler: _json(handler, 200, {"token_type": "Bearer"})
    )
    try:
        with pytest.raises(RuntimeError, match="missing access_token"):
            refresh_test_oauth_token(
                token_endpoint=f"{server.url}/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                refresh_token=REFRESH_TOKEN,
            )
    finally:
        server.close()


def test_refresh_test_oauth_token_requires_token_type() -> None:
    server = _start_server(
        lambda handler: _json(handler, 200, {"access_token": ACCESS_TOKEN})
    )
    try:
        with pytest.raises(RuntimeError, match="missing token_type"):
            refresh_test_oauth_token(
                token_endpoint=f"{server.url}/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                refresh_token=REFRESH_TOKEN,
            )
    finally:
        server.close()


def test_refresh_test_oauth_token_rejects_invalid_json() -> None:
    server = _start_server(lambda handler: _raw(handler, 200, b"not json"))
    try:
        with pytest.raises(RuntimeError, match="invalid JSON"):
            refresh_test_oauth_token(
                token_endpoint=f"{server.url}/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                refresh_token=REFRESH_TOKEN,
            )
    finally:
        server.close()


def test_refresh_test_oauth_token_rejects_non_object_json() -> None:
    server = _start_server(lambda handler: _raw(handler, 200, b"[]"))
    try:
        with pytest.raises(RuntimeError, match="invalid JSON"):
            refresh_test_oauth_token(
                token_endpoint=f"{server.url}/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                refresh_token=REFRESH_TOKEN,
            )
    finally:
        server.close()


def _json(handler: BaseHTTPRequestHandler, status: int, body: object) -> None:
    _raw(handler, status, json.dumps(body).encode("utf-8"))


def _raw(handler: BaseHTTPRequestHandler, status: int, body: bytes) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
