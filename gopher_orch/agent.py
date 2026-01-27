"""
GopherAgent - Main entry point for the gopher-orch Python SDK.

Provides a clean, Pythonic interface to the gopher-orch agent functionality.
"""

import atexit
import threading

from gopher_orch.config import GopherAgentConfig
from gopher_orch.errors import AgentException, TimeoutException
from gopher_orch.ffi.library import GopherOrchHandle, GopherOrchLibrary
from gopher_orch.result import AgentResult, AgentResultStatus


class GopherAgent:
    """
    GopherAgent - Main entry point for the gopher-orch Python SDK.

    Provides a clean, Pythonic interface to the gopher-orch agent functionality.

    Example:
        # Create an agent with API key
        config = GopherAgentConfig(
            provider="AnthropicProvider",
            model="claude-3-haiku-20240307",
            api_key="your-api-key"
        )
        agent = GopherAgent.create(config)

        # Run a query
        answer = agent.run("What time is it in Tokyo?")
        print(answer)

        # Cleanup (optional - happens automatically with context manager)
        agent.dispose()

    Or use context manager for automatic cleanup:

        with GopherAgent.create(config) as agent:
            answer = agent.run("What time is it in Tokyo?")
            print(answer)
    """

    _initialized = False
    _init_lock = threading.Lock()
    _cleanup_registered = False

    def __init__(self, handle: GopherOrchHandle):
        """Initialize GopherAgent with a native handle.

        Note: Use GopherAgent.create() instead of direct instantiation.
        """
        self._handle = handle
        self._disposed = False
        self._lock = threading.Lock()

    @classmethod
    def init(cls) -> None:
        """Initialize the gopher-orch library.

        Must be called before creating any agents.
        Called automatically by create() if not already initialized.

        Raises:
            AgentException: If initialization fails
        """
        with cls._init_lock:
            if cls._initialized:
                return

            lib = GopherOrchLibrary.get_instance()
            if lib is None or not lib.is_available():
                raise AgentException("Failed to load gopher-orch native library")

            cls._initialized = True
            cls._setup_cleanup_handler()

    @classmethod
    def shutdown(cls) -> None:
        """Shutdown the gopher-orch library.

        Called automatically on process exit, but can be called manually.
        """
        with cls._init_lock:
            cls._initialized = False

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the library is initialized."""
        return cls._initialized

    @classmethod
    def create(cls, config: GopherAgentConfig) -> "GopherAgent":
        """Create a new GopherAgent instance.

        Args:
            config: Agent configuration

        Returns:
            GopherAgent instance

        Raises:
            AgentException: If agent creation fails
        """
        if not cls._initialized:
            cls.init()

        lib = GopherOrchLibrary.get_instance()
        if lib is None:
            raise AgentException("Native library not available")

        try:
            if config.has_api_key:
                handle = lib.agent_create_by_api_key(
                    config.provider,
                    config.model,
                    config.api_key,
                )
            else:
                handle = lib.agent_create_by_json(
                    config.provider,
                    config.model,
                    config.server_config,
                )
        except Exception as e:
            raise AgentException(f"Failed to create agent: {e}") from e

        if handle is None:
            error = lib.get_last_error_message()
            lib.clear_error()
            raise AgentException(error or "Failed to create agent")

        return cls(handle)

    @classmethod
    def create_with_api_key(
        cls, provider: str, model: str, api_key: str
    ) -> "GopherAgent":
        """Create a new GopherAgent with API key.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model name (e.g., "claude-3-haiku-20240307")
            api_key: API key for fetching remote server config

        Returns:
            GopherAgent instance
        """
        config = GopherAgentConfig(provider=provider, model=model, api_key=api_key)
        return cls.create(config)

    @classmethod
    def create_with_server_config(
        cls, provider: str, model: str, server_config: str
    ) -> "GopherAgent":
        """Create a new GopherAgent with JSON server config.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model name (e.g., "claude-3-haiku-20240307")
            server_config: JSON server configuration

        Returns:
            GopherAgent instance
        """
        config = GopherAgentConfig(
            provider=provider, model=model, server_config=server_config
        )
        return cls.create(config)

    def run(self, query: str, timeout_ms: int = 60000) -> str:
        """Run a query against the agent.

        Args:
            query: The user query to process
            timeout_ms: Timeout in milliseconds (default: 60000)

        Returns:
            The agent's response

        Raises:
            AgentException: If the query fails or agent is disposed
        """
        self._ensure_not_disposed()

        lib = GopherOrchLibrary.get_instance()
        if lib is None:
            raise AgentException("Native library not available")

        try:
            response = lib.agent_run(self._handle, query, timeout_ms)
            if response is None:
                return f'No response for query: "{query}"'
            return response
        except Exception as e:
            raise AgentException(f"Query execution failed: {e}") from e

    def run_detailed(self, query: str, timeout_ms: int = 60000) -> AgentResult:
        """Run a query with detailed result information.

        Args:
            query: The user query to process
            timeout_ms: Timeout in milliseconds (default: 60000)

        Returns:
            AgentResult with response and metadata
        """
        try:
            response = self.run(query, timeout_ms)
            return AgentResult(
                response=response,
                status=AgentResultStatus.SUCCESS,
                iteration_count=1,
                tokens_used=0,
            )
        except TimeoutException as e:
            return AgentResult.timeout(str(e))
        except Exception as e:
            return AgentResult.error(str(e))

    def dispose(self) -> None:
        """Dispose of the agent and free resources."""
        with self._lock:
            if self._disposed:
                return
            self._disposed = True

            lib = GopherOrchLibrary.get_instance()
            if lib is not None and self._handle is not None:
                lib.agent_release(self._handle)
                self._handle = None

    @property
    def is_disposed(self) -> bool:
        """Check if agent is disposed."""
        return self._disposed

    def _ensure_not_disposed(self) -> None:
        """Ensure the agent is not disposed."""
        if self._disposed:
            raise AgentException("Agent has been disposed")

    @classmethod
    def _setup_cleanup_handler(cls) -> None:
        """Set up cleanup handler for process exit."""
        if not cls._cleanup_registered:
            atexit.register(cls.shutdown)
            cls._cleanup_registered = True

    def __enter__(self) -> "GopherAgent":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - calls dispose()."""
        self.dispose()

    def __del__(self) -> None:
        """Destructor - calls dispose()."""
        try:
            self.dispose()
        except Exception:
            pass
