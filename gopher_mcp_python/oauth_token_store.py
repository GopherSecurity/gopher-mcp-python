"""OAuth token cache helpers."""

import json
import time
from typing import Awaitable, Callable, Dict, List, Optional

from gopher_mcp_python.runtime_options import GopherAgentTokenRecord


class InMemoryGopherAgentTokenStore:
    """Simple in-memory async token store."""

    def __init__(self) -> None:
        self._tokens: Dict[str, GopherAgentTokenRecord] = {}

    async def get(self, key: str) -> Optional[GopherAgentTokenRecord]:
        return self._tokens.get(key)

    async def set(self, key: str, token: GopherAgentTokenRecord) -> None:
        self._tokens[key] = token

    async def delete(self, key: str) -> None:
        self._tokens.pop(key, None)


def create_oauth_token_cache_key(
    resource: str,
    issuer: str,
    client_id: str,
    scopes: List[str],
) -> str:
    """Create a stable token cache key."""
    unique_scopes = " ".join(sorted(set(scopes)))
    return json.dumps(
        {
            "resource": resource,
            "issuer": issuer,
            "client_id": client_id,
            "scopes": unique_scopes,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


async def resolve_oauth_token_from_store(
    store,
    key: str,
    refresh_token: Callable[[str], Awaitable[GopherAgentTokenRecord]],
    acquire_token: Callable[[], Awaitable[GopherAgentTokenRecord]],
    now_ms: Optional[float] = None,
) -> GopherAgentTokenRecord:
    """Return a valid cached token, refresh it, or acquire a new one."""
    now = now_ms if now_ms is not None else time.time() * 1000
    cached = await store.get(key)
    if cached is not None and not _is_expired(cached, now):
        return cached

    if cached is not None and cached.refresh_token:
        try:
            refreshed = await refresh_token(cached.refresh_token)
            await store.set(key, refreshed)
            return refreshed
        except Exception:
            delete = getattr(store, "delete", None)
            if delete is not None:
                await delete(key)

    acquired = await acquire_token()
    await store.set(key, acquired)
    return acquired


def _is_expired(token: GopherAgentTokenRecord, now_ms: float) -> bool:
    return token.expires_at is not None and token.expires_at <= now_ms
