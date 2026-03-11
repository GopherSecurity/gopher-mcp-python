"""Tests for configuration module."""

import tempfile

import pytest

from py_auth_mcp_server.config import (
    AuthServerConfig,
    build_config,
    create_default_config,
    load_config_from_file,
    parse_config_file,
    validate_required_fields,
)


class TestParseConfigFile:
    """Tests for parse_config_file function."""

    def test_parses_key_value_pairs(self):
        """Test parsing simple key=value pairs."""
        content = "host=localhost\nport=3001"
        result = parse_config_file(content)
        assert result == {"host": "localhost", "port": "3001"}

    def test_ignores_comments(self):
        """Test that comments are ignored."""
        content = "# This is a comment\nhost=localhost\n# Another comment"
        result = parse_config_file(content)
        assert result == {"host": "localhost"}

    def test_ignores_empty_lines(self):
        """Test that empty lines are ignored."""
        content = "host=localhost\n\n\nport=3001\n"
        result = parse_config_file(content)
        assert result == {"host": "localhost", "port": "3001"}

    def test_ignores_whitespace_only_lines(self):
        """Test that whitespace-only lines are ignored."""
        content = "host=localhost\n   \n\t\nport=3001"
        result = parse_config_file(content)
        assert result == {"host": "localhost", "port": "3001"}

    def test_trims_whitespace(self):
        """Test that whitespace is trimmed from keys and values."""
        content = "  host  =  localhost  \n  port  =  3001  "
        result = parse_config_file(content)
        assert result == {"host": "localhost", "port": "3001"}

    def test_ignores_lines_without_equals(self):
        """Test that lines without '=' are ignored."""
        content = "host=localhost\ninvalid line\nport=3001"
        result = parse_config_file(content)
        assert result == {"host": "localhost", "port": "3001"}

    def test_handles_values_with_equals(self):
        """Test values containing '=' are preserved."""
        content = "url=http://example.com?foo=bar"
        result = parse_config_file(content)
        assert result == {"url": "http://example.com?foo=bar"}

    def test_empty_content(self):
        """Test parsing empty content."""
        result = parse_config_file("")
        assert result == {}

    def test_only_comments(self):
        """Test parsing content with only comments."""
        content = "# comment 1\n# comment 2"
        result = parse_config_file(content)
        assert result == {}


class TestBuildConfig:
    """Tests for build_config function."""

    def test_default_values(self):
        """Test default values are applied."""
        config = build_config({"auth_disabled": "true"})
        assert config.host == "0.0.0.0"
        assert config.port == 3001
        assert config.jwks_cache_duration == 3600
        assert config.jwks_auto_refresh is True
        assert config.request_timeout == 30

    def test_custom_values(self):
        """Test custom values override defaults."""
        config = build_config(
            {
                "host": "127.0.0.1",
                "port": "8080",
                "auth_disabled": "true",
            }
        )
        assert config.host == "127.0.0.1"
        assert config.port == 8080

    def test_port_type_conversion(self):
        """Test port is converted to integer."""
        config = build_config({"port": "9000", "auth_disabled": "true"})
        assert config.port == 9000
        assert isinstance(config.port, int)

    def test_boolean_type_conversion(self):
        """Test boolean values are converted correctly."""
        config = build_config(
            {
                "auth_disabled": "true",
                "jwks_auto_refresh": "false",
            }
        )
        assert config.auth_disabled is True
        assert config.jwks_auto_refresh is False

    def test_server_url_default(self):
        """Test server_url defaults to localhost with port."""
        config = build_config({"port": "5000", "auth_disabled": "true"})
        assert config.server_url == "http://localhost:5000"

    def test_server_url_custom(self):
        """Test custom server_url."""
        config = build_config(
            {
                "server_url": "https://api.example.com",
                "auth_disabled": "true",
            }
        )
        assert config.server_url == "https://api.example.com"


