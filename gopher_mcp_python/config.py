"""
Configuration classes for the Gopher Security MCP SDK.

Provides a builder pattern for creating agent configurations with validation.
"""

from typing import Optional


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
    ) -> None:
        """
        Initialize a GopherAgentConfig.

        Args:
            provider: The LLM provider name (e.g., "AnthropicProvider")
            model: The model name (e.g., "claude-3-haiku-20240307")
            api_key: API key for fetching remote server config
            server_config: JSON server configuration string
        """
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._server_config = server_config

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
        )
