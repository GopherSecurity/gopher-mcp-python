"""
Tests for FFI bindings to the native gopher-mcp-python library.

These tests verify that the Python side can correctly call C++ functions
through ctypes FFI bindings.
"""

import json
import os
from ctypes import c_char_p, c_int, c_void_p

import pytest

import gopher_mcp_python.agent as agent_module
from gopher_mcp_python import AgentError, GopherAgent
from gopher_mcp_python.ffi import GopherOrchLibrary


def is_native_library_available() -> bool:
    """Check if native library is available."""
    return GopherOrchLibrary.is_available()


class TestGopherOrchLibrary:
    """Tests for GopherOrchLibrary FFI bindings."""

    def test_should_bind_present_optional_routing_symbols_independently(self):
        """Missing optional symbols must not skip binding later symbols."""

        class FakeFunction:
            def __init__(self):
                self.argtypes = None
                self.restype = c_int

            def __call__(self, *args):
                return None

        class FakeLib:
            missing = {"gopher_orch_agent_create_by_server_id"}

            def __init__(self):
                names = [
                    "gopher_orch_agent_create_by_json",
                    "gopher_orch_agent_create_by_api_key",
                    "gopher_orch_agent_create_by_server_name",
                    "gopher_orch_agent_create_by_gateway_id",
                    "gopher_orch_agent_create_by_gateway_name",
                    "gopher_orch_agent_create_by_url",
                    "gopher_orch_agent_run",
                    "gopher_orch_agent_add_ref",
                    "gopher_orch_agent_release",
                    "gopher_orch_api_fetch_servers",
                    "gopher_orch_last_error",
                    "gopher_orch_clear_error",
                    "gopher_orch_free",
                    "gopher_orch_set_log_level",
                ]
                self._functions = {name: FakeFunction() for name in names}

            def __getattr__(self, name):
                if name in self.missing:
                    raise AttributeError(name)
                try:
                    return self._functions[name]
                except KeyError:
                    raise AttributeError(name) from None

        fake_lib = FakeLib()
        lib = GopherOrchLibrary.__new__(GopherOrchLibrary)
        lib._lib = fake_lib

        lib._setup_functions()

        assert fake_lib.gopher_orch_agent_create_by_server_name.restype is c_void_p
        assert fake_lib.gopher_orch_agent_create_by_gateway_id.restype is c_void_p
        assert fake_lib.gopher_orch_agent_create_by_gateway_name.restype is c_void_p
        assert fake_lib.gopher_orch_agent_create_by_url.restype is c_void_p
        assert fake_lib.gopher_orch_agent_create_by_url.argtypes == [
            c_char_p,
            c_char_p,
            c_char_p,
        ]
        assert fake_lib.gopher_orch_agent_run.restype is c_void_p
        assert fake_lib.gopher_orch_api_fetch_servers.restype is c_void_p

    def test_agent_run_decodes_and_frees_owned_string(self):
        """Owned run responses must be released with gopher_orch_free."""

        class FakeLib:
            def __init__(self):
                self.buffer = b"agent response"
                self.freed = []

            def gopher_orch_agent_run(self, agent, query, timeout_ms):
                return c_char_p(self.buffer)

            def gopher_orch_free(self, ptr):
                self.freed.append(ptr)

        fake_lib = FakeLib()
        lib = GopherOrchLibrary.__new__(GopherOrchLibrary)
        lib._available = True
        lib._lib = fake_lib

        assert lib.agent_run(c_void_p(123), "hello", 1000) == "agent response"
        assert len(fake_lib.freed) == 1

    def test_api_fetch_servers_decodes_and_frees_owned_string(self):
        """Owned API config responses must be released with gopher_orch_free."""

        class FakeLib:
            def __init__(self):
                self.buffer = b'{"succeeded":true}'
                self.freed = []

            def gopher_orch_api_fetch_servers(self, api_key):
                return c_char_p(self.buffer)

            def gopher_orch_free(self, ptr):
                self.freed.append(ptr)

        fake_lib = FakeLib()
        lib = GopherOrchLibrary.__new__(GopherOrchLibrary)
        lib._available = True
        lib._lib = fake_lib

        assert lib.api_fetch_servers("key") == '{"succeeded":true}'
        assert len(fake_lib.freed) == 1

    def test_owned_string_null_return_is_not_freed(self):
        """Null native string returns should stay None without a free call."""

        class FakeLib:
            def __init__(self):
                self.freed = []

            def gopher_orch_agent_run(self, agent, query, timeout_ms):
                return None

            def gopher_orch_free(self, ptr):
                self.freed.append(ptr)

        fake_lib = FakeLib()
        lib = GopherOrchLibrary.__new__(GopherOrchLibrary)
        lib._available = True
        lib._lib = fake_lib

        assert lib.agent_run(c_void_p(123), "hello", 1000) is None
        assert fake_lib.freed == []

    def test_missing_optional_routing_symbol_raises_upgrade_error(self):
        """Absent routing factories should not look like native NULL returns."""

        class FakeLib:
            pass

        lib = GopherOrchLibrary.__new__(GopherOrchLibrary)
        lib._available = True
        lib._lib = FakeLib()

        with pytest.raises(AgentError, match="predates the routing factories"):
            lib.agent_create_by_url(
                "AnthropicProvider", "claude-3-haiku-20240307", "http://x/mcp"
            )

    def test_public_factory_surfaces_missing_routing_symbol_message(
        self, monkeypatch
    ):
        """AgentError should tell users to upgrade when the native symbol is absent."""

        class FakeLib:
            def agent_create_by_url(self, provider, model, url, runtime_options=None):
                raise RuntimeError(
                    "this build of libgopher-orch predates the routing factories; "
                    "upgrade to a native gopher-orch library release that includes "
                    "them"
                )

        monkeypatch.setattr(agent_module, "_initialized", True)
        monkeypatch.setattr(
            GopherOrchLibrary,
            "get_instance",
            classmethod(lambda cls: FakeLib()),
        )

        with pytest.raises(AgentError) as exc_info:
            GopherAgent.create_with_url(
                "AnthropicProvider", "claude-3-haiku-20240307", "http://x/mcp"
            )

        assert "predates the routing factories" in str(exc_info.value)
        assert "upgrade to a native gopher-orch library release" in str(
            exc_info.value
        )

    def test_library_should_be_available(self):
        """Test that library should be available."""
        available = GopherOrchLibrary.is_available()
        assert available is True, (
            "Native library should be available. "
            "Make sure to run ./build.sh first to build the native library."
        )

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_get_library_instance(self):
        """Test getting library instance."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_create_agent_by_json_with_valid_config(self):
        """Test creating agent by JSON with valid config."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Valid server configuration JSON
        server_config = json.dumps(
            {
                "succeeded": True,
                "code": 200000000,
                "message": "success",
                "data": {
                    "servers": [
                        {
                            "version": "2025-01-09",
                            "serverId": "1",
                            "name": "test-server",
                            "transport": "http_sse",
                            "config": {
                                "url": "http://127.0.0.1:9999/mcp",
                                "headers": {},
                            },
                            "connectTimeout": 5000,
                            "requestTimeout": 30000,
                        },
                    ],
                },
            }
        )

        # Call native function to create agent
        handle = lib.agent_create_by_json(
            "AnthropicProvider", "claude-3-haiku-20240307", server_config
        )

        # Agent should be created (handle may be None if no API key, but function should not crash)
        # The important thing is that the FFI call works without throwing
        if handle is not None:
            # Clean up if agent was created
            lib.agent_release(handle)

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_handle_agent_create_by_json_with_empty_config(self):
        """Test creating agent by JSON with empty config."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Empty/invalid config should return None handle
        handle = lib.agent_create_by_json(
            "AnthropicProvider", "claude-3-haiku-20240307", "{}"
        )

        # Should handle gracefully (None or valid pointer, but no crash)
        if handle is not None:
            lib.agent_release(handle)

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_create_agent_by_api_key(self):
        """Test creating agent by API key."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Call with a dummy API key - should not crash
        handle = lib.agent_create_by_api_key(
            "AnthropicProvider", "claude-3-haiku-20240307", "test-api-key-12345"
        )

        # May return None if API key is invalid, but should not crash
        if handle is not None:
            lib.agent_release(handle)

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_handle_last_error_and_clear_error(self):
        """Test handling last error and clearing error."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Try to get last error (may be None if no error)
        # Should not raise exception
        lib.last_error()

        # Clear error should not raise exception
        lib.clear_error()

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_fetch_servers_via_api(self):
        """Test fetching servers via API."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Call with dummy API key - should return JSON (possibly error response)
        # Should not raise exception
        lib.api_fetch_servers("test-api-key")

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_handle_agent_run_with_none_handle(self):
        """Test handling agent run with None handle."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Running with None handle should be handled gracefully
        try:
            lib.agent_run(None, "test query", 1000)
            # May return None or error message, but should not crash
        except Exception:
            # Exception is acceptable for None handle
            pass

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_handle_agent_release_with_none_handle(self):
        """Test handling agent release with None handle."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Releasing None handle should be handled gracefully
        try:
            lib.agent_release(None)
        except Exception:
            # Exception is acceptable for None handle
            pass

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_handle_free_with_none_pointer(self):
        """Test handling free with None pointer."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Free with None should be handled gracefully
        try:
            lib.free(None)
        except Exception:
            # Exception is acceptable for None pointer
            pass

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_should_get_last_error_message_gracefully(self):
        """Test getting last error message gracefully."""
        lib = GopherOrchLibrary.get_instance()
        if lib is not None:
            # Should return None gracefully, not raise exception
            lib.get_last_error_message()
