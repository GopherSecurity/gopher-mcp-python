"""
Tests for dynamic MCP runtime options at the ctypes FFI boundary.
"""

import ctypes

import pytest

from gopher_mcp_python.ffi.library import (
    GopherOrchAgentOptions,
    GopherOrchLibrary,
)


def _new_library(fake_lib):
    lib = object.__new__(GopherOrchLibrary)
    lib._available = True
    lib._lib = fake_lib
    return lib


def _read_options(options_ptr):
    options = ctypes.cast(
        options_ptr, ctypes.POINTER(GopherOrchAgentOptions)
    ).contents
    headers = {
        options.headers[i].name.decode("utf-8"): options.headers[i].value.decode(
            "utf-8"
        )
        for i in range(options.header_count)
    }
    access_token = (
        options.access_token.decode("utf-8") if options.access_token else None
    )
    return access_token, headers


def test_build_agent_options_maps_access_token_and_headers() -> None:
    lib = object.__new__(GopherOrchLibrary)

    storage = lib._build_agent_options(
        {"access_token": "abc123", "headers": {"X-Trace": "trace-1"}}
    )

    assert storage is not None
    access_token, headers = _read_options(storage.pointer)
    assert access_token == "abc123"
    assert headers == {
        "X-Trace": "trace-1",
        "Authorization": "Bearer abc123",
    }


def test_build_agent_options_normalizes_empty_options_to_none() -> None:
    lib = object.__new__(GopherOrchLibrary)

    assert lib._build_agent_options({"headers": {}}) is None


def test_agent_create_by_url_uses_existing_symbol_without_runtime_options() -> None:
    calls = []

    class FakeNativeLibrary:
        def gopher_orch_agent_create_by_url(self, provider, model, url):
            calls.append((provider, model, url))
            return 123

    lib = _new_library(FakeNativeLibrary())

    handle = lib.agent_create_by_url("Provider", "model", "http://127.0.0.1/mcp")

    assert handle == 123
    assert calls == [
        (b"Provider", b"model", b"http://127.0.0.1/mcp"),
    ]


def test_agent_create_by_url_uses_options_symbol_with_runtime_options() -> None:
    captured = {}

    class FakeNativeLibrary:
        def gopher_orch_agent_create_by_url_with_options(
            self, provider, model, url, options_ptr
        ):
            captured["args"] = (provider, model, url)
            captured["options"] = _read_options(options_ptr)
            return 456

    lib = _new_library(FakeNativeLibrary())

    handle = lib.agent_create_by_url(
        "Provider",
        "model",
        "http://127.0.0.1/mcp",
        {"headers": {"Authorization": "Bearer explicit"}},
    )

    assert handle == 456
    assert captured["args"] == (b"Provider", b"model", b"http://127.0.0.1/mcp")
    assert captured["options"] == (
        None,
        {"Authorization": "Bearer explicit"},
    )


def test_agent_create_by_url_requires_options_symbol_for_runtime_options() -> None:
    class FakeNativeLibrary:
        def gopher_orch_agent_create_by_url(self, provider, model, url):
            return 123

    lib = _new_library(FakeNativeLibrary())

    with pytest.raises(RuntimeError, match="does not expose agent runtime options"):
        lib.agent_create_by_url(
            "Provider",
            "model",
            "http://127.0.0.1/mcp",
            {"access_token": "abc123"},
        )