class TestEndpointDerivation:
    """Tests for endpoint derivation from auth_server_url."""

    def test_derives_jwks_uri(self):
        """Test jwks_uri is derived from auth_server_url."""
        config = build_config(
            {
                "auth_server_url": "https://auth.example.com/realms/test",
                "client_id": "test-client",
                "client_secret": "secret",
            }
        )
        assert config.jwks_uri == (
            "https://auth.example.com/realms/test/protocol/openid-connect/certs"
        )

    def test_derives_token_endpoint(self):
        """Test token_endpoint is derived from auth_server_url."""
        config = build_config(
            {
                "auth_server_url": "https://auth.example.com/realms/test",
                "client_id": "test-client",
                "client_secret": "secret",
            }
        )
        assert config.token_endpoint == (
            "https://auth.example.com/realms/test/protocol/openid-connect/token"
        )

    def test_derives_issuer(self):
        """Test issuer is derived from auth_server_url."""
        config = build_config(
            {
                "auth_server_url": "https://auth.example.com/realms/test",
                "client_id": "test-client",
                "client_secret": "secret",
            }
        )
        assert config.issuer == "https://auth.example.com/realms/test"

    def test_explicit_values_not_overwritten(self):
        """Test explicit values are not overwritten by derivation."""
        config = build_config(
            {
                "auth_server_url": "https://auth.example.com/realms/test",
                "jwks_uri": "https://custom.example.com/jwks",
                "issuer": "https://custom-issuer.example.com",
                "client_id": "test-client",
                "client_secret": "secret",
            }
        )
        assert config.jwks_uri == "https://custom.example.com/jwks"
        assert config.issuer == "https://custom-issuer.example.com"


class TestValidateRequiredFields:
    """Tests for validate_required_fields function."""

    def test_auth_disabled_skips_validation(self):
        """Test validation is skipped when auth is disabled."""
        config = create_default_config(auth_disabled=True)
        # Should not raise
        validate_required_fields(config)

    def test_missing_client_id_raises(self):
        """Test missing client_id raises ValueError."""
        config = create_default_config(
            auth_disabled=False,
            client_secret="secret",
            jwks_uri="https://example.com/jwks",
        )
        with pytest.raises(ValueError, match="client_id"):
            validate_required_fields(config)

    def test_missing_client_secret_raises(self):
        """Test missing client_secret raises ValueError."""
        config = create_default_config(
            auth_disabled=False,
            client_id="test-client",
            jwks_uri="https://example.com/jwks",
        )
        with pytest.raises(ValueError, match="client_secret"):
            validate_required_fields(config)

    def test_missing_jwks_uri_and_auth_server_url_raises(self):
        """Test missing jwks_uri and auth_server_url raises ValueError."""
        config = create_default_config(
            auth_disabled=False,
            client_id="test-client",
            client_secret="secret",
        )
        with pytest.raises(ValueError, match="jwks_uri"):
            validate_required_fields(config)

    def test_valid_config_passes(self):
        """Test valid configuration passes validation."""
        config = create_default_config(
            auth_disabled=False,
            client_id="test-client",
            client_secret="secret",
            jwks_uri="https://example.com/jwks",
        )
        # Should not raise
        validate_required_fields(config)


class TestLoadConfigFromFile:
    """Tests for load_config_from_file function."""

    def test_loads_config_from_file(self):
        """Test loading configuration from file."""
        content = """
host=127.0.0.1
port=8080
auth_disabled=true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".config", delete=False) as f:
            f.write(content)
            f.flush()
            config = load_config_from_file(f.name)

        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.auth_disabled is True

    def test_file_not_found_raises(self):
        """Test FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            load_config_from_file("/nonexistent/path/config.txt")


class TestCreateDefaultConfig:
    """Tests for create_default_config function."""

    def test_creates_default_config(self):
        """Test creating default configuration."""
        config = create_default_config()
        assert config.host == "0.0.0.0"
        assert config.port == 3001
        assert config.auth_disabled is True

    def test_accepts_overrides(self):
        """Test overrides are applied."""
        config = create_default_config(
            host="localhost",
            port=5000,
            auth_disabled=False,
        )
        assert config.host == "localhost"
        assert config.port == 5000
        assert config.auth_disabled is False


class TestAuthServerConfigDataclass:
    """Tests for AuthServerConfig dataclass."""

    def test_post_init_sets_server_url(self):
        """Test __post_init__ sets server_url default."""
        config = AuthServerConfig(port=9000)
        assert config.server_url == "http://localhost:9000"

    def test_explicit_server_url_preserved(self):
        """Test explicit server_url is not overwritten."""
        config = AuthServerConfig(
            port=9000,
            server_url="https://api.example.com",
        )
        assert config.server_url == "https://api.example.com"
