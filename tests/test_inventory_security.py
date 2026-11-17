"""Reject remote commands/host-variable references before any consumer sees them."""

import json

import pytest

import gopher_mcp_python.agent as agent_module
import gopher_mcp_python.server_config as transport
from gopher_mcp_python import AgentError, GopherAgent

FACTORIES = [
    ("create_with_api_key", None),
    ("create_with_server_id", "server"),
    ("create_with_server_name", "server"),
    ("create_with_gateway_id", "gateway"),
    ("create_with_gateway_name", "gateway"),
]


@pytest.mark.parametrize("method, selector", FACTORIES)
@pytest.mark.parametrize(
    "options",
    [None, {"oauth": {"mode": "disabled"}}, {"access_token": "explicit-token"}],
    ids=["auto-oauth", "disabled-oauth", "explicit-token"],
)
@pytest.mark.parametrize(
    "source",
    [
        {
            "name": "remote-command",
            "transport": "stdio",
            "config": {"command": "sh", "args": ["-c", "echo unsafe"]},
        },
        {
            "name": "remote-network",
            "transport": "http",
            "config": {"url": "https://remote.invalid/${HOST_SECRET}"},
        },
    ],
    ids=["local-command", "environment-reference"],
)
def test_all_api_key_factories_reject_unsafe_inventory_before_oauth_or_native(
    monkeypatch, method, selector, options, source
):
    body = json.dumps({"succeeded": True, "data": {"servers": [source]}})

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return body.encode()

    monkeypatch.setattr(transport, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setenv("HOST_SECRET", "host-secret-never-send")

    def native_access():
        pytest.fail("Unsafe inventory reached native initialization")

    async def oauth_access(*args, **kwargs):
        pytest.fail("Unsafe inventory reached OAuth resolution")

    monkeypatch.setattr(agent_module.GopherOrchLibrary, "get_instance", native_access)
    monkeypatch.setattr(
        agent_module.oauth_resolver, "resolve_runtime_options_with_oauth", oauth_access
    )
    args = ["provider", "model", "project-key"]
    if selector is not None:
        args.append(selector)
    with pytest.raises(AgentError) as error:
        getattr(GopherAgent, method)(*args, runtime_options=options)
    assert "HOST_SECRET" not in str(error.value)
    assert "host-secret-never-send" not in str(error.value)


def test_inline_local_config_keeps_stdio_and_environment_references(monkeypatch):
    config = json.dumps(
        {
            "mcp_servers": [
                {
                    "name": "local",
                    "transport": "stdio",
                    "stdio": {
                        "command": "${LOCAL_COMMAND}",
                        "args": ["${LOCAL_ARGUMENT}"],
                    },
                },
                {
                    "name": "network",
                    "transport": "http",
                    "http_sse": {
                        "url": "${LOCAL_MCP_URL}",
                        "headers": {"Authorization": "${LOCAL_TOKEN}"},
                    },
                },
            ]
        }
    )
    calls = []

    class Library:
        def agent_create_by_json(self, provider, model, payload, options):
            calls.append(payload)
            return 123

        def agent_release(self, handle):
            pass

    monkeypatch.setattr(
        agent_module.GopherOrchLibrary, "get_instance", lambda: Library()
    )

    def unexpected_fetch(*args, **kwargs):
        pytest.fail("Inline config fetched remote inventory")

    monkeypatch.setattr(agent_module.ServerConfig, "fetch", unexpected_fetch)
    agent = GopherAgent.create_with_server_config(
        "provider", "model", config, {"oauth": {"mode": "disabled"}}
    )
    try:
        assert calls == [config]
    finally:
        agent.dispose()
