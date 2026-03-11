"""Route handlers for the MCP server."""

from .health import register_health_routes
from .oauth_endpoints import register_oauth_routes

__all__ = [
    "register_health_routes",
    "register_oauth_routes",
]
