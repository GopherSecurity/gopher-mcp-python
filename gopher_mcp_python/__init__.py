"""
Gopher Orch Python SDK - AI Agent orchestration framework with native performance.

This module provides Python bindings to the gopher-mcp-python native library through ctypes FFI.

Example:
    >>> from gopher_mcp_python import GopherAgent, GopherAgentConfig
    >>>
    >>> # Create an agent with API key
    >>> config = (GopherAgentConfig.builder()
    ...     .provider("AnthropicProvider")
    ...     .model("claude-3-haiku-20240307")
    ...     .api_key("your-api-key")
    ...     .build())
    >>> agent = GopherAgent.create(config)
    >>>
    >>> # Run a query
    >>> answer = agent.run("What time is it in Tokyo?")
    >>> print(answer)
    >>>
    >>> # Cleanup
    >>> agent.dispose()
"""

from importlib import import_module

from gopher_mcp_python.agent import GopherAgent
from gopher_mcp_python.config import (
    GopherAgentConfig,
    GopherAgentConfigBuilder,
)
from gopher_mcp_python.runtime_options import (
    GopherAgentCreateOptions,
    GopherAgentOAuthOptions,
    GopherAgentRuntimeOptions,
    GopherAgentTokenRecord,
    GopherAgentTokenStore,
)
from gopher_mcp_python.result import AgentResult, AgentResultStatus, AgentResultBuilder
from gopher_mcp_python.errors import (
    AgentError,
    ApiKeyError,
    ConnectionError,
    TimeoutError,
)
from gopher_mcp_python.server_config import ServerConfig, ServerConfigRoute
from gopher_mcp_python.ffi import GopherOrchLibrary, GopherOrchHandle

__version__ = "0.1.2"

_AUTH_EXPORTS = {
    "GopherAuth",
    "GopherAuthError",
    "ConfigurationError",
    "InsufficientScopesError",
    "JwksError",
    "TokenExchangeError",
    "TokenValidationError",
    "has_all_scopes",
    "has_any_scope",
    "has_scope",
}

_AUTH_FFI_EXPORTS = {
    "AutoRefreshResult",
    "RegistrationResponse",
    "TokenResponse",
    "ValidationResult",
    "TokenPayload",
    "GopherAuthContext",
    "ERROR_DESCRIPTIONS",
    "get_error_description",
    "gopher_create_empty_auth_context",
    "is_gopher_auth_error",
    "GopherAuthClient",
    "GopherAuthConfig",
    "GopherOAuthClient",
    "GopherSessionManager",
    "GopherValidationOptions",
    "gopher_auth_auto_refresh",
    "gopher_auth_build_oidc_discovery_metadata",
    "gopher_auth_build_oauth_server_metadata",
    "gopher_auth_build_protected_resource_metadata",
    "gopher_auth_extract_bearer_token",
    "gopher_auth_extract_method",
    "gopher_auth_extract_path",
    "gopher_auth_url_decode",
    "gopher_auth_url_encode",
    "gopher_auth_validate_all_scopes",
    "gopher_auth_validate_any_scopes",
    "gopher_auth_validate_idp",
    "gopher_create_validation_options",
    "gopher_generate_www_authenticate_header",
    "gopher_generate_www_authenticate_header_v2",
    "gopher_get_auth_library_version",
    "gopher_init_auth_library",
    "gopher_is_auth_library_initialized",
    "gopher_shutdown_auth_library",
    "is_auth_available",
}


def __getattr__(name: str):
    if name in _AUTH_EXPORTS:
        auth = import_module("gopher_mcp_python.auth")
        value = getattr(auth, name)
        globals()[name] = value
        return value

    if name == "GopherAuthFfiError":
        from gopher_mcp_python.ffi.auth import GopherAuthError as GopherAuthFfiError

        globals()[name] = GopherAuthFfiError
        return GopherAuthFfiError

    if name in _AUTH_FFI_EXPORTS:
        ffi_auth = import_module("gopher_mcp_python.ffi.auth")
        value = getattr(ffi_auth, name)
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Main classes
    "GopherAgent",
    "GopherAgentConfig",
    "GopherAgentConfigBuilder",
    "GopherAgentCreateOptions",
    "GopherAgentOAuthOptions",
    "GopherAgentRuntimeOptions",
    "GopherAgentTokenRecord",
    "GopherAgentTokenStore",
    "AgentResult",
    "AgentResultStatus",
    "AgentResultBuilder",
    "ServerConfig",
    "ServerConfigRoute",
    # Errors
    "AgentError",
    "ApiKeyError",
    "ConnectionError",
    "TimeoutError",
    # FFI
    "GopherOrchLibrary",
    "GopherOrchHandle",
    # Auth
    "GopherAuth",
    "GopherAuthError",
    "GopherAuthFfiError",
    "AutoRefreshResult",
    "RegistrationResponse",
    "TokenResponse",
    "ValidationResult",
    "TokenPayload",
    "GopherAuthContext",
    "ERROR_DESCRIPTIONS",
    "get_error_description",
    "gopher_create_empty_auth_context",
    "is_gopher_auth_error",
    "GopherAuthClient",
    "GopherAuthConfig",
    "GopherOAuthClient",
    "GopherSessionManager",
    "GopherValidationOptions",
    "gopher_auth_auto_refresh",
    "gopher_auth_build_oidc_discovery_metadata",
    "gopher_auth_build_oauth_server_metadata",
    "gopher_auth_build_protected_resource_metadata",
    "gopher_auth_extract_bearer_token",
    "gopher_auth_extract_method",
    "gopher_auth_extract_path",
    "gopher_auth_url_decode",
    "gopher_auth_url_encode",
    "gopher_auth_validate_all_scopes",
    "gopher_auth_validate_any_scopes",
    "gopher_auth_validate_idp",
    "gopher_create_validation_options",
    "gopher_generate_www_authenticate_header",
    "gopher_generate_www_authenticate_header_v2",
    "gopher_get_auth_library_version",
    "gopher_init_auth_library",
    "gopher_is_auth_library_initialized",
    "gopher_shutdown_auth_library",
    "is_auth_available",
    "ConfigurationError",
    "InsufficientScopesError",
    "JwksError",
    "TokenExchangeError",
    "TokenValidationError",
    "has_all_scopes",
    "has_any_scope",
    "has_scope",
    # Version
    "__version__",
]
