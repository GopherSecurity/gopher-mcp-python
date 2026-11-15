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
import asyncio
import concurrent.futures
import copy
import threading
import weakref
from .source_selection import assert_no_source_selection
from typing import Callable, Optional

from gopher_mcp_python.gateway_elicitation_preflight import (
    preflight_gateway_elicitation_with_status,
)
import gopher_mcp_python.oauth_resolver as oauth_resolver
from gopher_mcp_python.config import GopherAgentConfig
from gopher_mcp_python.runtime_options import (
    GopherAgentCreateOptions,
    GopherAgentOAuthOptions,
    GopherAgentRuntimeOptions,
    RuntimeOptionsInput,
    normalize_create_options,
    normalize_runtime_options,
)
from gopher_mcp_python.result import AgentResult, AgentResultStatus
from gopher_mcp_python.server_config import ServerConfig, ServerConfigRoute
from gopher_mcp_python.errors import AgentError, TimeoutError
from gopher_mcp_python.ffi import GopherOrchLibrary, GopherOrchHandle
from gopher_mcp_python.embedded_auth import EmbeddedAgentSession

_initialized = False
_cleanup_handler_registered = False
_initialization_lock = threading.RLock()
_creation_context = threading.local()
_SKIP_DISCOVERY_ELICITATION_HEADER = "X-Gopher-Internal-Skip-Discovery-Elicitation"
_PREFLIGHT_MCP_SESSION_HEADER = "X-Gopher-Internal-Preflight-Mcp-Session-Id"


