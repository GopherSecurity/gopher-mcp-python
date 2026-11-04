"""Tests for GopherAgent lifecycle cleanup."""

import gc
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor

import pytest

import gopher_mcp_python.agent as agent_module
from gopher_mcp_python import GopherAgent
from gopher_mcp_python.errors import AgentError
from gopher_mcp_python.ffi.library import GopherOrchLibrary


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


@pytest.mark.parametrize("fail", [False, True])
def test_dispose_defers_release_until_active_run_exits(monkeypatch, fail):
    fake = _install_fake_library(monkeypatch)
    entered, finish = threading.Event(), threading.Event()

    def run(*args):
        entered.set()
        assert finish.wait(5)
        assert fake.calls == []
        if fail:
            raise ValueError("run failed")
        return "answer"

    fake.agent_run = run
    agent = GopherAgent(4005)
    with ThreadPoolExecutor(max_workers=8) as pool:
        query = pool.submit(agent.run, "question")
        try:
            assert entered.wait(5)
            with pytest.raises(AgentError, match="already running"):
                agent.run("overlap")
            disposals = [pool.submit(agent.dispose) for _ in range(6)]
            for disposal in disposals:
                disposal.result(5)
            assert agent.is_disposed()
            assert fake.calls == []
            with pytest.raises(AgentError, match="disposed"):
                agent.run("late")
        finally:
            finish.set()
        if fail:
            with pytest.raises(AgentError, match="run failed"):
                query.result(5)
        else:
            assert query.result(5) == "answer"
    assert fake.calls == [("release", 4005)]


def test_callback_can_dispose_agent_without_waiting(monkeypatch):
    fake = _install_fake_library(monkeypatch)
    agent = GopherAgent(4006)

    def run(*args):
        # Native callbacks may arrive on a different thread from run().
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(agent.dispose).result(5)
        assert fake.calls == []
        return "answer"

    fake.agent_run = run
    assert agent.run("question") == "answer"
    assert fake.calls == [("release", 4006)]


def test_agent_keeps_creating_library_for_run_and_cleanup(monkeypatch):
    original = _install_fake_library(monkeypatch)
    original.agent_run = lambda *args: "answer"
    agent = GopherAgent(4007)
    replacement = _install_fake_library(monkeypatch)
    assert agent.run("question") == "answer"
    agent.dispose()
    assert original.calls == [("release", 4007)]
    assert replacement.calls == []


@pytest.mark.parametrize("available", [True, False])
def test_concurrent_library_initialization_publishes_one_instance(monkeypatch, available):
    entered, finish = threading.Event(), threading.Event()
    loads = []

    def load(self):
        loads.append(self)
        entered.set()
        assert finish.wait(5)
        self._available = available

    monkeypatch.setattr(GopherOrchLibrary, "_instance", None)
    monkeypatch.setattr(GopherOrchLibrary, "_load_library", load)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(GopherOrchLibrary.get_instance) for _ in range(8)]
        try:
            assert entered.wait(5)
            assert GopherOrchLibrary._instance is None
        finally:
            finish.set()
        instances = [future.result(5) for future in futures]
    assert len(loads) == 1
    assert all(instance is (loads[0] if available else None) for instance in instances)


def test_concurrent_agent_initialization_registers_cleanup_once(monkeypatch):
    fake = _install_fake_library(monkeypatch)
    monkeypatch.setattr(agent_module, "_initialized", False)
    monkeypatch.setattr(agent_module, "_cleanup_handler_registered", False)
    registrations = []
    monkeypatch.setattr(agent_module.atexit, "register", registrations.append)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: GopherAgent.init(), range(32)))
    assert GopherAgent.is_initialized()
    assert registrations == [GopherAgent.shutdown]
