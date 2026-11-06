"""OAuth token cache helpers."""

import asyncio
import concurrent.futures
import json
import threading
import time
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from gopher_mcp_python.runtime_options import GopherAgentTokenRecord


class InMemoryGopherAgentTokenStore:
    """Process-local token store usable from multiple threads and event loops."""

    def __init__(self) -> None:
        self._tokens: Dict[str, GopherAgentTokenRecord] = {}
        self._lock = threading.Lock()

    async def get(self, key: str) -> Optional[GopherAgentTokenRecord]:
        with self._lock:
            return self._tokens.get(key)

    async def set(self, key: str, token: GopherAgentTokenRecord) -> None:
        with self._lock:
            self._tokens[key] = token

    async def delete(self, key: str) -> None:
        with self._lock:
            self._tokens.pop(key, None)

    async def compare_and_set(
        self,
        key: str,
        expected: Optional[GopherAgentTokenRecord],
        token: Optional[GopherAgentTokenRecord],
    ) -> bool:
        """Publish or delete only if the previously read record is still current."""
        with self._lock:
            if self._tokens.get(key) is not expected:
                return False
            if token is None:
                self._tokens.pop(key, None)
            else:
                self._tokens[key] = token
            return True


class _TokenFlight:
    def __init__(self, store) -> None:
        # Keep identity stable until completion, including non-weakref stores.
        self.store = store
        self.result = concurrent.futures.Future()
        self.task = None


_flights_lock = threading.Lock()
_flights: Dict[Tuple[int, str], _TokenFlight] = {}


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
    """Share one token resolution per store/key across process-local callers.

    Cancelling a waiter does not cancel the shared request. The request runs
    on its initiating event loop; cancelling its producer during orderly loop
    shutdown reports a retryable RuntimeError to callers still awaiting it.
    A caller's own task cancellation remains CancelledError.
    Custom stores must support the threads/loops from which they are used.
    """
    flight_key = (id(store), key)
    with _flights_lock:
        flight = _flights.get(flight_key)
        owner = flight is None
        if owner:
            flight = _TokenFlight(store)
            _flights[flight_key] = flight
    if owner:
        try:
            task = asyncio.create_task(
                _resolve_token(store, key, refresh_token, acquire_token, now_ms)
            )
            flight.task = task
            task.add_done_callback(
                lambda done: _finish_token_flight(flight_key, flight, done)
            )
        except BaseException as exc:
            with _flights_lock:
                _flights.pop(flight_key, None)
            flight.result.set_exception(exc)
            raise
    elif flight.task is asyncio.current_task():
        raise RuntimeError("Recursive OAuth token resolution for the same cache key")
    return await asyncio.shield(asyncio.wrap_future(flight.result))


def _finish_token_flight(key, flight, task) -> None:
    # Remove completed work even if its initiating caller was cancelled.
    with _flights_lock:
        if _flights.get(key) is flight:
            del _flights[key]
    if task.cancelled():
        flight.result.set_exception(
            RuntimeError("OAuth token resolution was interrupted; retry")
        )
    elif task.exception() is not None:
        flight.result.set_exception(task.exception())
    else:
        flight.result.set_result(task.result())


async def _resolve_token(store, key, refresh_token, acquire_token, now_ms):
    # Read inside the shared operation so queued callers see the latest token.
    now = now_ms if now_ms is not None else time.time() * 1000
    cached = await store.get(key)
    if cached is not None and not _is_expired(cached, now):
        return cached

    if cached is not None and cached.refresh_token:
        try:
            refreshed = await refresh_token(cached.refresh_token)
        except Exception:
            # A failed refresh must never delete a newer externally stored token.
            latest = await store.get(key)
            if latest is not None and not _is_expired(latest, now):
                return latest
            if _same_record(latest, cached):
                compare_and_set = getattr(store, "compare_and_set", None)
                delete = getattr(store, "delete", None)
                if compare_and_set is not None:
                    if await compare_and_set(key, cached, None):
                        cached = None
                elif delete is not None:
                    # Legacy stores need external coordination for writers
                    # outside this resolver, just as for publication below.
                    await delete(key)
                    cached = None
        else:
            return await _publish_token(store, key, cached, refreshed, now)

    acquired = await acquire_token()
    return await _publish_token(store, key, cached, acquired, now)


async def _publish_token(store, key, expected, token, now):
    compare_and_set = getattr(store, "compare_and_set", None)
    if compare_and_set is not None:
        published = await compare_and_set(key, expected, token)
    else:
        # Legacy stores remain supported. Out-of-band writers need an atomic
        # compare_and_set implementation; get/set alone cannot provide that.
        current = await store.get(key)
        published = _same_record(current, expected)
        if published:
            await store.set(key, token)
    if published:
        return token
    current = await store.get(key)
    if current is not None and not _is_expired(current, now):
        return current
    raise RuntimeError("OAuth token cache changed during resolution; retry the request")


def _same_record(left, right):
    if left is None or right is None:
        return left is right
    fields = ("access_token", "token_type", "refresh_token", "expires_at", "scope")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def _is_expired(token: GopherAgentTokenRecord, now_ms: float) -> bool:
    return token.expires_at is not None and token.expires_at <= now_ms
