"""
Auth FFI bindings for gopher-auth native library.

Provides Python bindings for JWT token validation and OAuth support
via the gopher-orch native library.
"""

from gopher_mcp_python.ffi.auth.types import (
    GopherAuthError,
    ERROR_DESCRIPTIONS,
    ValidationResult,
    TokenPayload,
    AuthContext,
    is_gopher_auth_error,
    get_error_description,
    create_empty_auth_context,
)

__all__ = [
    # Enums
    "GopherAuthError",
    # Constants
    "ERROR_DESCRIPTIONS",
    # Dataclasses
    "ValidationResult",
    "TokenPayload",
    "AuthContext",
    # Functions
    "is_gopher_auth_error",
    "get_error_description",
    "create_empty_auth_context",
]
