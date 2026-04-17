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
    GopherAuthContext,
    is_gopher_auth_error,
    get_error_description,
    gopher_create_empty_auth_context,
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
    GopherValidationOptions,
    gopher_create_validation_options,
)

from gopher_mcp_python.ffi.auth.config_loader import (
    GopherAuthConfig,
)

from gopher_mcp_python.ffi.auth.oauth_client import (
    GopherOAuthClient,
    TokenResponse,
    RegistrationResponse,
)

from gopher_mcp_python.ffi.auth.auth_client import (
    GopherAuthClient,
    gopher_init_auth_library,
    gopher_shutdown_auth_library,
    gopher_get_auth_library_version,
    gopher_is_auth_library_initialized,
    gopher_generate_www_authenticate_header,
    gopher_generate_www_authenticate_header_v2,
)

__all__ = [
    # Enums
    "GopherAuthError",
    # Constants
    "ERROR_DESCRIPTIONS",
    # Dataclasses
    "ValidationResult",
    "TokenPayload",
    "GopherAuthContext",
    # Type functions
    "is_gopher_auth_error",
    "get_error_description",
    "gopher_create_empty_auth_context",
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
    "GopherValidationOptions",
    "gopher_create_validation_options",
    # Config loader
    "GopherAuthConfig",
    # Auth client
    "GopherAuthClient",
    "gopher_init_auth_library",
    "gopher_shutdown_auth_library",
    "gopher_get_auth_library_version",
    "gopher_is_auth_library_initialized",
    "gopher_generate_www_authenticate_header",
    "gopher_generate_www_authenticate_header_v2",
]
