"""Tests for OAuth dynamic registration."""

from tests.test_oauth_discovery import _json, _start_server

from gopher_mcp_python.oauth_discovery import OAuthAuthorizationServerMetadata
from gopher_mcp_python.oauth_registration import register_oauth_client
from gopher_mcp_python.runtime_options import GopherAgentOAuthOptions


def test_register_oauth_client_sends_redirect_uri_and_scopes() -> None:
    captured = {}

    def handle(handler):
        length = int(handler.headers.get("Content-Length", "0"))
        captured["body"] = handler.rfile.read(length).decode("utf-8")
        _json(handler, 200, {"client_id": "cid", "client_secret": "secret"})

    server = _start_server(handle)
    try:
        client = register_oauth_client(
            metadata=OAuthAuthorizationServerMetadata(
                issuer=server.url,
                authorization_endpoint=f"{server.url}/authorize",
                token_endpoint=f"{server.url}/token",
                registration_endpoint=f"{server.url}/register",
                scopes_supported=[],
                raw_json="{}",
            ),
            redirect_uri="http://127.0.0.1/callback",
            scopes=["openid"],
            oauth=GopherAgentOAuthOptions(client_name="Test Client"),
        )
    finally:
        server.close()

    assert client.client_id == "cid"
    assert client.client_secret == "secret"
    assert "http://127.0.0.1/callback" in captured["body"]
    assert "openid" in captured["body"]


def test_register_oauth_client_requires_registration_endpoint() -> None:
    metadata = OAuthAuthorizationServerMetadata(
        issuer="https://auth.example.com",
        authorization_endpoint="https://auth.example.com/authorize",
        token_endpoint="https://auth.example.com/token",
        scopes_supported=[],
        raw_json="{}",
    )

    try:
        register_oauth_client(metadata, "http://127.0.0.1/callback", [])
    except RuntimeError as exc:
        assert "oauth_registration_required" in str(exc)
    else:
        raise AssertionError("expected registration failure")
