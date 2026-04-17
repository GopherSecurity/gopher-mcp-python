"""Python MCP server with OAuth authentication.

Uses Server + StreamableHTTP transport and GopherAuth
from gopher_mcp_python.auth for OAuth/JWT authentication.
"""

__version__ = "1.0.0"

from .app import create_app, main

__all__ = ["__version__", "create_app", "main"]
