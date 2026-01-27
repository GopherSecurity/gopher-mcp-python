"""
gopher-orch Python SDK

A Python SDK for the Gopher Orch AI Agent orchestration framework
with native performance through FFI bindings.

Example:
    >>> from gopher_orch import GopherAgent, GopherAgentConfig
    >>>
    >>> # Create agent with API key
    >>> config = GopherAgentConfig(
    ...     provider="AnthropicProvider",
    ...     model="claude-3-haiku-20240307",
    ...     api_key="your-api-key"
    ... )
    >>> agent = GopherAgent.create(config)
    >>>
    >>> # Run a query
    >>> response = agent.run("What time is it in Tokyo?")
    >>> print(response)
    >>>
    >>> # Cleanup
    >>> agent.dispose()

Or use context manager for automatic cleanup:

    >>> with GopherAgent.create(config) as agent:
    ...     response = agent.run("What time is it in Tokyo?")
    ...     print(response)
"""

from gopher_orch.agent import GopherAgent
from gopher_orch.config import GopherAgentConfig
from gopher_orch.errors import (
    AgentException,
    ApiKeyException,
    ConnectionException,
    TimeoutException,
)
from gopher_orch.result import AgentResult, AgentResultStatus

__version__ = "0.1.0"

__all__ = [
    "GopherAgent",
    "GopherAgentConfig",
    "AgentResult",
    "AgentResultStatus",
    "AgentException",
    "ConnectionException",
    "ApiKeyException",
    "TimeoutException",
    "__version__",
]
