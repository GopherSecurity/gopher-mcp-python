"""Opt-in integration checks against an actual embedded authorization v1 binary.

Set GOPHER_EMBEDDED_AUTH_TEST_LIBRARY to its path. No real API/LLM credentials
or external MCP service is used; OAuth issuers and MCP servers run locally.
"""

import asyncio
import json
import os
import threading

import pytest

import gopher_mcp_python.agent as module
import gopher_mcp_python.server_config as transport
from gopher_mcp_python import AgentError, GopherAgent
from gopher_mcp_python.ffi.embedded_auth import EmbeddedAuthBindings
from gopher_mcp_python.ffi.library import GopherOrchLibrary
from gopher_mcp_python.oauth_token_store import InMemoryGopherAgentTokenStore
from tests.helpers.embedded_oauth import OAuthFixture, authorize, fetch

ARTIFACT = os.environ.get("GOPHER_EMBEDDED_AUTH_TEST_LIBRARY")
pytestmark = pytest.mark.skipif(
    not ARTIFACT,
    reason="Set GOPHER_EMBEDDED_AUTH_TEST_LIBRARY to test a real v1 binary",
)


@pytest.fixture
def native_library(monkeypatch):
    monkeypatch.setenv("GOPHER_MCP_PYTHON_LIBRARY_PATH", ARTIFACT)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-only")
    library = GopherOrchLibrary()
    assert library._available, library._load_errors
    assert os.path.realpath(library._loaded_library_path) == os.path.realpath(ARTIFACT)
    assert EmbeddedAuthBindings(library).capabilities()["version"] == 1
    monkeypatch.setattr(module.GopherOrchLibrary, "get_instance", lambda: library)
    return library


def inventory_transport(monkeypatch, fixture):
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return fixture.inventory().encode()

    def open_inventory(request, timeout):
        calls.append(request)
        assert request.method == "POST"
        assert json.loads(request.data) == {
            "serverId": ["a", "b"],
            "serverName": [],
            "gatewayId": [],
            "gatewayName": [],
        }
        assert request.get_header("Authorization") == "Bearer inventory-fixture"
        return Response()

    monkeypatch.setattr(transport, "urlopen", open_inventory)
    return calls


def create_options(presenter, store=None, **settings):
    return {
        "server_ids": ["a", "b"],
        "oauth": {
            "open_browser": False,
            "token_store": store,
            "assemble": {
                "identity_namespace": "fixture-user",
                "allow_loopback_http": True,
                "network_timeout_ms": 2000,
                "discovery_timeout_ms": 5000,
                "timeout_ms": 10000,
                "on_authorization_url": presenter,
                **settings,
            },
        },
    }


@pytest.mark.parametrize(
    "shared",
    [False, True],
    ids=["distinct-issuers", "shared-issuer-distinct-resources"],
)
def test_real_handoff_distinct_grants_and_cached_source_refresh(
    monkeypatch, native_library, shared
):
    fixture = OAuthFixture(shared=shared)
    calls = inventory_transport(monkeypatch, fixture)
    pages = []
    store = InMemoryGopherAgentTokenStore()

    def presenter(url, flow):
        pages.append(url)
        authorize(url, flow)

    options = create_options(presenter, store)

    async def check():
        agent = await GopherAgent.create_with_api_key_async(
            "OpenAIProvider", "fixture-model", "inventory-fixture", options
        )
        try:
            assert len(calls) == 1
            assert len(pages) == 1
            assert len(store._tokens) == 2
            assert fixture.tokens["a"] != fixture.tokens["b"]
            assert {"a", "b"} <= set(fixture.initialized)
        finally:
            await agent.dispose_async()
        b_token = fixture.tokens["b"]
        for token in store._tokens.values():
            if "/a/mcp" in token.embedded_grant["binding"]["source"]:
                token.embedded_grant["expires_at"] = 0
        agent = await GopherAgent.create_with_api_key_async(
            "OpenAIProvider", "fixture-model", "inventory-fixture", options
        )
        try:
            assert len(calls) == 2
            assert len(pages) == 1
            assert fixture.refreshes == ["a"]
            assert fixture.tokens["b"] == b_token
        finally:
            await agent.dispose_async()

    try:
        asyncio.run(check())
    finally:
        fixture.close()
    assert not native_library._agent_option_storage


