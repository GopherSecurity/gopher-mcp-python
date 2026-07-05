"""Tests for Python AgentError message formatting."""

from types import SimpleNamespace

import pytest

import gopher_mcp_python.agent as agent_module
from gopher_mcp_python import AgentError, GopherAgent
from gopher_mcp_python.ffi.library import GopherOrchLibrary


class NullCreateLibrary:
    def __init__(self, message=None):
        self.message = message
        self.cleared = False

    def agent_create_by_url(self, provider, model, url, runtime_options=None):
        return None

    def get_last_error_message(self):
        return self.message

    def clear_error(self):
        self.cleared = True


def test_create_failure_uses_actionable_fallback(monkeypatch) -> None:
    fake = NullCreateLibrary()
    monkeypatch.setattr(agent_module, "_initialized", True)
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary,
        "get_instance",
        staticmethod(lambda: fake),
    )

    with pytest.raises(AgentError) as exc_info:
        GopherAgent.create_with_url(
            "Provider", "model", "http://127.0.0.1:5001/mcp"
        )

    assert "native library returned null without a specific error" in str(
        exc_info.value
    )
    assert "Set GOPHER_DEBUG=1" in str(exc_info.value)
    assert fake.cleared is True


def test_create_failure_keeps_native_error_message(monkeypatch) -> None:
    fake = NullCreateLibrary("Failed to create agent from MCP server URL: Timeout")
    monkeypatch.setattr(agent_module, "_initialized", True)
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary,
        "get_instance",
        staticmethod(lambda: fake),
    )

    with pytest.raises(AgentError) as exc_info:
        GopherAgent.create_with_url(
            "Provider", "model", "http://127.0.0.1:5001/mcp"
        )

    assert str(exc_info.value) == "Failed to create agent from MCP server URL: Timeout"
    assert fake.cleared is True


def test_last_error_message_includes_native_details(monkeypatch) -> None:
    lib = object.__new__(GopherOrchLibrary)
    error_info = SimpleNamespace(
        message=b"Failed to create agent from JSON configuration",
        details=b"No configured MCP servers connected: server-1: Init timeout after 5s",
    )
    monkeypatch.setattr(lib, "last_error", lambda: error_info)

    assert lib.get_last_error_message() == (
        "Failed to create agent from JSON configuration: "
        "No configured MCP servers connected: server-1: Init timeout after 5s"
    )
