"""
Auth Module - Reusable OAuth/JWT authentication for Python MCP servers.
"""

from gopher_mcp_python.auth.gopher_auth import GopherAuth
from gopher_mcp_python.auth.errors import (
    GopherAuthError,
    TokenValidationError,
    InsufficientScopesError,
    JwksError,
    ConfigurationError,
    TokenExchangeError,
)
from gopher_mcp_python.auth.scope_helpers import (
    has_scope,
    has_all_scopes,
    has_any_scope,
)

__all__ = [
    "GopherAuth",
    "GopherAuthError",
    "TokenValidationError",
    "InsufficientScopesError",
    "JwksError",
    "ConfigurationError",
    "TokenExchangeError",
    "has_scope",
    "has_all_scopes",
    "has_any_scope",
]
