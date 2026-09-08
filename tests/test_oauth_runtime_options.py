"""Tests for merging OAuth tokens into runtime options."""

from gopher_mcp_python.oauth_runtime_options import merge_oauth_token_into_runtime_options
from gopher_mcp_python.runtime_options import (
    GopherAgentRuntimeOptions,
    GopherAgentTokenRecord,
)


TOKEN = GopherAgentTokenRecord(access_token="oauth-token", token_type="Bearer")


def test_explicit_authorization_header_wins() -> None:
    result = merge_oauth_token_into_runtime_options(
        GopherAgentRuntimeOptions(headers={"Authorization": "Bearer caller-token"}),
        TOKEN,
    )

    assert result.headers == {"Authorization": "Bearer caller-token"}
    assert result.access_token is None


def test_explicit_access_token_wins() -> None:
    result = merge_oauth_token_into_runtime_options(
        GopherAgentRuntimeOptions(access_token="caller-token"),
        TOKEN,
    )

    assert result.access_token == "caller-token"


def test_oauth_token_fills_empty_options() -> None:
    result = merge_oauth_token_into_runtime_options(None, TOKEN)

    assert result.access_token == "oauth-token"


def test_existing_unrelated_headers_are_preserved() -> None:
    result = merge_oauth_token_into_runtime_options(
        GopherAgentRuntimeOptions(
            headers={"X-Tenant": "tenant-a"},
            elicitation={"open_browser": False},
        ),
        TOKEN,
    )

    assert result.headers == {
        "X-Tenant": "tenant-a",
        "Authorization": "Bearer oauth-token",
    }
    assert result.access_token == "oauth-token"
    assert result.elicitation is not None
    assert result.elicitation.open_browser is False
