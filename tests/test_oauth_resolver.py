"""Tests for OAuth runtime option resolution."""

import asyncio

import pytest

from gopher_mcp_python.oauth_discovery import McpOAuthChallenge
from gopher_mcp_python.oauth_resolver import (
    _resolve_resource_metadata_for_challenge,
    resolve_runtime_options_with_oauth,
    set_oauth_resolver_hooks_for_test,
)
from gopher_mcp_python.runtime_options import GopherAgentRuntimeOptions


def teardown_function() -> None:
    set_oauth_resolver_hooks_for_test()


def test_disabled_mode_is_noop() -> None:
    asyncio.run(_test_disabled_mode_is_noop())


async def _test_disabled_mode_is_noop() -> None:
    async def probe(_url):
        raise AssertionError("probe should not run")

    set_oauth_resolver_hooks_for_test(probe_challenge=probe)

    result = await resolve_runtime_options_with_oauth(
        urls=["https://mcp.example.com/mcp"],
        oauth={"mode": "disabled"},
    )

    assert result is None


def test_existing_authorization_header_skips_probe() -> None:
    asyncio.run(_test_existing_authorization_header_skips_probe())


async def _test_existing_authorization_header_skips_probe() -> None:
    async def probe(_url):
        raise AssertionError("probe should not run")

    runtime_options = GopherAgentRuntimeOptions(
        headers={"Authorization": "Bearer explicit"}
    )
    set_oauth_resolver_hooks_for_test(probe_challenge=probe)

    result = await resolve_runtime_options_with_oauth(
        urls=["https://mcp.example.com/mcp"],
        runtime_options=runtime_options,
    )

    assert result is not None
    assert result.headers == {"Authorization": "Bearer explicit"}


def test_one_oauth_server_returns_token_options() -> None:
    asyncio.run(_test_one_oauth_server_returns_token_options())


async def _test_one_oauth_server_returns_token_options() -> None:
    async def probe(url):
        return McpOAuthChallenge(
            url=url,
            requires_oauth=True,
            http_status=401,
            resource_metadata_url="https://mcp.example.com/resource",
        )

    async def acquire(challenges, oauth):
        assert len(challenges) == 1
        return GopherAgentRuntimeOptions(access_token="token")

    set_oauth_resolver_hooks_for_test(
        probe_challenge=probe,
        acquire_token=acquire,
    )

    result = await resolve_runtime_options_with_oauth(
        urls=["https://mcp.example.com/mcp"],
    )

    assert result is not None
    assert result.access_token == "token"


def test_synthetic_gopher_challenge_builds_resource_metadata() -> None:
    challenge = McpOAuthChallenge(
        url="https://mcp.gopher.security/v1/mcp/servers/example/mcp",
        requires_oauth=True,
        http_status=404,
        authorization_server="https://auth.gopher.security/realms/gopher-mcp",
        resource="https://mcp.gopher.security/v1/mcp/servers/example/mcp",
        scopes=["openid", "profile", "email"],
    )

    metadata = _resolve_resource_metadata_for_challenge(challenge)

    assert metadata.resource == challenge.resource
    assert metadata.authorization_servers == [challenge.authorization_server]
    assert metadata.scopes_supported == ["openid", "profile", "email"]


def test_missing_resource_metadata_without_authorization_server_fails() -> None:
    challenge = McpOAuthChallenge(
        url="https://mcp.example.com/mcp",
        requires_oauth=True,
        http_status=401,
    )

    with pytest.raises(RuntimeError, match="missing resource_metadata"):
        _resolve_resource_metadata_for_challenge(challenge)


def test_incompatible_oauth_servers_fail() -> None:
    asyncio.run(_test_incompatible_oauth_servers_fail())


async def _test_incompatible_oauth_servers_fail() -> None:
    async def probe(url):
        return McpOAuthChallenge(
            url=url,
            requires_oauth=True,
            http_status=401,
            resource_metadata_url=f"{url}/resource",
        )

    set_oauth_resolver_hooks_for_test(probe_challenge=probe)

    with pytest.raises(RuntimeError, match="multiple protected MCP servers"):
        await resolve_runtime_options_with_oauth(
            urls=["https://one.example.com/mcp", "https://two.example.com/mcp"]
        )
