"""Tests for OAuth token store helpers."""

import asyncio

from gopher_mcp_python.oauth_token_store import (
    InMemoryGopherAgentTokenStore,
    create_oauth_token_cache_key,
    resolve_oauth_token_from_store,
)
from gopher_mcp_python.runtime_options import GopherAgentTokenRecord


def test_cache_key_sorts_and_deduplicates_scopes() -> None:
    assert create_oauth_token_cache_key(
        resource="res",
        issuer="iss",
        client_id="cid",
        scopes=["email", "openid", "email"],
    ) == create_oauth_token_cache_key(
        resource="res",
        issuer="iss",
        client_id="cid",
        scopes=["openid", "email"],
    )


def test_valid_cached_token_is_returned() -> None:
    asyncio.run(_test_valid_cached_token_is_returned())


async def _test_valid_cached_token_is_returned() -> None:
    store = InMemoryGopherAgentTokenStore()
    token = GopherAgentTokenRecord(access_token="cached", expires_at=2000)
    await store.set("key", token)

    result = await resolve_oauth_token_from_store(
        store=store,
        key="key",
        now_ms=1000,
        refresh_token=lambda refresh: None,
        acquire_token=lambda: None,
    )

    assert result.access_token == "cached"


def test_expired_token_refreshes() -> None:
    asyncio.run(_test_expired_token_refreshes())


async def _test_expired_token_refreshes() -> None:
    store = InMemoryGopherAgentTokenStore()
    await store.set(
        "key",
        GopherAgentTokenRecord(
            access_token="old",
            refresh_token="refresh",
            expires_at=1000,
        ),
    )

    async def refresh_token(refresh: str) -> GopherAgentTokenRecord:
        assert refresh == "refresh"
        return GopherAgentTokenRecord(access_token="new")

    result = await resolve_oauth_token_from_store(
        store=store,
        key="key",
        now_ms=2000,
        refresh_token=refresh_token,
        acquire_token=lambda: None,
    )

    assert result.access_token == "new"
