import asyncio
import json
import threading
from types import SimpleNamespace

import pytest

import gopher_mcp_python.embedded_auth as host
import gopher_mcp_python.agent as agent_module
from gopher_mcp_python import AgentError, GopherAgent, GopherAgentCreateOptions
from gopher_mcp_python.oauth_discovery import McpOAuthChallenge
from gopher_mcp_python.oauth_token_store import InMemoryGopherAgentTokenStore

INVENTORY = json.dumps(
    {
        "succeeded": True,
        "data": {
            "servers": [
                {
                    "name": name,
                    "id": name,
                    "transport": "http",
                    "config": {"url": f"https://{name}.example/mcp"},
                }
                for name in ("a", "b")
            ]
        },
    }
)


class Context:
    def __init__(self, events=()):
        self.events = list(events)
        self.calls = []
        self.closed = threading.Event()

    def start(self):
        self.calls.append("start")

    def create_agent(self, provider, model):
        self.calls.append("create_agent")
        self.events.append({"type": "agent_ready"})

    def event(self):
        return self.events.pop(0) if self.events else None

    def store_request(self):
        return None

    def take_agent(self):
        self.calls.append("take_agent")
        return 42

    def cancel(self):
        self.calls.append("cancel")

    def close(self):
        self.calls.append("close")
        self.closed.set()


def install(monkeypatch, context, capabilities=None):
    class Bindings:
        def __init__(self, library):
            pass

        def capabilities(self):
            return capabilities or {"version": 1, "async_store": True}

        def create(self, inventory, options, runtime):
            context.options, context.runtime = options, runtime
            return context

    monkeypatch.setattr(host, "EmbeddedAuthBindings", Bindings)


def test_handoff_waits_for_presenter_and_sanitizes_progress(monkeypatch):
    context = Context(
        [
            {"type": "page", "url": "http://127.0.0.1:1234/private"},
            {
                "type": "progress",
                "sources": [
                    {"source": "a", "state": "ready", "access_token": "secret"}
                ],
            },
            {"type": "authorized"},
        ]
    )
    install(monkeypatch, context)
    calls = []

    async def presenter(url, flow):
        await asyncio.sleep(0.01)
        calls.append("page")

    def progress(rows):
        calls.append(rows)

    options = GopherAgentCreateOptions(
        oauth={
            "open_browser": False,
            "assemble": {
                "on_authorization_url": presenter,
                "on_progress": progress,
                "clients": {"a": {"client_id": "client"}},
            },
        }
    )
    session = host.EmbeddedAgentSession(None, INVENTORY, "p", "m", options)
    assert session.wait_ready() == 42
    session.close()
    assert "page" in calls
    assert [{"source": "a", "state": "ready"}] in calls
    assert context.calls == ["start", "create_agent", "take_agent", "close"]
    assert context.options["clients"]["a"]["client_id"] == "client"


@pytest.mark.parametrize(
    "settings, pattern",
    [
        ({}, "AUTH_PRESENTATION_REQUIRED"),
        (
            {
                "on_authorization_url": lambda *args: (_ for _ in ()).throw(
                    ValueError("private-token")
                )
            },
            "AUTH_HOST_CALLBACK",
        ),
    ],
)
def test_failed_presentation_cancels_and_releases(monkeypatch, settings, pattern):
    context = Context(
        [
            {"type": "page", "url": "http://127.0.0.1:1234/private"},
            {"type": "authorized"},
        ]
    )
    install(monkeypatch, context)
    session = host.EmbeddedAgentSession(
        None,
        INVENTORY,
        "p",
        "m",
        GopherAgentCreateOptions(oauth={"open_browser": False, "assemble": settings}),
    )
    with pytest.raises(AgentError, match=pattern) as error:
        session.wait_ready()
    session.close()
    assert "private-token" not in str(error.value)
    assert context.calls[-2:] == ["cancel", "close"]
    assert "take_agent" not in context.calls