class GopherAgent:
    """
    Main agent class for interacting with the gopher-mcp-python native library.
    """

    def __init__(
        self,
        handle: GopherOrchHandle,
        library: Optional[GopherOrchLibrary] = None,
        authorization_session=None,
    ) -> None:
        """
        Initialize a GopherAgent with a native handle.

        Note: Use create() factory method instead of direct instantiation.
        """
        self._handle = handle
        self._library = (
            library if library is not None else GopherOrchLibrary.get_instance()
        )
        self._lifecycle_lock = threading.Lock()
        self._running = False
        self._disposed = False
        self._authorization_session = authorization_session
        self._released = threading.Event()
        self._finalizer = weakref.finalize(
            self,
            _release_handle_best_effort,
            handle,
            self._library,
            authorization_session,
            self._released,
        )

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
        with _initialization_lock:
            if _initialized:
                return
            lib = GopherOrchLibrary.get_instance()
            if lib is None:
                load_error = GopherOrchLibrary.get_load_error_message()
                raise AgentError(
                    f"Failed to load gopher-mcp-python native library.\n{load_error}"
                )
            _setup_cleanup_handler()
            _initialized = True

    @staticmethod
    def shutdown() -> None:
        """
        Reset SDK initialization bookkeeping without disposing existing agents.

        The native library remains loaded. Called automatically on process exit,
        but can be called manually; callers still own their live agents.
        """
        global _initialized
        with _initialization_lock:
            _initialized = False

    @staticmethod
    def is_initialized() -> bool:
        """Check if the library is initialized."""
        with _initialization_lock:
            return _initialized

    @staticmethod
    def create(config: GopherAgentConfig) -> "GopherAgent":
        """
        Create a new GopherAgent instance, resolving SDK OAuth credentials if needed.

        Args:
            config: Agent configuration

        Returns:
            GopherAgent instance

        Raises:
            AgentError: if agent creation fails
        """
        if config.has_api_key():
            return GopherAgent.create_with_api_key(
                config.provider,
                config.model,
                config.api_key,
                config.runtime_options,
            )
        return GopherAgent.create_with_server_config(
            config.provider,
            config.model,
            config.server_config,
            config.runtime_options,
        )

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
        create_options = _normalize_create_options_for_agent(runtime_options)
        runtime_options = normalize_runtime_options(create_options)
        oauth = create_options.oauth if create_options is not None else None

        return _create_from_api_config(
            provider,
            model,
            api_key,
            route=None,
            runtime_options=runtime_options,
            oauth=oauth,
            selection=create_options.source_selection,
        )

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
        create_options = _normalize_create_options_for_agent(runtime_options)
        assert_no_source_selection(create_options)
        runtime_options = normalize_runtime_options(create_options)
        oauth = create_options.oauth if create_options is not None else None
        if _should_skip_oauth(runtime_options, oauth):
            return GopherAgent._create_from_ffi(
                lambda lib: lib.agent_create_by_json(
                    provider, model, server_config, runtime_options
                )
            )

        resolved_runtime_options = _run_oauth_coroutine(
            lambda: oauth_resolver.resolve_runtime_options_with_oauth(
                urls=[],
                server_config=server_config,
                runtime_options=runtime_options,
                oauth=oauth,
            )
        )
        return GopherAgent._create_from_ffi(
            lambda lib: lib.agent_create_by_json(
                provider, model, server_config, resolved_runtime_options
            )
        )

    @staticmethod
    def create_with_server_id(
        provider: str,
        model: str,
        api_key: str,
        server_id: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> "GopherAgent":
        """
        Create an agent selecting an MCP server ID plus optional selectors.

        POST the server ID and any additional runtime_options selectors to
        /v1/mcp-servers once. The backend response defines the final sources.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            api_key: Gopher API key
            server_id: MCP server id to scope the agent to
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        create_options = _normalize_create_options_for_agent(runtime_options)
        normalized_runtime_options = normalize_runtime_options(create_options)
        oauth = create_options.oauth if create_options is not None else None
        return _create_from_api_config(
            provider,
            model,
            api_key,
            route=ServerConfigRoute("serverId", server_id),
            runtime_options=normalized_runtime_options,
            oauth=oauth,
            selection=create_options.source_selection,
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
        Create an agent selecting an MCP server name plus optional selectors.

        POST the server name and any additional runtime_options selectors to
        /v1/mcp-servers once. The backend response defines the final sources.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            api_key: Gopher API key
            server_name: MCP server name to scope the agent to
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        create_options = _normalize_create_options_for_agent(runtime_options)
        normalized_runtime_options = normalize_runtime_options(create_options)
        oauth = create_options.oauth if create_options is not None else None
        return _create_from_api_config(
            provider,
            model,
            api_key,
            route=ServerConfigRoute("serverName", server_name),
            runtime_options=normalized_runtime_options,
            oauth=oauth,
            selection=create_options.source_selection,
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
        Create an agent selecting a remote gateway ID plus optional selectors.

        POST the gateway ID and any additional runtime_options selectors to
        /v1/mcp-servers once. Gateways remain remote MCP endpoints; their
        backing servers are not expanded locally.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            api_key: Gopher API key
            gateway_id: MCP gateway id to scope the agent to
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        create_options = _normalize_create_options_for_agent(runtime_options)
        normalized_runtime_options = normalize_runtime_options(create_options)
        oauth = create_options.oauth if create_options is not None else None
        return _create_from_api_config(
            provider,
            model,
            api_key,
            route=ServerConfigRoute("gatewayId", gateway_id),
            runtime_options=normalized_runtime_options,
            oauth=oauth,
            selection=create_options.source_selection,
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
        Create an agent selecting a remote gateway name plus optional selectors.

        POST the gateway name and any additional runtime_options selectors to
        /v1/mcp-servers once. Gateways remain remote MCP endpoints; their
        backing servers are not expanded locally.

        Args:
            provider: Provider name (e.g., "AnthropicProvider")
            model: Model identifier accepted by the chosen provider
            api_key: Gopher API key
            gateway_name: MCP gateway name to scope the agent to
            runtime_options: Dynamic MCP runtime headers/access token

        Returns:
            GopherAgent instance
        """
        create_options = _normalize_create_options_for_agent(runtime_options)
        normalized_runtime_options = normalize_runtime_options(create_options)
        oauth = create_options.oauth if create_options is not None else None
        return _create_from_api_config(
            provider,
            model,
            api_key,
            route=ServerConfigRoute("gatewayName", gateway_name),
            runtime_options=normalized_runtime_options,
            oauth=oauth,
            selection=create_options.source_selection,
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
        create_options = _normalize_create_options_for_agent(runtime_options)
        assert_no_source_selection(create_options)
        normalized_runtime_options = normalize_runtime_options(create_options)
        oauth = create_options.oauth if create_options is not None else None
        if url != "" and not _should_skip_oauth(normalized_runtime_options, oauth):
            normalized_runtime_options = _run_oauth_coroutine(
                lambda: oauth_resolver.resolve_url_runtime_options_with_oauth(
                    url,
                    runtime_options=normalized_runtime_options,
                    oauth=oauth,
                )
            )
        preflight = preflight_gateway_elicitation_with_status(
            url,
            normalized_runtime_options,
            create_options,
        )
        normalized_runtime_options = _mark_discovery_elicitation_preflighted(
            preflight.runtime_options,
            preflight.handled,
            preflight.session,
        )
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
        GopherAgent.init()

        lib = GopherOrchLibrary.get_instance()
        if lib is None:
            load_error = GopherOrchLibrary.get_load_error_message()
            raise AgentError(f"Native library not available.\n{load_error}")

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

        return GopherAgent(handle, lib)

    @staticmethod
    async def create_async(config: GopherAgentConfig) -> "GopherAgent":
        """Create off the event loop, retaining that loop for async OAuth stores."""
        return await _create_agent_async(GopherAgent.create, config)

    @staticmethod
    async def create_with_api_key_async(provider, model, api_key, runtime_options=None):
        return await _create_agent_async(
            GopherAgent.create_with_api_key, provider, model, api_key, runtime_options
        )

    @staticmethod
    async def create_with_server_id_async(
        provider, model, api_key, server_id, runtime_options=None
    ):
        return await _create_agent_async(
            GopherAgent.create_with_server_id,
            provider,
            model,
            api_key,
            server_id,
            runtime_options,
        )

    @staticmethod
    async def create_with_server_name_async(
        provider, model, api_key, server_name, runtime_options=None
    ):
        return await _create_agent_async(
            GopherAgent.create_with_server_name,
            provider,
            model,
            api_key,
            server_name,
            runtime_options,
        )

    @staticmethod
    async def create_with_gateway_id_async(
        provider, model, api_key, gateway_id, runtime_options=None
    ):
        return await _create_agent_async(
            GopherAgent.create_with_gateway_id,
            provider,
            model,
            api_key,
            gateway_id,
            runtime_options,
        )

    @staticmethod
    async def create_with_gateway_name_async(
        provider, model, api_key, gateway_name, runtime_options=None
    ):
        return await _create_agent_async(
            GopherAgent.create_with_gateway_name,
            provider,
            model,
            api_key,
            gateway_name,
            runtime_options,
        )

    @staticmethod
    async def create_with_url_async(provider, model, url, runtime_options=None):
        return await _create_agent_async(
            GopherAgent.create_with_url, provider, model, url, runtime_options
        )

    @staticmethod
    async def create_with_server_config_async(
        provider, model, server_config, runtime_options=None
    ):
        return await _create_agent_async(
            GopherAgent.create_with_server_config,
            provider,
            model,
            server_config,
            runtime_options,
        )

    async def run_async(self, query: str, timeout_ms: int = 60000) -> str:
        """Keep the event loop available for OAuth stores during a native query.

        Cancelling this await does not interrupt the native query. Its worker
        retains the agent and deferred disposal until native execution exits.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, query, timeout_ms)

    async def dispose_async(self) -> None:
        """Wait for native release and authorization-host shutdown off the loop."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.dispose)
        await loop.run_in_executor(None, self._released.wait)

    def run(self, query: str, timeout_ms: int = 60000) -> str:
        """
        Run a query against the agent.

        Only one query may be active on an agent; overlapping calls raise
        AgentError. Disposal during execution defers cleanup until this call
        exits and does not cancel the query.

        Args:
            query: The user query to process
            timeout_ms: Timeout in milliseconds (default: 60000)

        Returns:
            The agent's response

        Raises:
            AgentError: if the query fails
        """
        with self._lifecycle_lock:
            self._ensure_not_disposed()
            if self._running:
                raise AgentError("Agent is already running a query")
            self._running = True
        try:
            if self._authorization_session is not None:
                self._authorization_session.check()
                self._authorization_session.check_run_loop()
            lib = self._library
            if lib is None:
                load_error = GopherOrchLibrary.get_load_error_message()
                raise AgentError(f"Native library not available.\n{load_error}")
            response = lib.agent_run(self._handle, query, timeout_ms)
            if self._authorization_session is not None:
                self._authorization_session.check()
            if response is None:
                error = lib.get_last_error_message()
                lib.clear_error()
                raise AgentError(error or f'No response for query: "{query}"')
            return response
        except AgentError:
            raise
        except Exception as e:
            raise AgentError(f"Query execution failed: {e}")
        finally:
            with self._lifecycle_lock:
                self._running = False
                release = self._disposed
            if release:
                self._finalizer()

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
        """
        Dispose of the agent and free native resources deterministically.

        Stop accepting queries immediately. If a query is active, its exit
        releases native resources. Use dispose_async() from an event loop to
        wait for release without blocking that loop.
        A best-effort finalizer also releases forgotten agents.
        """
        with self._lifecycle_lock:
            if self._disposed:
                return
            self._disposed = True
            release = not self._running
        if release:
            self._finalizer()

    def is_disposed(self) -> bool:
        """Check if agent is disposed."""
        with self._lifecycle_lock:
            return self._disposed

    def _ensure_not_disposed(self) -> None:
        """Ensure agent has not been disposed."""
        if self._disposed:
            raise AgentError("Agent has been disposed")


def _setup_cleanup_handler() -> None:
    """Register cleanup handler for process exit."""
    global _cleanup_handler_registered
    with _initialization_lock:
        if _cleanup_handler_registered:
            return
        atexit.register(GopherAgent.shutdown)
        _cleanup_handler_registered = True


def _release_handle_best_effort(
    handle: GopherOrchHandle,
    lib: Optional[GopherOrchLibrary],
    authorization_session=None,
    released=None,
) -> None:
    try:
        if lib is not None and handle is not None:
            lib.agent_release(handle)
    except Exception:
        pass
    finally:
        try:
            if authorization_session is not None:
                authorization_session.close()
        finally:
            if released is not None:
                released.set()


def _create_from_api_config(
    provider: str,
    model: str,
    api_key: str,
    route: Optional[ServerConfigRoute],
    runtime_options: Optional[GopherAgentRuntimeOptions],
    oauth: Optional[GopherAgentOAuthOptions],
    selection=None,
) -> GopherAgent:
    server_config = ServerConfig.fetch(api_key, route=route, selection=selection)
    try:
        resolved_runtime_options = (
            runtime_options
            if _should_skip_oauth(runtime_options, oauth)
            else _run_oauth_coroutine(
                lambda: oauth_resolver.resolve_runtime_options_with_oauth(
                    urls=[],
                    server_config=server_config,
                    runtime_options=runtime_options,
                    oauth=oauth,
                    defer_multiple_oauth=True,
                )
            )
        )
    except oauth_resolver.MultipleMcpOAuthRequired:
        GopherAgent.init()
        lib = GopherOrchLibrary.get_instance()
        embedded_oauth = copy.copy(oauth or GopherAgentOAuthOptions())
        embedded_oauth.assemble = dict(embedded_oauth.assemble or {})
        cancellation = getattr(_creation_context, "cancellation", None)
        if cancellation is not None:
            embedded_oauth.assemble["cancel_event"] = _CombinedCancellation(
                cancellation, embedded_oauth.assemble.get("cancel_event")
            )
        options = GopherAgentCreateOptions(
            access_token=runtime_options.access_token if runtime_options else None,
            headers=runtime_options.headers if runtime_options else None,
            elicitation=runtime_options.elicitation if runtime_options else None,
            server_options=runtime_options.server_options if runtime_options else None,
            oauth=embedded_oauth,
        )
        session = EmbeddedAgentSession(
            lib,
            server_config,
            provider,
            model,
            options,
            callback_loop=getattr(_creation_context, "callback_loop", None),
        )
        try:
            handle = session.wait_ready()
        except BaseException:
            session.close()
            raise
        try:
            return GopherAgent(handle, lib, session)
        except BaseException:
            _release_handle_best_effort(handle, lib, session)
            raise
    return GopherAgent._create_from_ffi(
        lambda lib: lib.agent_create_by_json(
            provider, model, server_config, resolved_runtime_options
        )
    )


def _run_oauth_coroutine(create_coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:

        async def run():
            task = asyncio.create_task(create_coroutine())
            cancellation = getattr(_creation_context, "cancellation", None)
            try:
                while not task.done():
                    if cancellation is not None and cancellation.is_set():
                        raise AgentError("AUTH_CANCELLED: agent creation cancelled")
                    await asyncio.wait({task}, timeout=0.05)
                return task.result()
            finally:
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

        return asyncio.run(run())
    raise AgentError(
        "SDK OAuth auto-flow cannot run inside an active asyncio event loop. "
        "Provide runtime_options with access_token/Authorization, or set "
        'oauth.mode to "disabled".'
    )


class _CombinedCancellation:
    def __init__(self, *events):
        self.events = events

    def is_set(self):
        return any(event is not None and event.is_set() for event in self.events)


async def _create_agent_async(factory, *args):
    loop = asyncio.get_running_loop()
    cancellation = threading.Event()
    result = concurrent.futures.Future()

    def create():
        _creation_context.callback_loop = loop
        _creation_context.cancellation = cancellation
        try:
            if cancellation.is_set():
                raise AgentError("AUTH_CANCELLED: agent creation cancelled")
            agent = factory(*args)
            if cancellation.is_set():
                agent.dispose()
                raise AgentError("AUTH_CANCELLED: agent creation cancelled")
            result.set_result(agent)
        except BaseException as exc:
            result.set_exception(exc)
        finally:
            del _creation_context.callback_loop
            del _creation_context.cancellation

    threading.Thread(target=create, daemon=True, name="gopher-mcp-create").start()
    waiting = asyncio.wrap_future(result)
    try:
        return await asyncio.shield(waiting)
    except asyncio.CancelledError:
        cancellation.set()

        def discard(done):
            try:
                agent = done.result()
            except BaseException:
                return
            threading.Thread(
                target=agent.dispose, daemon=True, name="gopher-mcp-cancel-create"
            ).start()

        result.add_done_callback(discard)
        # Consume the shielded result even if its originating loop is closing.
        waiting.add_done_callback(
            lambda done: done.exception() if not done.cancelled() else None
        )
        raise


def _normalize_create_options_for_agent(
    runtime_options: RuntimeOptionsInput,
) -> GopherAgentCreateOptions:
    create_options = normalize_create_options(runtime_options)
    return create_options if create_options is not None else GopherAgentCreateOptions()


def _should_skip_oauth(
    runtime_options: Optional[GopherAgentRuntimeOptions],
    oauth: Optional[GopherAgentOAuthOptions],
) -> bool:
    if oauth is not None and oauth.mode == "disabled":
        return True
    if runtime_options is None:
        return False
    if runtime_options.access_token is not None:
        return True
    return any(name.lower() == "authorization" for name in runtime_options.headers)


def _mark_discovery_elicitation_preflighted(
    runtime_options: Optional[GopherAgentRuntimeOptions],
    handled: bool,
    session: Optional[str],
) -> Optional[GopherAgentRuntimeOptions]:
    if not handled:
        return runtime_options
    headers = dict(runtime_options.headers) if runtime_options is not None else {}
    headers[_SKIP_DISCOVERY_ELICITATION_HEADER] = "1"
    if session:
        headers[_PREFLIGHT_MCP_SESSION_HEADER] = session
    return GopherAgentRuntimeOptions(
        access_token=runtime_options.access_token if runtime_options else None,
        headers=headers,
        elicitation=runtime_options.elicitation if runtime_options else None,
        server_options=runtime_options.server_options if runtime_options else None,
    )


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
        "or the LLM provider could not be initialized. Set DEBUG=1 to see "
        "Python-side native library load diagnostics and native-side logs."
    )
