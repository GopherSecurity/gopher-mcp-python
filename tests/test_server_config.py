"""Tests for Gopher API server config fetching."""

from urllib.error import HTTPError

import pytest

import gopher_mcp_python.server_config as server_config_module
from gopher_mcp_python.errors import AgentError
from gopher_mcp_python.server_config import ServerConfig, ServerConfigRoute


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        return None


def test_fetch_with_route_uses_scoped_test_api_url(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(b'{"servers":[]}')

    monkeypatch.setenv("GOPHER_SDK_TEST", "true")
    monkeypatch.setattr(server_config_module, "urlopen", fake_urlopen)

    result = ServerConfig.fetch(
        "api-key",
        route=ServerConfigRoute("serverName", "Draft Mail"),
    )

    request, timeout = requests[0]
    assert result == '{"servers":[]}'
    assert timeout == server_config_module.FETCH_TIMEOUT_SECONDS
    assert request.full_url == (
        "https://api-test.gopher.security/v1/mcp-servers?"
        "serverName=Draft+Mail"
    )
    assert request.headers["Authorization"] == "Bearer api-key"
    assert request.headers["Accept"] == "application/json"


def test_fetch_with_route_rejects_unknown_route_key() -> None:
    with pytest.raises(AgentError, match="Unsupported server config route"):
        ServerConfig.fetch("api-key", route=ServerConfigRoute("bad", "value"))


def test_fetch_with_route_includes_http_error_preview(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            403,
            "Forbidden",
            hdrs=None,
            fp=FakeResponse(b"denied"),
        )

    monkeypatch.delenv("GOPHER_SDK_TEST", raising=False)
    monkeypatch.setattr(server_config_module, "urlopen", fake_urlopen)

    with pytest.raises(AgentError, match="HTTP request failed with status 403: denied"):
        ServerConfig.fetch("api-key", route=ServerConfigRoute("serverId", "srv-1"))
