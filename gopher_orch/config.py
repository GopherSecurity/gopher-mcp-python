"""Configuration classes for GopherAgent."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GopherAgentConfig:
    """Configuration options for creating a GopherAgent.

    Args:
        provider: LLM provider name (e.g., "AnthropicProvider")
        model: Model name (e.g., "claude-3-haiku-20240307")
        api_key: API key for fetching remote server config (mutually exclusive with server_config)
        server_config: JSON server configuration (mutually exclusive with api_key)

    Example:
        >>> config = GopherAgentConfig(
        ...     provider="AnthropicProvider",
        ...     model="claude-3-haiku-20240307",
        ...     api_key="your-api-key"
        ... )

        Or with server config:

        >>> config = GopherAgentConfig(
        ...     provider="AnthropicProvider",
        ...     model="claude-3-haiku-20240307",
        ...     server_config='{"servers": [...]}'
        ... )
    """

    provider: str
    model: str
    api_key: Optional[str] = None
    server_config: Optional[str] = None

    def __post_init__(self):
        if not self.provider:
            raise ValueError("Provider is required")
        if not self.model:
            raise ValueError("Model is required")
        if self.api_key is None and self.server_config is None:
            raise ValueError("Either api_key or server_config is required")
        if self.api_key is not None and self.server_config is not None:
            raise ValueError("Cannot specify both api_key and server_config")

    @property
    def has_api_key(self) -> bool:
        """Check if API key is set."""
        return self.api_key is not None

    @property
    def has_server_config(self) -> bool:
        """Check if server config is set."""
        return self.server_config is not None


class GopherAgentConfigBuilder:
    """Builder pattern for GopherAgentConfig.

    Example:
        >>> config = (GopherAgentConfigBuilder()
        ...     .provider("AnthropicProvider")
        ...     .model("claude-3-haiku-20240307")
        ...     .api_key("your-api-key")
        ...     .build())
    """

    def __init__(self):
        self._provider: Optional[str] = None
        self._model: Optional[str] = None
        self._api_key: Optional[str] = None
        self._server_config: Optional[str] = None

    def provider(self, provider: str) -> "GopherAgentConfigBuilder":
        """Set the LLM provider."""
        self._provider = provider
        return self

    def model(self, model: str) -> "GopherAgentConfigBuilder":
        """Set the model name."""
        self._model = model
        return self

    def api_key(self, api_key: str) -> "GopherAgentConfigBuilder":
        """Set the API key for fetching remote server config."""
        self._api_key = api_key
        return self

    def server_config(self, server_config: str) -> "GopherAgentConfigBuilder":
        """Set the JSON server configuration."""
        self._server_config = server_config
        return self

    def build(self) -> GopherAgentConfig:
        """Build the configuration."""
        if not self._provider:
            raise ValueError("Provider is required")
        if not self._model:
            raise ValueError("Model is required")
        return GopherAgentConfig(
            provider=self._provider,
            model=self._model,
            api_key=self._api_key,
            server_config=self._server_config,
        )
