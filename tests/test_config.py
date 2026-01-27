"""Tests for GopherAgentConfig."""

import pytest

from gopher_orch.config import GopherAgentConfig, GopherAgentConfigBuilder


class TestGopherAgentConfig:
    """Tests for GopherAgentConfig dataclass."""

    def test_create_with_api_key(self):
        """Test creating config with API key."""
        config = GopherAgentConfig(
            provider="AnthropicProvider",
            model="claude-3-haiku-20240307",
            api_key="test-api-key",
        )
        assert config.provider == "AnthropicProvider"
        assert config.model == "claude-3-haiku-20240307"
        assert config.api_key == "test-api-key"
        assert config.server_config is None
        assert config.has_api_key is True
        assert config.has_server_config is False

    def test_create_with_server_config(self):
        """Test creating config with server config."""
        config = GopherAgentConfig(
            provider="AnthropicProvider",
            model="claude-3-haiku-20240307",
            server_config='{"servers": []}',
        )
        assert config.provider == "AnthropicProvider"
        assert config.model == "claude-3-haiku-20240307"
        assert config.api_key is None
        assert config.server_config == '{"servers": []}'
        assert config.has_api_key is False
        assert config.has_server_config is True

    def test_provider_required(self):
        """Test that provider is required."""
        with pytest.raises(ValueError, match="Provider is required"):
            GopherAgentConfig(
                provider="",
                model="claude-3-haiku-20240307",
                api_key="test-key",
            )

    def test_model_required(self):
        """Test that model is required."""
        with pytest.raises(ValueError, match="Model is required"):
            GopherAgentConfig(
                provider="AnthropicProvider",
                model="",
                api_key="test-key",
            )

    def test_either_api_key_or_server_config_required(self):
        """Test that either api_key or server_config is required."""
        with pytest.raises(ValueError, match="Either api_key or server_config"):
            GopherAgentConfig(
                provider="AnthropicProvider",
                model="claude-3-haiku-20240307",
            )

    def test_cannot_have_both_api_key_and_server_config(self):
        """Test that both api_key and server_config cannot be specified."""
        with pytest.raises(ValueError, match="Cannot specify both"):
            GopherAgentConfig(
                provider="AnthropicProvider",
                model="claude-3-haiku-20240307",
                api_key="test-key",
                server_config='{"servers": []}',
            )


class TestGopherAgentConfigBuilder:
    """Tests for GopherAgentConfigBuilder."""

    def test_builder_with_api_key(self):
        """Test builder pattern with API key."""
        config = (
            GopherAgentConfigBuilder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .api_key("test-api-key")
            .build()
        )
        assert config.provider == "AnthropicProvider"
        assert config.model == "claude-3-haiku-20240307"
        assert config.api_key == "test-api-key"

    def test_builder_with_server_config(self):
        """Test builder pattern with server config."""
        config = (
            GopherAgentConfigBuilder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .server_config('{"servers": []}')
            .build()
        )
        assert config.provider == "AnthropicProvider"
        assert config.model == "claude-3-haiku-20240307"
        assert config.server_config == '{"servers": []}'

    def test_builder_provider_required(self):
        """Test that builder requires provider."""
        with pytest.raises(ValueError, match="Provider is required"):
            GopherAgentConfigBuilder().model("test").api_key("key").build()

    def test_builder_model_required(self):
        """Test that builder requires model."""
        with pytest.raises(ValueError, match="Model is required"):
            GopherAgentConfigBuilder().provider("test").api_key("key").build()