def test_cancel_and_stalled_presenter_timeout_release_context(monkeypatch):
    for cancel in (False, True):
        context = Context([{"type": "page", "url": "http://127.0.0.1:1234/private"}])
        install(monkeypatch, context)
        event = threading.Event()
        stalled = threading.Event()
        if cancel:
            event.set()
        options = GopherAgentCreateOptions(
            oauth={
                "assemble": {
                    "cancel_event": event,
                    "on_authorization_url": lambda *args: stalled.wait(2),
                    "timeout_ms": 100,
                    "network_timeout_ms": 100,
                    "discovery_timeout_ms": 100,
                }
            }
        )
        session = host.EmbeddedAgentSession(None, INVENTORY, "p", "m", options)
        try:
            with pytest.raises(AgentError, match="AUTH_CANCELLED|timed out"):
                session.wait_ready()
            session.close()
            assert context.closed.is_set()
        finally:
            stalled.set()


def test_store_keys_isolate_every_binding_field_and_preserve_native_grant():
    asyncio.run(_store_roundtrip())


async def _store_roundtrip():
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
    key = host.store_key(binding)
    for field in binding:
        changed = dict(binding, **{field: "different"})
        assert host.store_key(changed) != key
    store = InMemoryGopherAgentTokenStore()
    grant = {
        "access_token": "token",
        "refresh_token": "refresh",
        "client_secret": "secret",
        "expires_at": 123,
        "binding": binding,
    }
    request = {"operation": "put", "binding": binding, "grant": grant}
    assert await host.service_store(store, request) == {"ok": True}
    assert (await store.get(key)).expires_at == 123000
    grant["access_token"] = "mutated"
    assert (await host.service_store(store, dict(request, operation="get")))["grant"][
        "access_token"
    ] == "token"
    await host.service_store(store, dict(request, operation="erase"))
    assert await host.service_store(store, dict(request, operation="get")) == {
        "found": False
    }


def test_external_store_requires_stable_identity():
    with pytest.raises(AgentError, match="identity_namespace"):
        host._settings(
            GopherAgentCreateOptions(
                oauth={"token_store": InMemoryGopherAgentTokenStore()}
            ),
            INVENTORY,
        )


def test_multiple_bindings_use_native_handoff_after_one_inventory_fetch(monkeypatch):
    context = Context([{"type": "authorized"}])
    install(monkeypatch, context)
    calls = []
    library = SimpleNamespace(
        agent_release=lambda handle: calls.append(("release", handle))
    )
    monkeypatch.setattr(agent_module.GopherOrchLibrary, "get_instance", lambda: library)

    def fetch(*args, **kwargs):
        calls.append(("fetch",))
        return INVENTORY

    monkeypatch.setattr(agent_module.ServerConfig, "fetch", fetch)

    async def probe(url):
        return McpOAuthChallenge(
            url=url,
            requires_oauth=True,
            http_status=401,
            resource_metadata_url=url + "/metadata",
        )

    agent_module.oauth_resolver.set_oauth_resolver_hooks_for_test(probe_challenge=probe)
    try:
        agent = GopherAgent.create_with_api_key("p", "m", "inventory-key")
        agent.dispose()
        assert calls == [("fetch",), ("release", 42)]
        assert context.closed.is_set()
    finally:
        agent_module.oauth_resolver.set_oauth_resolver_hooks_for_test()


def test_config_headers_used_by_inventory_oauth_probe(monkeypatch):
    calls = []

    def probe(url, **kwargs):
        calls.append(kwargs["headers"])
        return McpOAuthChallenge(url=url, requires_oauth=False, http_status=200)

    monkeypatch.setattr(agent_module.oauth_resolver, "probe_mcp_oauth_challenge", probe)
    config = json.dumps(
        {
            "servers": [
                {
                    "transport": "http",
                    "config": {
                        "url": "https://a.example",
                        "headers": {"X-API-Key": "source-key"},
                    },
                }
            ]
        }
    )
    asyncio.run(
        agent_module.oauth_resolver.resolve_runtime_options_with_oauth(
            server_config=config
        )
    )
    assert calls == [{"X-API-Key": "source-key"}]
