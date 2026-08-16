"""Tests for OAuth authorization URL construction."""

from urllib.parse import parse_qs, urlparse

from gopher_mcp_python.oauth_authorization_url import build_oauth_authorization_url
from gopher_mcp_python.oauth_discovery import (
    OAuthAuthorizationServerMetadata,
    OAuthProtectedResourceMetadata,
)


METADATA = OAuthAuthorizationServerMetadata(
    issuer="https://auth.example.com",
    authorization_endpoint="https://auth.example.com/authorize?prompt=consent",
    token_endpoint="https://auth.example.com/token",
    scopes_supported=["openid", "profile"],
    raw_json="{}",
)


def _params(url: str):
    return parse_qs(urlparse(url).query)


def test_includes_all_required_params() -> None:
    search = _params(
        build_oauth_authorization_url(
            metadata=METADATA,
            client_id="client-123",
            redirect_uri="http://127.0.0.1:49152/callback",
            state="state-123",
            code_challenge="challenge-123",
        )
    )

    assert search["response_type"] == ["code"]
    assert search["client_id"] == ["client-123"]
    assert search["redirect_uri"] == ["http://127.0.0.1:49152/callback"]
    assert search["state"] == ["state-123"]
    assert search["code_challenge"] == ["challenge-123"]
    assert search["code_challenge_method"] == ["S256"]


def test_scope_defaults_from_options_first() -> None:
    search = _params(
        build_oauth_authorization_url(
            metadata=METADATA,
            client_id="client-123",
            redirect_uri="http://127.0.0.1:49152/callback",
            state="state-123",
            code_challenge="challenge-123",
            scopes=["email"],
        )
    )

    assert search["scope"] == ["email"]


def test_scope_defaults_from_resource_metadata_before_server_metadata() -> None:
    resource_metadata = OAuthProtectedResourceMetadata(
        resource="https://mcp.example.com/mcp",
        authorization_servers=["https://auth.example.com"],
        scopes_supported=["mcp:read"],
        raw_json="{}",
    )

    search = _params(
        build_oauth_authorization_url(
            metadata=METADATA,
            client_id="client-123",
            redirect_uri="http://127.0.0.1:49152/callback",
            state="state-123",
            code_challenge="challenge-123",
            resource_metadata=resource_metadata,
        )
    )

    assert search["scope"] == ["mcp:read"]


def test_includes_resource_parameter_when_provided() -> None:
    search = _params(
        build_oauth_authorization_url(
            metadata=METADATA,
            client_id="client-123",
            redirect_uri="http://127.0.0.1:49152/callback",
            state="state-123",
            code_challenge="challenge-123",
            resource_metadata=OAuthProtectedResourceMetadata(
                resource="https://mcp.example.com/mcp",
                authorization_servers=["https://auth.example.com"],
                scopes_supported=[],
                raw_json="{}",
            ),
        )
    )

    assert search["resource"] == ["https://mcp.example.com/mcp"]


def test_preserves_existing_query_params_on_authorization_endpoint() -> None:
    search = _params(
        build_oauth_authorization_url(
            metadata=METADATA,
            client_id="client-123",
            redirect_uri="http://127.0.0.1:49152/callback",
            state="state-123",
            code_challenge="challenge-123",
        )
    )

    assert search["prompt"] == ["consent"]
