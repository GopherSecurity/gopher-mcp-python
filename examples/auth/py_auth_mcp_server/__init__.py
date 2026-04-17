"""Python MCP server with OAuth authentication.

Uses FastMCP with Streamable HTTP transport and GopherAuth
from gopher_mcp_python.auth for OAuth/JWT authentication.
"""

__version__ = "1.0.0"

from .app import create_server, main

__all__ = [
    "__version__",
    "create_server",
    "main",
]
