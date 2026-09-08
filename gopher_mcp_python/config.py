"""
Configuration classes for the Gopher Security MCP SDK.

Provides a builder pattern for creating agent configurations with validation.
"""

from typing import Mapping, Optional

from gopher_mcp_python.runtime_options import (
    GopherAgentCreateOptions,
    GopherAgentOAuthOptions,
    GopherAgentRuntimeOptions,
    GopherAgentTokenRecord,
    GopherAgentTokenStore,
    RuntimeOptionsInput,
    normalize_create_options,
    normalize_runtime_options,
)


class GopherAgentConfig:
    """
    Immutable configuration for GopherAgent created via GopherAgent.create().

    Use the builder() method to create configurations.

    The builder accepts only the api_key / server_config XOR that maps to
    the original gopher_orch_agent_create_by_api_key and
    gopher_orch_agent_create_by_json C entry points. The five newer routing
    factories (GopherAgent.create_with_server_id, create_with_server_name,
    create_with_gateway_id, create_with_gateway_name, create_with_url) take
    additional inputs (server / gateway identifier, or URL) that do not fit
    that XOR shape and deliberately bypass this builder; they are exposed
    as static methods on GopherAgent and dispatch into GopherOrchLibrary
    directly via GopherAgent._create_from_ffi.

    Example:
        >>> config = (GopherAgentConfig.builder()
        ...     .provider("AnthropicProvider")
        ...     .model("claude-3-haiku-20240307")
        ...     .api_key("your-api-key")
        ...     .build())
    """

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        server_config: Optional[str] = None,
        runtime_options: RuntimeOptionsInput = None,
    ) -> None:
        """
        Initialize a GopherAgentConfig.

        Args:
            provider: The LLM provider name (e.g., "AnthropicProvider")
            model: The model name (e.g., "claude-3-haiku-20240307")
            api_key: API key for fetching remote server config
            server_config: JSON server configuration string
            runtime_options: Dynamic MCP runtime headers/access token
        """
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._server_config = server_config
        self._runtime_options = normalize_create_options(runtime_options)

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return self._provider

    @property
    def model(self) -> str:
        """Get the model name."""
        return self._model

    @property
    def api_key(self) -> Optional[str]:
        """Get the API key."""
        return self._api_key

    @property
    def server_config(self) -> Optional[str]:
        """Get the server configuration JSON."""
        return self._server_config

    @property
    def runtime_options(self) -> Optional[GopherAgentCreateOptions]:
        """Get dynamic MCP runtime and SDK OAuth options."""
        return self._runtime_options

    def has_api_key(self) -> bool:
        """Check if configuration uses API key."""
        return self._api_key is not None

    def has_server_config(self) -> bool:
        """Check if configuration uses server config."""
        return self._server_config is not None

    @staticmethod
    def builder() -> "GopherAgentConfigBuilder":
        """Create a new configuration builder."""
        return GopherAgentConfigBuilder()


class GopherAgentConfigBuilder:
    """
    Builder for GopherAgentConfig.

    Provides a fluent interface for building configurations with validation.
    """

    def __init__(self) -> None:
        self._provider: Optional[str] = None
        self._model: Optional[str] = None
        self._api_key: Optional[str] = None
        self._server_config: Optional[str] = None
        self._runtime_options: Optional[GopherAgentCreateOptions] = None

    def provider(self, provider: str) -> "GopherAgentConfigBuilder":
        """
        Set the LLM provider.

        Args:
            provider: The provider name (e.g., "AnthropicProvider", "OpenAIProvider")

        Returns:
            self for chaining
        """
        self._provider = provider
        return self

    def model(self, model: str) -> "GopherAgentConfigBuilder":
        """
        Set the model name.

        Args:
            model: The model name (e.g., "claude-3-haiku-20240307")

        Returns:
            self for chaining
        """
        self._model = model
        return self

    def api_key(self, api_key: str) -> "GopherAgentConfigBuilder":
        """
        Set the API key for fetching remote server config.

        Mutually exclusive with server_config().

        Args:
            api_key: The API key

        Returns:
            self for chaining
        """
        self._api_key = api_key
        return self

    def server_config(self, server_config: str) -> "GopherAgentConfigBuilder":
        """
        Set the JSON server configuration.

        Mutually exclusive with api_key().

        Args:
            server_config: JSON string containing server configuration

        Returns:
            self for chaining
        """
        self._server_config = server_config
        return self

    def runtime_options(
        self, options: RuntimeOptionsInput
    ) -> "GopherAgentConfigBuilder":
        """
        Set dynamic MCP runtime options.

        Args:
            options: GopherAgentRuntimeOptions or mapping with access_token/headers

        Returns:
            self for chaining
        """
        self._runtime_options = normalize_create_options(options)
        return self

    def access_token(self, access_token: str) -> "GopherAgentConfigBuilder":
        """
        Set the MCP runtime bearer token.

        Args:
            access_token: Token sent as Authorization: Bearer <token>

        Returns:
            self for chaining
        """
        current_headers = (
            self._runtime_options.headers if self._runtime_options is not None else None
        )
        current_oauth = (
            self._runtime_options.oauth if self._runtime_options is not None else None
        )
        current_elicitation = (
            self._runtime_options.elicitation
            if self._runtime_options is not None
            else None
        )
        next_options = {
            "access_token": access_token,
            "headers": current_headers,
            "oauth": current_oauth,
        }
        if current_elicitation is not None:
            next_options["elicitation"] = current_elicitation
        self._runtime_options = normalize_create_options(next_options)
        return self

    def headers(self, headers: Mapping[str, str]) -> "GopherAgentConfigBuilder":
        """
        Set dynamic MCP runtime headers.

        Args:
            headers: Header name/value mapping

        Returns:
            self for chaining
        """
        current_token = (
            self._runtime_options.access_token
            if self._runtime_options is not None
            else None
        )
        current_oauth = (
            self._runtime_options.oauth if self._runtime_options is not None else None
        )
        current_elicitation = (
            self._runtime_options.elicitation
            if self._runtime_options is not None
            else None
        )
        next_options = {
            "access_token": current_token,
            "headers": headers,
            "oauth": current_oauth,
        }
        if current_elicitation is not None:
            next_options["elicitation"] = current_elicitation
        self._runtime_options = normalize_create_options(next_options)
        return self

    def build(self) -> GopherAgentConfig:
        """
        Build the configuration.

        Returns:
            GopherAgentConfig instance

        Raises:
            ValueError: If required fields are missing or configuration is invalid
        """
        if not self._provider:
            raise ValueError("Provider is required")
        if not self._model:
            raise ValueError("Model is required")
        if not self._api_key and not self._server_config:
            raise ValueError("Either api_key or server_config is required")
        if self._api_key and self._server_config:
            raise ValueError("Cannot specify both api_key and server_config")

        return GopherAgentConfig(
            provider=self._provider,
            model=self._model,
            api_key=self._api_key,
            server_config=self._server_config,
            runtime_options=self._runtime_options,
        )
