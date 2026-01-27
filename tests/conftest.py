"""Pytest configuration and fixtures for gopher-orch tests."""

import pytest

from gopher_orch.ffi.library import GopherOrchLibrary


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers",
        "requires_native: mark test as requiring the native library to be available",
    )


@pytest.fixture
def native_library():
    """Fixture that provides the native library instance.

    Skips the test if the native library is not available.
    """
    if not GopherOrchLibrary.is_available():
        pytest.skip("Native library not available")

    lib = GopherOrchLibrary.get_instance()
    if lib is None:
        pytest.skip("Failed to get library instance")

    return lib


@pytest.fixture
def server_config():
    """Fixture that provides a valid server configuration for testing."""
    return """{
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


def is_native_library_available():
    """Check if native library is available for tests.

    This function is used by pytest.mark.skipif decorators.
    """
    return GopherOrchLibrary.is_available()
