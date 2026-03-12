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

from gopher_mcp_python.agent import GopherAgent
from gopher_mcp_python.config import GopherAgentConfig, GopherAgentConfigBuilder
from gopher_mcp_python.result import AgentResult, AgentResultStatus, AgentResultBuilder
from gopher_mcp_python.errors import AgentError, ApiKeyError, ConnectionError, TimeoutError
from gopher_mcp_python.server_config import ServerConfig
from gopher_mcp_python.ffi import GopherOrchLibrary

# Auth module re-exports
from gopher_mcp_python.ffi.auth import (
    # Types
    GopherAuthError,
    ValidationResult,
    TokenPayload,
    GopherAuthContext,
    # Classes
    GopherAuthClient,
    GopherValidationOptions,
    # Functions
    gopher_init_auth_library,
    gopher_shutdown_auth_library,
    is_auth_available,
)

__version__ = "0.1.2"

__all__ = [
    # Main classes
    "GopherAgent",
    "GopherAgentConfig",
    "GopherAgentConfigBuilder",
    "AgentResult",
    "AgentResultStatus",
    "AgentResultBuilder",
    "ServerConfig",
    # Errors
    "AgentError",
    "ApiKeyError",
    "ConnectionError",
    "TimeoutError",
    # FFI
    "GopherOrchLibrary",
    # Auth
    "GopherAuthError",
    "ValidationResult",
    "TokenPayload",
    "GopherAuthContext",
    "GopherAuthClient",
    "GopherValidationOptions",
    "gopher_init_auth_library",
    "gopher_shutdown_auth_library",
    "is_auth_available",
    # Version
    "__version__",
]
