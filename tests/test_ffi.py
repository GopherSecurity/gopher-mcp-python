"""
Tests for FFI bindings to the native gopher-security-mcp library.

These tests verify that the Python side can correctly call C++ functions
through ctypes FFI bindings.
"""

import json
import os

import pytest

from gopher_security_mcp.ffi import GopherOrchLibrary


def is_native_library_available() -> bool:
    """Check if native library is available."""
    return GopherOrchLibrary.is_available()


class TestGopherOrchLibrary:
    """Tests for GopherOrchLibrary FFI bindings."""

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
        server_config = json.dumps({
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
                        "config": {"url": "http://127.0.0.1:9999/mcp", "headers": {}},
                        "connectTimeout": 5000,
                        "requestTimeout": 30000,
                    },
                ],
            },
        })

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
