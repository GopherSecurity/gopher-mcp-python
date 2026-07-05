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
from typing import Callable, Optional

from gopher_mcp_python.config import GopherAgentConfig
from gopher_mcp_python.runtime_options import (
    RuntimeOptionsInput,
    normalize_runtime_options,
)
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
                    config.provider,
                    config.model,
                    config.api_key,
                    config.runtime_options,
                )
            else:
                handle = lib.agent_create_by_json(
                    config.provider,
                    config.model,
                    config.server_config,
                    config.runtime_options,
                )
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(f"Failed to create agent: {e}")

        if handle is None:
            error = lib.get_last_error_message()
            lib.clear_error()
            raise AgentError(error or _build_create_error_message())

        return GopherAgent(handle)

    @staticmethod
    def create_with_api_key(
        provider: str,
        model: str,
        api_key: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> "GopherAgent":
        """
        Create a new GopherAgent with API key.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model name (e.g., "claude-3-haiku-20240307")
            api_key: API key for fetching remote server config
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        builder = (
            GopherAgentConfig.builder()
            .provider(provider)
            .model(model)
            .api_key(api_key)
        )
        if runtime_options is not None:
            builder.runtime_options(runtime_options)
        return GopherAgent.create(builder.build())

    @staticmethod
    def create_with_server_config(
        provider: str,
        model: str,
        server_config: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> "GopherAgent":
        """
        Create a new GopherAgent with JSON server config.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model name (e.g., "claude-3-haiku-20240307")
            server_config: JSON server configuration
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        builder = (
            GopherAgentConfig.builder()
            .provider(provider)
            .model(model)
            .server_config(server_config)
        )
        if runtime_options is not None:
            builder.runtime_options(runtime_options)
        return GopherAgent.create(builder.build())

    @staticmethod
    def create_with_server_id(
        provider: str,
        model: str,
        api_key: str,
        server_id: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> "GopherAgent":
        """
        Create a new GopherAgent scoped to a single MCP server by id.

        Fetches server config from the Gopher API using the Bearer api key,
        appending "?serverId={server_id}" so the response carries only the
        matching MCP server entry.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            api_key: Gopher API key
            server_id: MCP server id to scope the agent to
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        normalized_runtime_options = normalize_runtime_options(runtime_options)
        return GopherAgent._create_from_ffi(
            lambda lib: lib.agent_create_by_server_id(
                provider, model, api_key, server_id, normalized_runtime_options
            )
        )

    @staticmethod
    def create_with_server_name(
        provider: str,
        model: str,
        api_key: str,
        server_name: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> "GopherAgent":
        """
        Create a new GopherAgent scoped to a single MCP server by name.

        Fetches server config from the Gopher API using the Bearer api key,
        appending "?serverName={server_name}" so the response carries only
        the matching MCP server entry.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            api_key: Gopher API key
            server_name: MCP server name to scope the agent to
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        normalized_runtime_options = normalize_runtime_options(runtime_options)
        return GopherAgent._create_from_ffi(
            lambda lib: lib.agent_create_by_server_name(
                provider, model, api_key, server_name, normalized_runtime_options
            )
        )

    @staticmethod
    def create_with_gateway_id(
        provider: str,
        model: str,
        api_key: str,
        gateway_id: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> "GopherAgent":
        """
        Create a new GopherAgent scoped to a single MCP gateway by id.

        Fetches server config from the Gopher API using the Bearer api key,
        appending "?gatewayId={gateway_id}" so the response carries the
        backing MCP servers for that gateway.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            api_key: Gopher API key
            gateway_id: MCP gateway id to scope the agent to
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        normalized_runtime_options = normalize_runtime_options(runtime_options)
        return GopherAgent._create_from_ffi(
            lambda lib: lib.agent_create_by_gateway_id(
                provider, model, api_key, gateway_id, normalized_runtime_options
            )
        )

    @staticmethod
    def create_with_gateway_name(
        provider: str,
        model: str,
        api_key: str,
        gateway_name: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> "GopherAgent":
        """
        Create a new GopherAgent scoped to a single MCP gateway by name.

        Fetches server config from the Gopher API using the Bearer api key,
        appending "?gatewayName={gateway_name}" so the response carries the
        backing MCP servers for that gateway.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            api_key: Gopher API key
            gateway_name: MCP gateway name to scope the agent to
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        normalized_runtime_options = normalize_runtime_options(runtime_options)
        return GopherAgent._create_from_ffi(
            lambda lib: lib.agent_create_by_gateway_name(
                provider, model, api_key, gateway_name, normalized_runtime_options
            )
        )

    @staticmethod
    def create_with_url(
        provider: str,
        model: str,
        url: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> "GopherAgent":
        """
        Create a new GopherAgent for a single MCP server reachable at a URL.

        Skips the remote config fetch entirely: synthesises an http_sse
        server entry around the URL and delegates to create_by_json on the
        native side. Useful for local development or one-off endpoints where
        the operator already knows the URL.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            url: Full URL of the MCP server (e.g., "http://127.0.0.1:8080/mcp")
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        normalized_runtime_options = normalize_runtime_options(runtime_options)
        return GopherAgent._create_from_ffi(
            lambda lib: lib.agent_create_by_url(
                provider, model, url, normalized_runtime_options
            )
        )

    @staticmethod
    def _create_from_ffi(
        create_handle: Callable[[GopherOrchLibrary], Optional[GopherOrchHandle]],
    ) -> "GopherAgent":
        """
        Shared handle-creation pump for factories that bypass GopherAgentConfig.

        Ensures the native library is initialised, invokes the supplied FFI
        callable, and translates a null handle return into AgentError using
        the same last_error / clear_error contract as create().
        """
        if not _initialized:
            GopherAgent.init()

        lib = GopherOrchLibrary.get_instance()
        if lib is None:
            raise AgentError("Native library not available")

        try:
            handle = create_handle(lib)
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(f"Failed to create agent: {e}")

        if handle is None:
            error = lib.get_last_error_message()
            lib.clear_error()
            raise AgentError(error or _build_create_error_message())

        return GopherAgent(handle)

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


def _build_create_error_message() -> str:
    """
    Build the AgentError message for a null native create*() result.

    Native should usually populate gopher_orch_last_error, but a few
    defensive paths can still return null without details. Keep that
    fallback actionable instead of raising only "Failed to create agent".
    """
    return (
        "Failed to create agent: native library returned null without a "
        "specific error. Most often this means every configured MCP server "
        "failed to connect or returned no tools (TLS / network / bad URL), "
        "or the LLM provider could not be initialized. Set GOPHER_DEBUG=1 to "
        "see native-side logs."
    )
