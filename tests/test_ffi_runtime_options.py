"""
Tests for dynamic MCP runtime options at the ctypes FFI boundary.
"""

import ctypes

import pytest

from gopher_mcp_python.config import GopherAgentRuntimeOptions
from gopher_mcp_python.errors import AgentError
from gopher_mcp_python.ffi.library import (
    GopherOrchAgentOptions,
    GopherOrchElicitationRequest,
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


def _read_raw_options(options_ptr):
    return ctypes.cast(options_ptr, ctypes.POINTER(GopherOrchAgentOptions)).contents


def test_agent_options_struct_matches_native_field_order() -> None:
    assert [name for name, _ctype in GopherOrchAgentOptions._fields_] == [
        "access_token",
        "headers",
        "header_count",
        "server_options",
        "server_option_count",
        "elicitation_callback",
        "elicitation_user_data",
        "elicitation_timeout_ms",
    ]


def test_build_agent_options_maps_access_token_and_headers() -> None:
    lib = object.__new__(GopherOrchLibrary)

    storage = lib._build_agent_options(
        {"access_token": "abc123", "headers": {"X-Trace": "trace-1"}}
    )

    assert storage is not None
    raw_options = _read_raw_options(storage.pointer)
    access_token, headers = _read_options(storage.pointer)
    assert access_token == "abc123"
    assert headers == {
        "X-Trace": "trace-1",
        "Authorization": "Bearer abc123",
    }
    assert not raw_options.server_options
    assert raw_options.server_option_count == 0
    assert not raw_options.elicitation_callback
    assert not raw_options.elicitation_user_data
    assert raw_options.elicitation_timeout_ms == 0


def test_build_agent_options_normalizes_empty_options_to_none() -> None:
    lib = object.__new__(GopherOrchLibrary)

    assert lib._build_agent_options({"headers": {}}) is None


def test_build_agent_options_normalizes_empty_access_token_to_none() -> None:
    lib = object.__new__(GopherOrchLibrary)

    assert lib._build_agent_options({"access_token": ""}) is None
    assert lib._build_agent_options(GopherAgentRuntimeOptions(access_token="")) is None


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

    with pytest.raises(AgentError, match="does not expose agent runtime options"):
        lib.agent_create_by_url(
            "Provider",
            "model",
            "http://127.0.0.1/mcp",
            {"access_token": "abc123"},
        )


def test_build_agent_options_requires_elicitation_support() -> None:
    lib = object.__new__(GopherOrchLibrary)
    lib._lib = None
    lib._loaded_native_package_version = "0.1.32"

    with pytest.raises(AgentError, match="elicitation callback support"):
        lib._build_agent_options({"elicitation": {}})


def test_build_agent_options_maps_elicitation_callback(monkeypatch) -> None:
    lib = object.__new__(GopherOrchLibrary)
    lib._lib = None
    lib._loaded_native_package_version = "0.1.35"
    seen = []

    def handler(request):
        seen.append(request)
        return "accept"

    storage = lib._build_agent_options(
        {"elicitation": {"handler": handler, "timeout_ms": 1234}}
    )

    assert storage is not None
    raw_options = _read_raw_options(storage.pointer)
    assert raw_options.elicitation_callback
    assert raw_options.elicitation_timeout_ms == 1234

    request = GopherOrchElicitationRequest(
        b'"1"',
        b"elicit-1",
        b"url",
        b"Connect",
        b"https://auth.example.com",
        b'{"method":"elicitation/create"}',
        b'{"url":"https://auth.example.com"}',
    )

    action = storage.elicitation_callback(ctypes.byref(request), None)

    assert action == 1
    assert seen[0].mode == "url"
    assert seen[0].elicitation_id == "elicit-1"
    assert seen[0].url == "https://auth.example.com"


def test_elicitation_callback_errors_return_cancel() -> None:
    lib = object.__new__(GopherOrchLibrary)
    lib._lib = None
    lib._loaded_native_package_version = "0.1.35"

    def handler(request):
        raise RuntimeError("boom")

    storage = lib._build_agent_options({"elicitation": {"handler": handler}})
    raw_options = _read_raw_options(storage.pointer)
    request = GopherOrchElicitationRequest(None, None, b"url", None, None, None, None)

    assert storage.elicitation_callback(ctypes.byref(request), None) == 3


def test_agent_create_by_url_retains_and_releases_elicitation_options() -> None:
    captured = {}
    releases = []

    class FakeNativeLibrary:
        def gopher_orch_agent_options_supports_elicitation(self):
            return 1

        def gopher_orch_agent_create_by_url_with_options(
            self, provider, model, url, options_ptr
        ):
            captured["options"] = _read_raw_options(options_ptr)
            return 789

        def gopher_orch_agent_release(self, handle):
            releases.append(handle)

    lib = _new_library(FakeNativeLibrary())
    lib._loaded_native_package_version = None
    lib._agent_option_storage = {}

    handle = lib.agent_create_by_url(
        "Provider",
        "model",
        "http://127.0.0.1/mcp",
        {"elicitation": {"handler": lambda request: "accept"}},
    )

    assert handle == 789
    assert 789 in lib._agent_option_storage
    assert captured["options"].elicitation_callback

    lib.agent_release(handle)

    assert releases == [789]
    assert lib._agent_option_storage == {}
