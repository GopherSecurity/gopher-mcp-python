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
    gopher_auth_validate_idp,
    gopher_auth_validate_all_scopes,
    gopher_auth_validate_any_scopes,
    gopher_auth_url_encode,
    gopher_auth_url_decode,
    gopher_auth_build_protected_resource_metadata,
    gopher_auth_build_oauth_server_metadata,
    gopher_auth_build_oidc_discovery_metadata,
    gopher_auth_extract_bearer_token,
    gopher_auth_extract_method,
    gopher_auth_extract_path,
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

from gopher_mcp_python.ffi.auth.session_manager import (
    GopherSessionManager,
)

from gopher_mcp_python.ffi.auth.auto_refresh import (
    AutoRefreshResult,
    gopher_auth_auto_refresh,
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
    "gopher_auth_validate_idp",
    "gopher_auth_validate_all_scopes",
    "gopher_auth_validate_any_scopes",
    "gopher_auth_url_encode",
    "gopher_auth_url_decode",
    "gopher_auth_build_protected_resource_metadata",
    "gopher_auth_build_oauth_server_metadata",
    "gopher_auth_build_oidc_discovery_metadata",
    "gopher_auth_extract_bearer_token",
    "gopher_auth_extract_method",
    "gopher_auth_extract_path",
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
    # OAuth/session helpers
    "GopherOAuthClient",
    "TokenResponse",
    "RegistrationResponse",
    "GopherSessionManager",
    "AutoRefreshResult",
    "gopher_auth_auto_refresh",
]
