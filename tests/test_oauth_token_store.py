"""Tests for OAuth token store helpers."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import gopher_mcp_python.oauth_token_store as token_store_module

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


@pytest.mark.parametrize("cancel_owner", [False, True])
def test_concurrent_refresh_rotates_token_once_and_survives_caller_cancellation(
    cancel_owner,
):
    async def check():
        store = InMemoryGopherAgentTokenStore()
        await store.set(
            "key", GopherAgentTokenRecord("old", refresh_token="r1", expires_at=1)
        )
        started, finish = asyncio.Event(), asyncio.Event()
        calls = []

        async def refresh(token):
            calls.append(token)
            started.set()
            await finish.wait()
            return GopherAgentTokenRecord("new", refresh_token="r2")

        def resolve():
            return resolve_oauth_token_from_store(store, "key", refresh, None)

        owner = asyncio.create_task(resolve())
        await started.wait()
        waiters = [asyncio.create_task(resolve()) for _ in range(8)]
        requests = [owner, *waiters]
        cancelled = owner if cancel_owner else waiters[0]
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        finish.set()
        results = await asyncio.gather(
            *(request for request in requests if request is not cancelled)
        )
        assert calls == ["r1"]
        assert all(result.refresh_token == "r2" for result in results)
        assert (await store.get("key")).access_token == "new"
        assert not token_store_module._flights

    asyncio.run(check())


def test_different_cache_keys_resolve_independently():
    async def check():
        store = InMemoryGopherAgentTokenStore()
        started = {key: asyncio.Event() for key in ("a", "b")}
        finish = asyncio.Event()

        async def acquire(key):
            started[key].set()
            await finish.wait()
            return GopherAgentTokenRecord(key)

        tasks = [
            asyncio.create_task(
                resolve_oauth_token_from_store(
                    store, key, None, lambda key=key: acquire(key)
                )
            )
            for key in started
        ]
        try:
            for event in started.values():
                await asyncio.wait_for(event.wait(), 5)
        finally:
            finish.set()
        assert {token.access_token for token in await asyncio.gather(*tasks)} == {
            "a",
            "b",
        }

    asyncio.run(check())


def test_shared_acquisition_failure_is_removed_and_can_be_retried():
    async def check():
        store = InMemoryGopherAgentTokenStore()
        started, finish = asyncio.Event(), asyncio.Event()
        calls = []

        async def acquire():
            calls.append(1)
            started.set()
            await finish.wait()
            raise ValueError("authorization failed")

        first = asyncio.create_task(
            resolve_oauth_token_from_store(store, "key", None, acquire)
        )
        await started.wait()
        second = asyncio.create_task(
            resolve_oauth_token_from_store(store, "key", None, acquire)
        )
        finish.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(result, ValueError) for result in results)
        assert calls == [1]
        assert not token_store_module._flights

        async def retry():
            return GopherAgentTokenRecord("retry")

        assert (
            await resolve_oauth_token_from_store(store, "key", None, retry)
        ).access_token == "retry"

    asyncio.run(check())


@pytest.mark.parametrize("refresh_fails", [False, True])
def test_refresh_does_not_overwrite_or_delete_newer_external_token(refresh_fails):
    async def check():
        store = InMemoryGopherAgentTokenStore()
        await store.set(
            "key", GopherAgentTokenRecord("old", refresh_token="r1", expires_at=1)
        )
        latest = GopherAgentTokenRecord("external")

        async def refresh(token):
            await store.set("key", latest)
            if refresh_fails:
                raise ValueError("old refresh was rejected")
            return GopherAgentTokenRecord("slow")

        result = await resolve_oauth_token_from_store(store, "key", refresh, None)
        assert result is latest
        assert await store.get("key") is latest

    asyncio.run(check())


def test_failed_refresh_acquires_new_token_without_losing_newer_record():
    async def check():
        store = InMemoryGopherAgentTokenStore()
        await store.set(
            "key", GopherAgentTokenRecord("old", refresh_token="r1", expires_at=1)
        )

        async def refresh(token):
            raise ValueError("revoked refresh token")

        async def acquire():
            return GopherAgentTokenRecord("reacquired")

        result = await resolve_oauth_token_from_store(store, "key", refresh, acquire)
        assert result.access_token == "reacquired"

    asyncio.run(check())


def test_owner_event_loop_shutdown_cleans_pending_resolution():
    store = InMemoryGopherAgentTokenStore()

    async def cancelled():
        started = asyncio.Event()

        async def acquire():
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(
            resolve_oauth_token_from_store(store, "key", None, acquire)
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancelled())
    assert not token_store_module._flights

    async def retry():
        async def acquire():
            return GopherAgentTokenRecord("retry")

        return await resolve_oauth_token_from_store(store, "key", None, acquire)

    assert asyncio.run(retry()).access_token == "retry"


def test_producer_loop_shutdown_reports_retryable_error_to_another_thread(monkeypatch):
    store = InMemoryGopherAgentTokenStore()
    started, attached, shutdown = (threading.Event() for _ in range(3))
    caller = threading.local()
    wrap_future = asyncio.wrap_future
    acquisitions = []

    def observe_attachment(future, **kwargs):
        wrapped = wrap_future(future, **kwargs)
        if getattr(caller, "is_waiter", False):
            attached.set()
        return wrapped

    monkeypatch.setattr(token_store_module.asyncio, "wrap_future", observe_attachment)

    async def acquire():
        started.set()
        await asyncio.Event().wait()

    async def initiating_loop():
        request = asyncio.create_task(
            resolve_oauth_token_from_store(store, "key", None, acquire)
        )
        assert await asyncio.get_running_loop().run_in_executor(None, shutdown.wait, 5)
        # Returning lets asyncio.run() cancel both the initiating request and
        # its producer, while another event loop is still awaiting that work.
        return request

    async def waiting_loop():
        caller.is_waiter = True

        async def acquire_retry():
            acquisitions.append("retry")
            return GopherAgentTokenRecord("retry")

        with pytest.raises(
            RuntimeError, match="OAuth token resolution was interrupted; retry"
        ):
            await resolve_oauth_token_from_store(store, "key", None, acquire_retry)
        assert not token_store_module._flights
        assert acquisitions == []
        token = await resolve_oauth_token_from_store(store, "key", None, acquire_retry)
        return token.access_token

    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(asyncio.run, initiating_loop())
        try:
            assert started.wait(5)
            waiter = pool.submit(asyncio.run, waiting_loop())
            assert attached.wait(5)
        finally:
            shutdown.set()
        assert owner.result(5).cancelled()
        assert waiter.result(5) == "retry"
    assert acquisitions == ["retry"]
    assert not token_store_module._flights


def test_shared_token_store_coordinates_threads_and_event_loops():
    store = InMemoryGopherAgentTokenStore()
    asyncio.run(
        store.set(
            "key", GopherAgentTokenRecord("old", refresh_token="r1", expires_at=1)
        )
    )
    barrier = threading.Barrier(4)
    entered, finish = threading.Event(), threading.Event()
    calls = []

    async def resolve():
        async def refresh(token):
            calls.append(token)
            entered.set()
            assert await asyncio.get_running_loop().run_in_executor(
                None, finish.wait, 5
            )
            return GopherAgentTokenRecord("new", refresh_token="r2")

        barrier.wait(5)
        return await resolve_oauth_token_from_store(store, "key", refresh, None)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(asyncio.run, resolve()) for _ in range(4)]
        try:
            assert entered.wait(5)
        finally:
            finish.set()
        results = [future.result(5) for future in futures]
    assert calls == ["r1"]
    assert all(result.access_token == "new" for result in results)
    assert not token_store_module._flights


def test_external_token_deletion_during_refresh_is_not_reversed():
    async def check():
        store = InMemoryGopherAgentTokenStore()
        await store.set(
            "key", GopherAgentTokenRecord("old", refresh_token="r1", expires_at=1)
        )

        async def refresh(token):
            await store.delete("key")
            return GopherAgentTokenRecord("slow")

        with pytest.raises(RuntimeError, match="cache changed"):
            await resolve_oauth_token_from_store(store, "key", refresh, None)
        assert await store.get("key") is None
        assert not token_store_module._flights

    asyncio.run(check())


def test_legacy_store_without_compare_and_set_remains_supported():
    class LegacyStore:
        def __init__(self):
            self.token = GopherAgentTokenRecord("old", refresh_token="r1", expires_at=1)

        async def get(self, key):
            # Persistent stores may deserialize a new object on every read.
            return GopherAgentTokenRecord(**vars(self.token))

        async def set(self, key, token):
            self.token = token

    async def check():
        store = LegacyStore()

        async def refresh(token):
            return GopherAgentTokenRecord("new")

        result = await resolve_oauth_token_from_store(store, "key", refresh, None)
        assert result.access_token == store.token.access_token == "new"

    asyncio.run(check())


def test_rejected_refresh_is_deleted_before_failed_fallback():
    async def check():
        store = InMemoryGopherAgentTokenStore()
        await store.set(
            "key", GopherAgentTokenRecord("old", refresh_token="rejected", expires_at=1)
        )

        async def refresh(token):
            raise ValueError("invalid_grant")

        async def acquire():
            assert await store.get("key") is None
            raise ValueError("authorization unavailable")

        with pytest.raises(ValueError, match="authorization unavailable"):
            await resolve_oauth_token_from_store(store, "key", refresh, acquire)
        assert await store.get("key") is None
        assert not token_store_module._flights

    asyncio.run(check())
