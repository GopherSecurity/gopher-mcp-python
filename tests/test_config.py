"""Tests for GopherAgentConfig."""

import pytest
from gopher_mcp_python.config import GopherAgentConfig, GopherAgentRuntimeOptions


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

    def test_should_normalize_empty_runtime_options_to_none(self):
        """Test empty runtime options are omitted."""
        config = (
            GopherAgentConfig.builder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .api_key("test-key")
            .runtime_options({})
            .build()
        )

        assert config.runtime_options is None

    def test_should_create_runtime_options_with_access_token(self):
        """Test access_token maps to Authorization bearer header."""
        config = (
            GopherAgentConfig.builder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .api_key("test-key")
            .access_token("abc123")
            .build()
        )

        assert config.runtime_options is not None
        assert config.runtime_options.access_token == "abc123"
        assert config.runtime_options.headers == {"Authorization": "Bearer abc123"}

    def test_should_create_runtime_options_with_headers(self):
        """Test dynamic headers are copied into runtime options."""
        headers = {"X-Test": "one"}
        config = (
            GopherAgentConfig.builder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .api_key("test-key")
            .headers(headers)
            .build()
        )
        headers["X-Test"] = "mutated"

        assert config.runtime_options is not None
        assert config.runtime_options.access_token is None
        assert config.runtime_options.headers == {"X-Test": "one"}

    def test_should_merge_access_token_and_headers(self):
        """Test access_token and headers can be combined."""
        config = (
            GopherAgentConfig.builder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .api_key("test-key")
            .runtime_options(
                {"access_token": "abc123", "headers": {"X-Test": "one"}}
            )
            .build()
        )

        assert config.runtime_options is not None
        assert config.runtime_options.headers == {
            "Authorization": "Bearer abc123",
            "X-Test": "one",
        }

    def test_should_prefer_explicit_authorization_header(self):
        """Test explicit Authorization header overrides access_token."""
        options = GopherAgentRuntimeOptions(
            access_token="abc123",
            headers={"Authorization": "Bearer override", "X-Test": "one"},
        )
        config = (
            GopherAgentConfig.builder()
            .provider("AnthropicProvider")
            .model("claude-3-haiku-20240307")
            .api_key("test-key")
            .runtime_options(options)
            .build()
        )

        assert config.runtime_options is not None
        assert config.runtime_options.access_token == "abc123"
        assert config.runtime_options.headers["Authorization"] == "Bearer override"
        assert config.runtime_options.headers["X-Test"] == "one"

    def test_should_reject_invalid_runtime_header_values(self):
        """Test runtime headers must be strings."""
        with pytest.raises(ValueError, match="headers must be a string mapping"):
            GopherAgentRuntimeOptions(headers={"X-Test": 1})

    def test_should_reject_invalid_runtime_access_token(self):
        """Test access_token must be a string."""
        with pytest.raises(ValueError, match="access_token must be a string"):
            GopherAgentRuntimeOptions(access_token=123)
