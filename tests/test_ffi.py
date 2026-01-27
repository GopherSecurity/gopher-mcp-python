"""Tests for FFI bindings to the native gopher-orch library.

These tests verify that the Python side can correctly call C++ functions
through ctypes FFI bindings.
"""

import pytest

from gopher_orch.ffi.library import GopherOrchLibrary


def is_native_library_available():
    """Check if native library is available for tests."""
    return GopherOrchLibrary.is_available()


class TestGopherOrchLibrary:
    """Tests for GopherOrchLibrary ctypes bindings."""

    def test_library_is_available(self):
        """Test that the native library can be loaded."""
        available = GopherOrchLibrary.is_available()
        assert available, (
            "Native library should be available. "
            "Make sure to run ./build.sh first to build the native library."
        )

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_get_instance(self):
        """Test getting library instance."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None, "Library instance should not be None"

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_agent_create_by_json_with_valid_config(self):
        """Test creating agent with valid JSON config."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Valid server configuration JSON
        server_config = """{
            "succeeded": true,
            "code": 200000000,
            "message": "success",
            "data": {
                "servers": [
                    {
                        "version": "2025-01-09",
                        "serverId": "1",
                        "name": "test-server",
                        "transport": "http_sse",
                        "config": {"url": "http://127.0.0.1:9999/mcp", "headers": {}},
                        "connectTimeout": 5000,
                        "requestTimeout": 30000
                    }
                ]
            }
        }"""

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
    def test_agent_create_by_json_with_empty_config(self):
        """Test creating agent with empty config."""
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
    def test_agent_create_by_api_key(self):
        """Test creating agent with API key."""
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
    def test_last_error_and_clear_error(self):
        """Test error handling functions."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Try to get last error (may be None if no error)
        try:
            error_info = lib.last_error()
            # error_info may be None or have None message if no error
        except Exception as e:
            pytest.fail(f"last_error should not throw: {e}")

        # Clear error should not throw
        try:
            lib.clear_error()
        except Exception as e:
            pytest.fail(f"clear_error should not throw: {e}")

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_api_fetch_servers(self):
        """Test fetching server config from API."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Call with dummy API key - should return JSON (possibly error response)
        try:
            result = lib.api_fetch_servers("test-api-key")
            # Result may be None or contain error, but should not crash
        except Exception as e:
            pytest.fail(f"api_fetch_servers should not throw: {e}")

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_agent_run_with_none_handle(self):
        """Test running with None handle."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Running with None handle should be handled gracefully
        try:
            result = lib.agent_run(None, "test query", 1000)
            # May return None or error message, but should not crash
        except Exception:
            # Exception is acceptable for None handle
            pass

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_agent_release_with_none_handle(self):
        """Test releasing None handle."""
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
    def test_free_with_none_pointer(self):
        """Test free with None pointer."""
        lib = GopherOrchLibrary.get_instance()
        assert lib is not None

        # Free with None should be handled gracefully
        try:
            lib.free(None)
        except Exception:
            # Exception is acceptable for None pointer
            pass

    def test_get_last_error_when_library_not_loaded(self):
        """Test error helper when library might not be loaded."""
        lib = GopherOrchLibrary.get_instance()
        if lib is not None:
            error = lib.get_last_error_message()
            # Should return None gracefully, not throw
            # (error may be None or a message depending on state)
