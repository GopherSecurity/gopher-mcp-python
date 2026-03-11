"""Route handlers for the MCP server."""

from .health import register_health_routes
from .mcp_handler import (
    JsonRpcError,
    JsonRpcErrorCode,
    JsonRpcRequest,
    JsonRpcResponse,
    McpHandler,
    ToolContentItem,
    ToolResult,
    ToolSpec,
    register_mcp_routes,
)
from .oauth_endpoints import register_oauth_routes

__all__ = [
    "register_health_routes",
    "register_oauth_routes",
    "register_mcp_routes",
    "McpHandler",
    "JsonRpcError",
    "JsonRpcErrorCode",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "ToolSpec",
    "ToolContentItem",
    "ToolResult",
]
