"""Tests for OAuth-aware GopherAgent factories."""

import pytest

import gopher_mcp_python.agent as agent_module
from gopher_mcp_python import AgentError, GopherAgent
from gopher_mcp_python.runtime_options import GopherAgentRuntimeOptions


class FakeLibrary:
    def __init__(self) -> None:
        self.calls = []

    def agent_create_by_url(self, provider, model, url, runtime_options=None):
        self.calls.append(("url", provider, model, url, runtime_options))
        return 2001

    def agent_create_by_json(self, provider, model, server_config, runtime_options=None):
        self.calls.append(("json", provider, model, server_config, runtime_options))
        return 2002

    def agent_create_by_api_key(self, provider, model, api_key, runtime_options=None):
        self.calls.append(("api_key", provider, model, api_key, runtime_options))
        return 2003

    def agent_create_by_server_id(
        self, provider, model, api_key, server_id, runtime_options=None
    ):
        self.calls.append(
            ("server_id", provider, model, api_key, server_id, runtime_options)
        )
        return 2004

    def agent_create_by_server_name(
        self, provider, model, api_key, server_name, runtime_options=None
    ):
        self.calls.append(
            ("server_name", provider, model, api_key, server_name, runtime_options)
        )
        return 2005

    def agent_create_by_gateway_id(
        self, provider, model, api_key, gateway_id, runtime_options=None
    ):
        self.calls.append(
            ("gateway_id", provider, model, api_key, gateway_id, runtime_options)
        )
        return 2006

    def agent_create_by_gateway_name(
        self, provider, model, api_key, gateway_name, runtime_options=None
    ):
        self.calls.append(
            ("gateway_name", provider, model, api_key, gateway_name, runtime_options)
        )
        return 2007

    def agent_release(self, handle):
        self.calls.append(("release", handle))

    def get_last_error_message(self):
        return None

    def clear_error(self):
        self.calls.append(("clear_error",))


def _install_fake_library(monkeypatch):
    fake = FakeLibrary()
    monkeypatch.setattr(agent_module, "_initialized", True)
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary,
        "get_instance",
        staticmethod(lambda: fake),
    )
    return fake


