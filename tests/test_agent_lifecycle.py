"""Tests for GopherAgent lifecycle cleanup."""

import gc
import weakref

import gopher_mcp_python.agent as agent_module
from gopher_mcp_python import GopherAgent


class FakeLibrary:
    def __init__(self) -> None:
        self.calls = []

    def agent_release(self, handle):
        self.calls.append(("release", handle))


def _install_fake_library(monkeypatch):
    fake = FakeLibrary()
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary,
        "get_instance",
        staticmethod(lambda: fake),
    )
    return fake


def test_dispose_is_idempotent(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    agent = GopherAgent(4001)

    agent.dispose()
    agent.dispose()

    assert agent.is_disposed() is True
    assert fake.calls == [("release", 4001)]


def test_context_manager_cleanup_uses_dispose(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)

    with GopherAgent(4002) as agent:
        assert agent.is_disposed() is False

    assert agent.is_disposed() is True
    assert fake.calls == [("release", 4002)]


def test_finalizer_releases_undisposed_agent(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    agent = GopherAgent(4003)
    ref = weakref.ref(agent)

    del agent
    for _ in range(5):
        gc.collect()
        if ref() is None:
            break

    assert ref() is None
    assert fake.calls.count(("release", 4003)) == 1


def test_dispose_detaches_finalizer(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    agent = GopherAgent(4004)
    ref = weakref.ref(agent)

    agent.dispose()
    del agent
    for _ in range(5):
        gc.collect()
        if ref() is None:
            break

    assert ref() is None
    assert fake.calls.count(("release", 4004)) == 1
