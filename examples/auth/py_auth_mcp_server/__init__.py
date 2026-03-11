"""Python MCP server with OAuth authentication.

OAuth-protected MCP server example using gopher-auth FFI bindings.
Demonstrates JWT token validation and scope-based access control
for MCP tools.
"""

__version__ = "1.0.0"
__author__ = "Gopher Security"

from .app import cleanup_app, create_app
from .config import AuthServerConfig, create_default_config, load_config_from_file

__all__ = [
    "__version__",
    "__author__",
    "create_app",
    "cleanup_app",
    "AuthServerConfig",
    "create_default_config",
    "load_config_from_file",
]
