"""
GopherAgent - Main entry point for the gopher-mcp-python Python SDK.

Provides a clean, Pythonic interface to the gopher-mcp-python agent functionality.

Example:
    # Create an agent with API key
    config = (GopherAgentConfig.builder()
        .provider("AnthropicProvider")
        .model("claude-3-haiku-20240307")
        .api_key("your-api-key")
        .build())

    agent = GopherAgent.create(config)

    # Run a query
    answer = agent.run("What time is it in Tokyo?")
    print(answer)

    # Cleanup
    agent.dispose()

Example with context manager:
    with GopherAgent.create(config) as agent:
        answer = agent.run("What time is it in Tokyo?")
        print(answer)
"""

import atexit
from typing import Optional

from gopher_mcp_python.config import GopherAgentConfig
from gopher_mcp_python.result import AgentResult, AgentResultStatus
from gopher_mcp_python.errors import AgentError, TimeoutError
from gopher_mcp_python.ffi import GopherOrchLibrary, GopherOrchHandle


_initialized = False
_cleanup_handler_registered = False


class GopherAgent:
    """
    Main agent class for interacting with the gopher-mcp-python native library.
    """

    def __init__(self, handle: GopherOrchHandle) -> None:
        """
        Initialize a GopherAgent with a native handle.

        Note: Use create() factory method instead of direct instantiation.
        """
        self._handle = handle
        self._disposed = False

    def __enter__(self) -> "GopherAgent":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with automatic cleanup."""
        self.dispose()

    @staticmethod
    def init() -> None:
        """
        Initialize the gopher-mcp-python library.

        Must be called before creating any agents. Called automatically by
        create() if not already initialized.

        Raises:
            AgentError: if initialization fails
        """
        global _initialized
        if _initialized:
            return

        lib = GopherOrchLibrary.get_instance()
        if lib is None:
            raise AgentError("Failed to load gopher-mcp-python native library")

        _initialized = True
        _setup_cleanup_handler()

    @staticmethod
    def shutdown() -> None:
        """
        Shutdown the gopher-mcp-python library.

        Called automatically on process exit, but can be called manually.
        """
        global _initialized
        _initialized = False

    @staticmethod
    def is_initialized() -> bool:
        """Check if the library is initialized."""
        return _initialized

    @staticmethod
    def create(config: GopherAgentConfig) -> "GopherAgent":
        """
        Create a new GopherAgent instance.

        Args:
            config: Agent configuration

        Returns:
            GopherAgent instance

        Raises:
            AgentError: if agent creation fails
        """
        if not _initialized:
            GopherAgent.init()

        lib = GopherOrchLibrary.get_instance()
        if lib is None:
            raise AgentError("Native library not available")

        handle: Optional[GopherOrchHandle] = None
        try:
            if config.has_api_key():
                handle = lib.agent_create_by_api_key(
                    config.provider, config.model, config.api_key
                )
            else:
                handle = lib.agent_create_by_json(
                    config.provider, config.model, config.server_config
                )
        except Exception as e:
            raise AgentError(f"Failed to create agent: {e}")

        if handle is None:
            error = lib.get_last_error_message()
            lib.clear_error()
            raise AgentError(error or "Failed to create agent")

        return GopherAgent(handle)

    @staticmethod
    def create_with_api_key(provider: str, model: str, api_key: str) -> "GopherAgent":
        """
        Create a new GopherAgent with API key.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model name (e.g., "claude-3-haiku-20240307")
            api_key: API key for fetching remote server config

        Returns:
            GopherAgent instance
        """
        return GopherAgent.create(
            GopherAgentConfig.builder()
            .provider(provider)
            .model(model)
            .api_key(api_key)
            .build()
        )

    @staticmethod
    def create_with_server_config(
        provider: str, model: str, server_config: str
    ) -> "GopherAgent":
        """
        Create a new GopherAgent with JSON server config.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model name (e.g., "claude-3-haiku-20240307")
            server_config: JSON server configuration

        Returns:
            GopherAgent instance
        """
        return GopherAgent.create(
            GopherAgentConfig.builder()
            .provider(provider)
            .model(model)
            .server_config(server_config)
            .build()
        )

    def run(self, query: str, timeout_ms: int = 60000) -> str:
        """
        Run a query against the agent.

        Args:
            query: The user query to process
            timeout_ms: Timeout in milliseconds (default: 60000)

        Returns:
            The agent's response

        Raises:
            AgentError: if the query fails
        """
        self._ensure_not_disposed()

        lib = GopherOrchLibrary.get_instance()
        if lib is None:
            raise AgentError("Native library not available")

        try:
            response = lib.agent_run(self._handle, query, timeout_ms)
            if response is None:
                return f'No response for query: "{query}"'
            return response
        except Exception as e:
            raise AgentError(f"Query execution failed: {e}")

    def run_detailed(self, query: str, timeout_ms: int = 60000) -> AgentResult:
        """
        Run a query with detailed result information.

        Args:
            query: The user query to process
            timeout_ms: Timeout in milliseconds (default: 60000)

        Returns:
            AgentResult with response and metadata
        """
        try:
            response = self.run(query, timeout_ms)
            return (
                AgentResult.builder()
                .response(response)
                .status(AgentResultStatus.SUCCESS)
                .iteration_count(1)
                .tokens_used(0)
                .build()
            )
        except TimeoutError as e:
            return AgentResult.timeout(str(e))
        except Exception as e:
            return AgentResult.error(str(e))

    def dispose(self) -> None:
        """Dispose of the agent and free resources."""
        if self._disposed:
            return

        self._disposed = True
        lib = GopherOrchLibrary.get_instance()
        if lib is not None and self._handle is not None:
            lib.agent_release(self._handle)

    def is_disposed(self) -> bool:
        """Check if agent is disposed."""
        return self._disposed

    def _ensure_not_disposed(self) -> None:
        """Ensure agent has not been disposed."""
        if self._disposed:
            raise AgentError("Agent has been disposed")


def _setup_cleanup_handler() -> None:
    """Register cleanup handler for process exit."""
    global _cleanup_handler_registered
    if _cleanup_handler_registered:
        return

    _cleanup_handler_registered = True
    atexit.register(GopherAgent.shutdown)