def test_real_cancel_closes_private_page(monkeypatch, native_library):
    fixture = OAuthFixture()
    inventory_transport(monkeypatch, fixture)
    cancelled = threading.Event()
    pages = []

    def presenter(url, flow):
        pages.append(url)
        cancelled.set()

    try:
        with pytest.raises(AgentError, match="AUTH_CANCELLED"):
            GopherAgent.create_with_api_key(
                "OpenAIProvider",
                "fixture-model",
                "inventory-fixture",
                create_options(presenter, cancel_event=cancelled),
            )
        assert len(pages) == 1
        with pytest.raises(OSError):
            fetch(pages[0])
    finally:
        fixture.close()


def test_real_server_auth_keeps_provider_elicitation_enabled(
    monkeypatch, native_library
):
    fixture = OAuthFixture(provider_required=True)
    inventory_transport(monkeypatch, fixture)
    callbacks = []

    def handler(request):
        callbacks.append(request)
        assert len(fixture.tokens) == 2
        fixture.provider_ready = True
        return "accept"

    options = create_options(authorize)
    options["elicitation"] = {"handler": handler}
    try:
        agent = GopherAgent.create_with_api_key(
            "OpenAIProvider", "fixture-model", "inventory-fixture", options
        )
        try:
            assert callbacks
            assert fixture.provider_ready
        finally:
            agent.dispose()
    finally:
        fixture.close()


def test_real_concurrent_identities_have_separate_pages_and_grants(
    monkeypatch, native_library
):
    fixture = OAuthFixture()
    calls = inventory_transport(monkeypatch, fixture)
    store = InMemoryGopherAgentTokenStore()
    pages = []

    def presenter(url, flow):
        pages.append(url)
        authorize(url, flow)

    async def check():
        agents = await asyncio.gather(
            *(
                GopherAgent.create_with_api_key_async(
                    "OpenAIProvider",
                    "fixture-model",
                    "inventory-fixture",
                    create_options(presenter, store, identity_namespace=user),
                )
                for user in ("user-one", "user-two")
            )
        )
        try:
            assert len(calls) == 2
            assert len(set(pages)) == 2
            assert len(store._tokens) == 4
            identities = {
                token.embedded_grant["binding"]["identity_namespace"]
                for token in store._tokens.values()
            }
            assert identities == {"user-one", "user-two"}
        finally:
            await asyncio.gather(*(agent.dispose_async() for agent in agents))

    try:
        asyncio.run(check())
    finally:
        fixture.close()
    assert not native_library._agent_option_storage


def test_real_store_failure_is_sanitized_and_releases_context(
    monkeypatch, native_library
):
    fixture = OAuthFixture()
    inventory_transport(monkeypatch, fixture)

    class Store:
        async def get(self, key):
            raise ValueError("private-store-secret")

    try:
        with pytest.raises(AgentError) as error:
            GopherAgent.create_with_api_key(
                "OpenAIProvider",
                "fixture-model",
                "inventory-fixture",
                create_options(authorize, Store()),
            )
        assert "private-store-secret" not in str(error.value)
        assert not native_library._agent_option_storage
    finally:
        fixture.close()


def test_real_legacy_single_grant_does_not_reach_public_source(
    monkeypatch, native_library
):
    from gopher_mcp_python import GopherAgentRuntimeOptions

    fixture = OAuthFixture()
    fixture.inventory_sources = ("a", "public")
    inventory_transport(monkeypatch, fixture)

    async def acquire(*args):
        fixture.valid_tokens["a"].add("one-source-only")
        return GopherAgentRuntimeOptions(access_token="one-source-only")

    monkeypatch.setattr(module.oauth_resolver, "_acquire_token", acquire)
    try:
        agent = GopherAgent.create_with_api_key(
            "OpenAIProvider",
            "fixture-model",
            "inventory-fixture",
            {"server_ids": ["a", "b"]},
        )
        try:
            assert {"a", "public"} <= set(fixture.initialized)
            assert ("a", "one-source-only") in fixture.received_credentials
            assert all(
                not token
                for source, token in fixture.received_credentials
                if source == "public"
            )
        finally:
            agent.dispose()
    finally:
        fixture.close()
