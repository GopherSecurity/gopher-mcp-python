"""
Server configuration utilities for the Gopher Orch SDK.

Provides utilities for fetching and managing MCP server configurations.
"""

from typing import Optional
from gopher_orch.ffi import GopherOrchLibrary
from gopher_orch.errors import ApiKeyError, ConnectionError


class ServerConfig:
    """
    Utility class for fetching server configurations.
    """

    @staticmethod
    def fetch(api_key: str) -> str:
        """
        Fetch server configuration from the API.

        Args:
            api_key: API key for authentication

        Returns:
            JSON string containing server configuration

        Raises:
            ApiKeyError: If API key is invalid
            ConnectionError: If fetch fails
        """
        if not api_key:
            raise ApiKeyError("API key is required")

        lib = GopherOrchLibrary.get_instance()
        if lib is None:
            raise ConnectionError("Native library not available")

        result = lib.api_fetch_servers(api_key)
        if result is None:
            error_msg = lib.get_last_error_message()
            lib.clear_error()
            if error_msg and "api key" in error_msg.lower():
                raise ApiKeyError(error_msg)
            raise ConnectionError(error_msg or "Failed to fetch server configuration")

        return result
