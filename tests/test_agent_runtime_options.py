"""
Tests for public GopherAgent runtime option passthrough.
"""

import pytest

import gopher_mcp_python.agent as agent_module
from gopher_mcp_python import AgentError, GopherAgent, GopherAgentConfig


class FakeLibrary:
    def __init__(self) -> None:
        self.calls = []

    def agent_create_by_api_key(self, provider, model, api_key, runtime_options=None):
        self.calls.append(
            ("api_key", provider, model, api_key, runtime_options)
        )
        return 1001

    def agent_create_by_json(
        self, provider, model, server_config, runtime_options=None
    ):
        self.calls.append(
            ("json", provider, model, server_config, runtime_options)
        )
        return 1002

    def agent_create_by_server_id(
        self, provider, model, api_key, server_id, runtime_options=None
    ):
        self.calls.append(
            ("server_id", provider, model, api_key, server_id, runtime_options)
        )
        return 1003

    def agent_create_by_server_name(
        self, provider, model, api_key, server_name, runtime_options=None
    ):
        self.calls.append(
            ("server_name", provider, model, api_key, server_name, runtime_options)
        )
        return 1004

    def agent_create_by_gateway_id(
        self, provider, model, api_key, gateway_id, runtime_options=None
    ):
        self.calls.append(
            ("gateway_id", provider, model, api_key, gateway_id, runtime_options)
        )
        return 1005

    def agent_create_by_gateway_name(
        self, provider, model, api_key, gateway_name, runtime_options=None
    ):
        self.calls.append(
            ("gateway_name", provider, model, api_key, gateway_name, runtime_options)
        )
        return 1006

    def agent_create_by_url(self, provider, model, url, runtime_options=None):
        self.calls.append(("url", provider, model, url, runtime_options))
        return 1007

    def agent_release(self, handle):
        self.calls.append(("release", handle))

    def get_last_error_message(self):
        return None

    def clear_error(self):
        self.calls.append(("clear_error",))


@pytest.fixture()
def fake_library(monkeypatch):
    fake = FakeLibrary()
    monkeypatch.setattr(agent_module, "_initialized", True)
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary,
        "get_instance",
        staticmethod(lambda: fake),
    )
    return fake


def _assert_normalized_options(options, expected_headers):
    assert options is not None
    assert options.headers == expected_headers


def test_create_passes_runtime_options_for_api_key_config(fake_library) -> None:
    config = (
        GopherAgentConfig.builder()
        .provider("Provider")
        .model("model")
        .api_key("api-key")
        .access_token("abc123")
        .build()
    )

    agent = GopherAgent.create(config)

    call = fake_library.calls[0]
    assert call[:4] == ("api_key", "Provider", "model", "api-key")
    _assert_normalized_options(call[4], {"Authorization": "Bearer abc123"})
    agent.dispose()


def test_create_passes_runtime_options_for_server_config(fake_library) -> None:
    config = (
        GopherAgentConfig.builder()
        .provider("Provider")
        .model("model")
        .server_config("{}")
        .headers({"X-Trace": "trace-1"})
        .build()
    )

    agent = GopherAgent.create(config)

    call = fake_library.calls[0]
    assert call[:4] == ("json", "Provider", "model", "{}")
    _assert_normalized_options(call[4], {"X-Trace": "trace-1"})
    agent.dispose()


def test_create_with_api_key_accepts_runtime_options(fake_library) -> None:
    agent = GopherAgent.create_with_api_key(
        "Provider",
        "model",
        "api-key",
        {"headers": {"X-Trace": "trace-1"}},
    )

    call = fake_library.calls[0]
    assert call[:4] == ("api_key", "Provider", "model", "api-key")
    _assert_normalized_options(call[4], {"X-Trace": "trace-1"})
    agent.dispose()


@pytest.mark.parametrize(
    "factory, expected",
    [
        (
            lambda options: GopherAgent.create_with_server_id(
                "Provider", "model", "api-key", "srv-1", options
            ),
            ("server_id", "Provider", "model", "api-key", "srv-1"),
        ),
        (
            lambda options: GopherAgent.create_with_server_name(
                "Provider", "model", "api-key", "weather", options
            ),
            ("server_name", "Provider", "model", "api-key", "weather"),
        ),
        (
            lambda options: GopherAgent.create_with_gateway_id(
                "Provider", "model", "api-key", "gw-1", options
            ),
            ("gateway_id", "Provider", "model", "api-key", "gw-1"),
        ),
        (
            lambda options: GopherAgent.create_with_gateway_name(
                "Provider", "model", "api-key", "main", options
            ),
            ("gateway_name", "Provider", "model", "api-key", "main"),
        ),
        (
            lambda options: GopherAgent.create_with_url(
                "Provider", "model", "http://127.0.0.1:5001/mcp", options
            ),
            ("url", "Provider", "model", "http://127.0.0.1:5001/mcp"),
        ),
    ],
)
def test_direct_factories_pass_runtime_options(fake_library, factory, expected) -> None:
    runtime_options = {"access_token": "abc123"}

    agent = factory(runtime_options)

    call = fake_library.calls[0]
    assert call[:-1] == expected
    _assert_normalized_options(call[-1], {"Authorization": "Bearer abc123"})
    agent.dispose()


def test_direct_factory_normalizes_empty_runtime_options(fake_library) -> None:
    agent = GopherAgent.create_with_url(
        "Provider",
        "model",
        "http://127.0.0.1:5001/mcp",
        {"access_token": ""},
    )

    call = fake_library.calls[0]
    assert call == ("url", "Provider", "model", "http://127.0.0.1:5001/mcp", None)
    agent.dispose()


def test_direct_factory_rejects_invalid_runtime_options_before_ffi(
    fake_library,
) -> None:
    with pytest.raises(ValueError, match="headers must be a string mapping"):
        GopherAgent.create_with_url(
            "Provider",
            "model",
            "http://127.0.0.1:5001/mcp",
            {"headers": {"X-Test": 1}},
        )

    assert fake_library.calls == []


def test_runtime_options_native_error_surfaces_as_agent_error(fake_library) -> None:
    def fail(provider, model, url, runtime_options=None):
        raise RuntimeError("native options symbol missing")

    fake_library.agent_create_by_url = fail

    with pytest.raises(AgentError, match="native options symbol missing"):
        GopherAgent.create_with_url(
            "Provider",
            "model",
            "http://127.0.0.1:5001/mcp",
            {"access_token": "abc123"},
        )
