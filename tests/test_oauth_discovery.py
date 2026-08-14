"""Tests for OAuth discovery helpers."""

import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from gopher_mcp_python.oauth_discovery import (
    fetch_oauth_authorization_server_metadata,
    fetch_oauth_protected_resource_metadata,
    parse_www_authenticate_param,
    probe_mcp_oauth_challenge,
)


def test_parses_quoted_resource_metadata() -> None:
    challenge = 'Bearer realm="mcp", resource_metadata="https://mcp.example.com/meta"'

    assert (
        parse_www_authenticate_param(challenge, "resource_metadata")
        == "https://mcp.example.com/meta"
    )


def test_probe_treats_2xx_as_no_oauth() -> None:
    server = _start_server(lambda handler: _json(handler, 200, {}))
    try:
        result = probe_mcp_oauth_challenge(f"{server.url}/mcp")
    finally:
        server.close()

    assert result.requires_oauth is False
    assert result.http_status == 200


def test_probe_returns_oauth_challenge() -> None:
    def handle(handler):
        handler.send_response(401)
        handler.send_header(
            "WWW-Authenticate",
            f'Bearer realm="mcp", resource_metadata="{server.url}/resource"',
        )
        handler.end_headers()

    server = _start_server(handle)
    try:
        result = probe_mcp_oauth_challenge(f"{server.url}/mcp")
    finally:
        server.close()

    assert result.requires_oauth is True
    assert result.resource_metadata_url == f"{server.url}/resource"


def test_probe_uses_gopher_hosted_oauth_fallback_for_prod_404(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _raise_http_404)
    hosted_url = "https://mcp.gopher.security/v1/mcp/servers/example/mcp"
    result = probe_mcp_oauth_challenge(hosted_url)

    assert result.requires_oauth is True
    assert result.http_status == 404
    assert (
        result.authorization_server
        == "https://auth.gopher.security/realms/gopher-mcp"
    )
    assert result.registration_endpoint == "https://api.gopher.security/oauth/register"
    assert result.resource == hosted_url
    assert result.scopes == ["openid", "profile", "email"]


def test_probe_uses_gopher_hosted_oauth_fallback_for_test_404(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", _raise_http_404)
    hosted_url = "https://mcp-test.gopher.security/v1/mcp/servers/example/mcp"
    result = probe_mcp_oauth_challenge(hosted_url)

    assert result.requires_oauth is True
    assert result.http_status == 404
    assert (
        result.authorization_server
        == "https://auth-test.gopher.security/realms/gopher-mcp"
    )
    assert result.registration_endpoint == "https://api-test.gopher.security/oauth/register"
    assert result.resource == hosted_url
    assert result.scopes == ["openid", "profile", "email"]


def test_probe_non_gopher_404_still_fails() -> None:
    server = _start_server(lambda handler: _json(handler, 404, {}))
    try:
        with pytest.raises(RuntimeError, match="received HTTP 404"):
            probe_mcp_oauth_challenge(f"{server.url}/mcp")
    finally:
        server.close()


def test_probe_missing_resource_metadata_fails() -> None:
    def handle(handler):
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Bearer realm="mcp"')
        handler.end_headers()

    server = _start_server(handle)
    try:
        with pytest.raises(RuntimeError, match="missing resource_metadata"):
            probe_mcp_oauth_challenge(f"{server.url}/mcp")
    finally:
        server.close()


def test_fetches_protected_resource_metadata() -> None:
    server = _start_server(
        lambda handler: _json(
            handler,
            200,
            {
                "resource": "https://mcp.example.com/mcp",
                "authorization_servers": ["https://auth.example.com"],
                "scopes_supported": ["openid"],
            },
        )
    )
    try:
        metadata = fetch_oauth_protected_resource_metadata(f"{server.url}/resource")
    finally:
        server.close()

    assert metadata.resource == "https://mcp.example.com/mcp"
    assert metadata.authorization_servers == ["https://auth.example.com"]
    assert metadata.scopes_supported == ["openid"]


def test_fetches_authorization_server_metadata_with_oidc_fallback() -> None:
    def handle(handler):
        if handler.path.startswith("/.well-known/oauth-authorization-server"):
            _json(handler, 404, {})
            return
        _json(
            handler,
            200,
            {
                "issuer": server.url,
                "authorization_endpoint": f"{server.url}/authorize",
                "token_endpoint": f"{server.url}/token",
                "registration_endpoint": f"{server.url}/register",
                "scopes_supported": ["openid"],
            },
        )

    server = _start_server(handle)
    try:
        metadata = fetch_oauth_authorization_server_metadata(server.url)
    finally:
        server.close()

    assert metadata.issuer == server.url
    assert metadata.authorization_endpoint == f"{server.url}/authorize"
    assert metadata.token_endpoint == f"{server.url}/token"
    assert metadata.registration_endpoint == f"{server.url}/register"


def test_fetches_path_based_oidc_metadata() -> None:
    issuer = ""

    def handle(handler):
        if handler.path.startswith("/.well-known/oauth-authorization-server"):
            _json(handler, 404, {})
            return
        if handler.path != "/realms/gopher-mcp/.well-known/openid-configuration":
            _json(handler, 404, {})
            return
        _json(
            handler,
            200,
            {
                "issuer": issuer,
                "authorization_endpoint": f"{issuer}/protocol/openid-connect/auth",
                "token_endpoint": f"{issuer}/protocol/openid-connect/token",
                "registration_endpoint": f"{issuer}/clients-registrations/openid-connect",
                "scopes_supported": ["openid"],
            },
        )

    server = _start_server(handle)
    issuer = f"{server.url}/realms/gopher-mcp"
    try:
        metadata = fetch_oauth_authorization_server_metadata(issuer)
    finally:
        server.close()

    assert metadata.issuer == issuer
    assert metadata.authorization_endpoint == f"{issuer}/protocol/openid-connect/auth"
    assert metadata.token_endpoint == f"{issuer}/protocol/openid-connect/token"


class _Server:
    def __init__(self, server):
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        self.url = f"http://127.0.0.1:{server.server_address[1]}"

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)


def _start_server(callback):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def do_GET(self):
            callback(self)

        def do_POST(self):
            callback(self)

    return _Server(ThreadingHTTPServer(("127.0.0.1", 0), Handler))


def _raise_http_404(request, timeout):
    raise urllib.error.HTTPError(
        request.full_url,
        404,
        "Not Found",
        {},
        None,
    )


def _json(handler, status, body):
    data = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
