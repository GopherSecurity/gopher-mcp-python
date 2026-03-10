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

from gopher_mcp_python.ffi.auth.loader import (
    GopherAuthClientPtr,
    GopherAuthPayloadPtr,
    GopherAuthOptionsPtr,
    GopherAuthValidationResult,
    load_library,
    is_library_loaded,
    get_library,
    is_auth_available,
    get_auth_functions,
)

from gopher_mcp_python.ffi.auth.validation_options import (
    ValidationOptions,
    create_validation_options,
)

from gopher_mcp_python.ffi.auth.auth_client import (
    AuthClient,
    init_auth_library,
    shutdown_auth_library,
    get_auth_library_version,
    is_auth_library_initialized,
    generate_www_authenticate_header,
    generate_www_authenticate_header_v2,
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
    # Type functions
    "is_gopher_auth_error",
    "get_error_description",
    "create_empty_auth_context",
    # Pointer types
    "GopherAuthClientPtr",
    "GopherAuthPayloadPtr",
    "GopherAuthOptionsPtr",
    # Structures
    "GopherAuthValidationResult",
    # Loader functions
    "load_library",
    "is_library_loaded",
    "get_library",
    "is_auth_available",
    "get_auth_functions",
    # Validation options
    "ValidationOptions",
    "create_validation_options",
    # Auth client
    "AuthClient",
    "init_auth_library",
    "shutdown_auth_library",
    "get_auth_library_version",
    "is_auth_library_initialized",
    "generate_www_authenticate_header",
    "generate_www_authenticate_header_v2",
]
