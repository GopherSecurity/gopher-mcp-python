"""
Gopher Orch Python SDK - AI Agent orchestration framework with native performance.

This module provides Python bindings to the gopher-security-mcp native library through ctypes FFI.

Example:
    >>> from gopher_security_mcp import GopherAgent, GopherAgentConfig
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

from gopher_security_mcp.agent import GopherAgent
from gopher_security_mcp.config import GopherAgentConfig, GopherAgentConfigBuilder
from gopher_security_mcp.result import AgentResult, AgentResultStatus, AgentResultBuilder
from gopher_security_mcp.errors import AgentError, ApiKeyError, ConnectionError, TimeoutError
from gopher_security_mcp.server_config import ServerConfig
from gopher_security_mcp.ffi import GopherOrchLibrary

__version__ = "0.1.0.dev20260227124047"

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
    # Version
    "__version__",
]
