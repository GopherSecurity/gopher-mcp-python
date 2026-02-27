"""Tests for GopherAgentConfig."""

import pytest
from gopher_security_mcp.config import GopherAgentConfig


class TestGopherAgentConfig:
    """Tests for GopherAgentConfig builder pattern."""

    def test_should_create_config_with_api_key(self):
        """Test creating config with API key."""
        config = (
            GopherAgentConfig.builder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .api_key("test-api-key")
            .build()
        )

        assert config.provider == "AnthropicProvider"
        assert config.model == "claude-3-haiku-20240307"
        assert config.api_key == "test-api-key"
        assert config.server_config is None
        assert config.has_api_key() is True
        assert config.has_server_config() is False

    def test_should_create_config_with_server_config(self):
        """Test creating config with server config."""
        config = (
            GopherAgentConfig.builder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .server_config('{"servers": []}')
            .build()
        )

        assert config.provider == "AnthropicProvider"
        assert config.model == "claude-3-haiku-20240307"
        assert config.api_key is None
        assert config.server_config == '{"servers": []}'
        assert config.has_api_key() is False
        assert config.has_server_config() is True

    def test_should_require_provider(self):
        """Test that provider is required."""
        with pytest.raises(ValueError, match="Provider is required"):
            GopherAgentConfig.builder().model("claude-3-haiku-20240307").api_key(
                "test-key"
            ).build()

    def test_should_require_model(self):
        """Test that model is required."""
        with pytest.raises(ValueError, match="Model is required"):
            GopherAgentConfig.builder().provider("AnthropicProvider").api_key(
                "test-key"
            ).build()

    def test_should_require_either_api_key_or_server_config(self):
        """Test that either API key or server config is required."""
        with pytest.raises(
            ValueError, match="Either api_key or server_config is required"
        ):
            GopherAgentConfig.builder().provider("AnthropicProvider").model(
                "claude-3-haiku-20240307"
            ).build()

    def test_should_not_allow_both_api_key_and_server_config(self):
        """Test that both API key and server config cannot be specified."""
        with pytest.raises(
            ValueError, match="Cannot specify both api_key and server_config"
        ):
            (
                GopherAgentConfig.builder()
                .provider("AnthropicProvider")
                .model("claude-3-haiku-20240307")
                .api_key("test-key")
                .server_config('{"servers": []}')
                .build()
            )
