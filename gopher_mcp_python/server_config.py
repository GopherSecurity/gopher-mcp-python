"""
Server configuration utilities for the Gopher Security MCP SDK.

Provides utilities for fetching and managing MCP server configurations.
"""

import os
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from gopher_mcp_python.errors import AgentError, ApiKeyError, ConnectionError
from gopher_mcp_python.ffi import GopherOrchLibrary

FETCH_TIMEOUT_SECONDS = 30
FETCH_MAX_BODY_PREVIEW = 512


@dataclass(frozen=True)
class ServerConfigRoute:
    """Scoped Gopher API route for fetching a subset of MCP servers."""

    key: str
    value: str


class ServerConfig:
    """
    Utility class for fetching server configurations.
    """

    @staticmethod
    def fetch(api_key: str, route: Optional[ServerConfigRoute] = None) -> str:
        """
        Fetch server configuration from the API.

        Args:
            api_key: API key for authentication
            route: Optional scoped server/gateway route

        Returns:
            JSON string containing server configuration

        Raises:
            ApiKeyError: If API key is invalid
            ConnectionError: If fetch fails
        """
        if not api_key:
            raise ApiKeyError("API key is required")

        if route is not None:
            return _fetch_with_route(api_key, route)

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


def _fetch_with_route(api_key: str, route: ServerConfigRoute) -> str:
    if route.key not in {"serverId", "serverName", "gatewayId", "gatewayName"}:
        raise AgentError(f"Unsupported server config route: {route.key}")

    query = urlencode({route.key: route.value})
    url = f"{_gopher_api_root()}/v1/mcp-servers?{query}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8")
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        preview = (
            f"{body[:FETCH_MAX_BODY_PREVIEW]}..."
            if len(body) > FETCH_MAX_BODY_PREVIEW
            else body
        )
        suffix = f": {preview}" if preview else ""
        raise AgentError(f"HTTP request failed with status {error.code}{suffix}")
    except TimeoutError as error:
        raise AgentError(
            f"Failed to fetch servers: request timed out after "
            f"{FETCH_TIMEOUT_SECONDS * 1000}ms"
        ) from error
    except URLError as error:
        raise AgentError(f"Failed to fetch servers: {error.reason}") from error
    except OSError as error:
        raise AgentError(f"Failed to fetch servers: {error}") from error


def _gopher_api_root() -> str:
    value = os.environ.get("GOPHER_SDK_TEST")
    if value is not None and value.strip().lower() in {"true", "1", "yes"}:
        return "https://api-test.gopher.security"
    return "https://api.gopher.security"
