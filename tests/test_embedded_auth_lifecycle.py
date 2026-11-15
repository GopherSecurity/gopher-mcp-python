"""Exercise host stores across creation, query cancellation, and disposal."""

import asyncio
import queue
import threading
from types import SimpleNamespace

import pytest

import gopher_mcp_python.agent as module
from gopher_mcp_python import AgentError, GopherAgent
from gopher_mcp_python.oauth_resolver import MultipleMcpOAuthRequired
from tests.test_embedded_auth import Context, INVENTORY, install


async def eventually(predicate):
    for _ in range(200):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Background cleanup did not finish")


def factory_setup(monkeypatch, context, library):
    install(monkeypatch, context)
    monkeypatch.setattr(module.GopherOrchLibrary, "get_instance", lambda: library)
    monkeypatch.setattr(module.ServerConfig, "fetch", lambda *args, **kwargs: INVENTORY)

    async def multiple(**kwargs):
        raise MultipleMcpOAuthRequired()

    monkeypatch.setattr(
        module.oauth_resolver, "resolve_runtime_options_with_oauth", multiple
    )


def test_query_services_store_on_creation_loop_and_disposal_stops_host(monkeypatch):
    async def check():
        loop = asyncio.get_running_loop()
        requests = queue.Queue()
        completed = threading.Event()
        context = Context([{"type": "authorized"}])
        context.store_request = lambda: (
            requests.get_nowait() if not requests.empty() else None
        )
        context.complete_store = lambda *args: completed.set()
        binding = dict(
            zip(
                (
                    "identity_namespace",
                    "source",
                    "issuer",
                    "resource",
                    "scopes",
                    "client_identity",
                ),
                ("user", "a", "issuer", "resource", "read", "client"),
            )
        )
        calls = []

        class Store:
            async def get(self, key):
                assert asyncio.get_running_loop() is loop
                await asyncio.sleep(0.01)
                calls.append("get")

            async def set(self, *args):
                pass

        def run(*args):
            requests.put({"operation": "get", "id": "refresh", "binding": binding})
            assert completed.wait(3), "Store callback could not run during native query"
            return "answer"

        library = SimpleNamespace(
            agent_run=run, agent_release=lambda handle: calls.append("release")
        )
        factory_setup(monkeypatch, context, library)
        agent = await GopherAgent.create_with_api_key_async(
            "p",
            "m",
            "key",
            {
                "oauth": {
                    "token_store": Store(),
                    "assemble": {"identity_namespace": "user"},
                }
            },
        )
        assert not context.closed.is_set()
        with pytest.raises(AgentError, match="ASYNC_RUN_REQUIRED"):
            agent.run("would block")
        assert await agent.run_async("query") == "answer"
        await agent.dispose_async()
        assert context.closed.is_set()
        assert calls == ["get", "release"]
        await agent.dispose_async()
        assert calls.count("release") == 1

    asyncio.run(check())


def test_cancelled_query_keeps_agent_and_host_until_native_call_exits(monkeypatch):
    async def check():
        entered, finish = threading.Event(), threading.Event()
        context = Context([{"type": "authorized"}])
        releases = []

        def run(*args):
            entered.set()
            assert finish.wait(3)
            assert not context.closed.is_set()
            return "answer"

        library = SimpleNamespace(
            agent_run=run, agent_release=lambda h: releases.append(h)
        )
        factory_setup(monkeypatch, context, library)

        class Store:
            async def get(self, key):
                pass

        agent = await GopherAgent.create_with_api_key_async(
            "p",
            "m",
            "key",
            {
                "oauth": {
                    "token_store": Store(),
                    "assemble": {"identity_namespace": "user"},
                }
            },
        )
        query = asyncio.create_task(agent.run_async("query"))
        await eventually(entered.is_set)
        with pytest.raises(AgentError, match="already running"):
            await agent.run_async("overlap")
        query.cancel()
        with pytest.raises(asyncio.CancelledError):
            await query
        dispose = asyncio.create_task(agent.dispose_async())
        await eventually(agent.is_disposed)
        assert not dispose.done()
        assert releases == []
        finish.set()
        await asyncio.wait_for(dispose, 3)
        assert releases == [42]
        assert context.closed.is_set()

    asyncio.run(check())


def test_async_creation_cancellation_releases_context_and_cancels_presenter(
    monkeypatch,
):
    async def check():
        entered, exited = asyncio.Event(), asyncio.Event()

        async def presenter(*args):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.set()

        context = Context([{"type": "page", "url": "http://127.0.0.1:1234/private"}])
        factory_setup(monkeypatch, context, SimpleNamespace())
        create = asyncio.create_task(
            GopherAgent.create_with_api_key_async(
                "p",
                "m",
                "key",
                {"oauth": {"assemble": {"on_authorization_url": presenter}}},
            )
        )
        await asyncio.wait_for(entered.wait(), 3)
        create.cancel()
        with pytest.raises(asyncio.CancelledError):
            await create
        await eventually(context.closed.is_set)
        await asyncio.wait_for(exited.wait(), 3)
        assert context.calls[-2:] == ["cancel", "close"]
        assert "take_agent" not in context.calls

    asyncio.run(check())


def test_cancelled_factory_disposes_a_late_native_agent():
    async def check():
        entered, finish = threading.Event(), threading.Event()
        releases = []
        library = SimpleNamespace(agent_release=lambda h: releases.append(h))

        def factory():
            entered.set()
            assert finish.wait(3)
            return GopherAgent(123, library)

        create = asyncio.create_task(module._create_agent_async(factory))
        await eventually(entered.is_set)
        create.cancel()
        with pytest.raises(asyncio.CancelledError):
            await create
        finish.set()
        await eventually(lambda: releases == [123])

    asyncio.run(check())


def test_closed_store_callback_loop_is_reported_before_native_query(monkeypatch):
    async def create():
        context = Context([{"type": "authorized"}])

        class Store:
            async def get(self, key):
                pass

        library = SimpleNamespace(agent_release=lambda h: None)
        factory_setup(monkeypatch, context, library)
        return await GopherAgent.create_with_api_key_async(
            "p",
            "m",
            "key",
            {
                "oauth": {
                    "token_store": Store(),
                    "assemble": {"identity_namespace": "user"},
                }
            },
        )

    agent = asyncio.run(create())
    try:
        with pytest.raises(AgentError, match="AUTH_CALLBACK_LOOP"):
            agent.run("query")
    finally:
        agent.dispose()