def test_create_with_url_resolves_oauth_token(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    resolver_calls = []

    async def resolver(url, runtime_options=None, oauth=None):
        resolver_calls.append((url, runtime_options, oauth))
        return GopherAgentRuntimeOptions(access_token="oauth-token")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_url_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_url(
        "Provider",
        "model",
        "https://mcp.example.com/mcp",
    )

    call = fake.calls[0]
    assert call[:4] == ("url", "Provider", "model", "https://mcp.example.com/mcp")
    assert call[4].access_token == "oauth-token"
    assert resolver_calls[0][0] == "https://mcp.example.com/mcp"
    agent.dispose()


def test_create_with_url_disabled_oauth_skips_resolver(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)

    async def resolver(*args, **kwargs):
        raise AssertionError("resolver should not run")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_url_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_url(
        "Provider",
        "model",
        "https://mcp.example.com/mcp",
        {"oauth": {"mode": "disabled"}},
    )

    assert fake.calls[0] == (
        "url",
        "Provider",
        "model",
        "https://mcp.example.com/mcp",
        None,
    )
    agent.dispose()


def test_create_with_url_explicit_token_skips_resolver(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)

    async def resolver(*args, **kwargs):
        raise AssertionError("resolver should not run")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_url_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_url(
        "Provider",
        "model",
        "https://mcp.example.com/mcp",
        {"access_token": "caller-token"},
    )

    call = fake.calls[0]
    assert call[:4] == ("url", "Provider", "model", "https://mcp.example.com/mcp")
    assert call[4].access_token == "caller-token"
    agent.dispose()


def test_create_with_server_config_uses_resolved_options(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    resolver_calls = []

    async def resolver(urls=None, server_config=None, runtime_options=None, oauth=None):
        resolver_calls.append((urls, server_config, runtime_options, oauth))
        return GopherAgentRuntimeOptions(access_token="oauth-token")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_server_config(
        "Provider",
        "model",
        '{"servers":[]}',
    )

    call = fake.calls[0]
    assert call[:4] == ("json", "Provider", "model", '{"servers":[]}')
    assert call[4].access_token == "oauth-token"
    assert resolver_calls[0][1] == '{"servers":[]}'
    agent.dispose()


def test_create_with_api_key_fetches_config_before_oauth(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    server_config = '{"servers":[{"config":{"url":"https://mcp.example.com/mcp"}}]}'

    monkeypatch.setattr(
        agent_module.ServerConfig,
        "fetch",
        staticmethod(lambda api_key, route=None: server_config),
    )

    async def resolver(urls=None, server_config=None, runtime_options=None, oauth=None):
        return GopherAgentRuntimeOptions(access_token="oauth-token")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_api_key("Provider", "model", "api-key")

    call = fake.calls[0]
    assert call[:4] == ("json", "Provider", "model", server_config)
    assert call[4].access_token == "oauth-token"
    agent.dispose()


def test_create_with_server_id_fetches_routed_config(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    server_config = '{"servers":[{"id":"srv-1"}]}'
    fetch_calls = []

    def fetch(api_key, route=None):
        fetch_calls.append((api_key, route))
        return server_config

    monkeypatch.setattr(agent_module.ServerConfig, "fetch", staticmethod(fetch))

    async def resolver(urls=None, server_config=None, runtime_options=None, oauth=None):
        return GopherAgentRuntimeOptions(access_token="oauth-token")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_server_id("Provider", "model", "api-key", "srv-1")

    assert fetch_calls[0][0] == "api-key"
    assert fetch_calls[0][1].key == "serverId"
    assert fetch_calls[0][1].value == "srv-1"
    call = fake.calls[0]
    assert call[:4] == ("json", "Provider", "model", server_config)
    assert call[4].access_token == "oauth-token"
    agent.dispose()


def test_create_with_gateway_name_fetches_routed_config(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    server_config = '{"servers":[{"name":"gateway"}]}'
    fetch_calls = []

    def fetch(api_key, route=None):
        fetch_calls.append((api_key, route))
        return server_config

    monkeypatch.setattr(agent_module.ServerConfig, "fetch", staticmethod(fetch))

    async def resolver(urls=None, server_config=None, runtime_options=None, oauth=None):
        return GopherAgentRuntimeOptions(access_token="oauth-token")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_gateway_name(
        "Provider",
        "model",
        "api-key",
        "gateway",
    )

    assert fetch_calls[0][0] == "api-key"
    assert fetch_calls[0][1].key == "gatewayName"
    assert fetch_calls[0][1].value == "gateway"
    call = fake.calls[0]
    assert call[:4] == ("json", "Provider", "model", server_config)
    assert call[4].access_token == "oauth-token"
    agent.dispose()


def test_create_with_server_name_explicit_token_uses_native_selector(
    monkeypatch,
) -> None:
    fake = _install_fake_library(monkeypatch)

    async def resolver(*args, **kwargs):
        raise AssertionError("resolver should not run")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_server_name(
        "Provider",
        "model",
        "api-key",
        "server",
        {"access_token": "caller-token"},
    )

    call = fake.calls[0]
    assert call[:5] == ("server_name", "Provider", "model", "api-key", "server")
    assert call[5].access_token == "caller-token"
    agent.dispose()


def test_create_with_gateway_id_disabled_oauth_uses_native_selector(
    monkeypatch,
) -> None:
    fake = _install_fake_library(monkeypatch)

    async def resolver(*args, **kwargs):
        raise AssertionError("resolver should not run")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_runtime_options_with_oauth",
        resolver,
    )

    agent = GopherAgent.create_with_gateway_id(
        "Provider",
        "model",
        "api-key",
        "gateway-id",
        {"oauth": {"mode": "disabled"}},
    )

    assert fake.calls[0] == (
        "gateway_id",
        "Provider",
        "model",
        "api-key",
        "gateway-id",
        None,
    )
    agent.dispose()


def test_create_uses_server_config_oauth_path(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)

    async def resolver(urls=None, server_config=None, runtime_options=None, oauth=None):
        return GopherAgentRuntimeOptions(access_token="oauth-token")

    monkeypatch.setattr(
        agent_module.oauth_resolver,
        "resolve_runtime_options_with_oauth",
        resolver,
    )

    config = (
        agent_module.GopherAgentConfig.builder()
        .provider("Provider")
        .model("model")
        .server_config("{}")
        .build()
    )

    agent = GopherAgent.create(config)

    assert fake.calls[0][0] == "json"
    assert fake.calls[0][4].access_token == "oauth-token"
    agent.dispose()


def test_oauth_inside_running_event_loop_fails_clearly(monkeypatch) -> None:
    _install_fake_library(monkeypatch)

    async def create_inside_loop():
        with pytest.raises(AgentError, match="active asyncio event loop"):
            GopherAgent.create_with_url("Provider", "model", "https://mcp.example.com/mcp")

    agent_module.asyncio.run(create_inside_loop())
