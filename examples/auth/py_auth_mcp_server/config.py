"""Configuration loader for Auth MCP Server.

Mirrors AuthServerConfig from the C++ example:
/gopher-orch/examples/auth/auth_server_config.h
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AuthServerConfig:
    """Server configuration for the Auth MCP Server."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 3001
    server_url: str = ""

    # OAuth/IDP settings
    auth_server_url: str = ""
    jwks_uri: str = ""
    issuer: str = ""
    client_id: str = ""
    client_secret: str = ""
    token_endpoint: str = ""

    # Direct OAuth endpoint URLs
    oauth_authorize_url: str = ""
    oauth_token_url: str = ""

    # Scopes
    allowed_scopes: str = "openid profile email mcp:read mcp:admin"

    # Cache settings
    jwks_cache_duration: int = 3600
    jwks_auto_refresh: bool = True
    request_timeout: int = 30

    # Auth bypass mode
    auth_disabled: bool = False

    def __post_init__(self) -> None:
        """Set derived defaults after initialization."""
        if not self.server_url:
            self.server_url = f"http://localhost:{self.port}"


def parse_config_file(content: str) -> dict[str, str]:
    """Parse a configuration file in key=value format.

    Args:
        content: Raw file content.

    Returns:
        Parsed key-value map.
    """
    result: dict[str, str] = {}

    for line in content.split("\n"):
        trimmed = line.strip()

        # Skip empty lines and comments
        if not trimmed or trimmed.startswith("#"):
            continue

        eq_index = trimmed.find("=")
        if eq_index == -1:
            continue

        key = trimmed[:eq_index].strip()
        value = trimmed[eq_index + 1 :].strip()

        if key:
            result[key] = value

    return result


def load_config_from_file(config_path: str | Path) -> AuthServerConfig:
    """Load and parse configuration from a file.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Parsed AuthServerConfig.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    content = path.read_text(encoding="utf-8")
    config_map = parse_config_file(content)

    return build_config(config_map)


def load_config_from_default_location(base_path: str | Path) -> AuthServerConfig:
    """Load configuration from the default location relative to a base path.

    Args:
        base_path: Base path (typically __file__ directory or executable path).

    Returns:
        Parsed AuthServerConfig.
    """
    config_path = Path(base_path) / "server.config"
    return load_config_from_file(config_path)


def build_config(config_map: dict[str, str]) -> AuthServerConfig:
    """Build AuthServerConfig from a parsed key-value map.

    Args:
        config_map: Parsed configuration map.

    Returns:
        AuthServerConfig object.

    Raises:
        ValueError: If required fields are missing when auth is enabled.
    """
    port = int(config_map.get("port", "3001"))

    config = AuthServerConfig(
        # Server settings
        host=config_map.get("host", "0.0.0.0"),
        port=port,
        server_url=config_map.get("server_url", f"http://localhost:{port}"),
        # OAuth/IDP settings
        auth_server_url=config_map.get("auth_server_url", ""),
        jwks_uri=config_map.get("jwks_uri", ""),
        issuer=config_map.get("issuer", ""),
        client_id=config_map.get("client_id", ""),
        client_secret=config_map.get("client_secret", ""),
        token_endpoint=config_map.get("token_endpoint", ""),
        # Direct OAuth endpoint URLs
        oauth_authorize_url=config_map.get("oauth_authorize_url", ""),
        oauth_token_url=config_map.get("oauth_token_url", ""),
        # Scopes
        allowed_scopes=config_map.get(
            "allowed_scopes", "openid profile email mcp:read mcp:admin"
        ),
        # Cache settings
        jwks_cache_duration=int(config_map.get("jwks_cache_duration", "3600")),
        jwks_auto_refresh=config_map.get("jwks_auto_refresh", "true") != "false",
        request_timeout=int(config_map.get("request_timeout", "30")),
        # Auth bypass mode
        auth_disabled=config_map.get("auth_disabled", "false") == "true",
    )

    # Derive endpoints from auth_server_url if not explicitly set
    if config.auth_server_url:
        if not config.jwks_uri:
            config.jwks_uri = f"{config.auth_server_url}/protocol/openid-connect/certs"
        if not config.token_endpoint:
            config.token_endpoint = (
                f"{config.auth_server_url}/protocol/openid-connect/token"
            )
        if not config.issuer:
            config.issuer = config.auth_server_url
        if not config.oauth_authorize_url:
            config.oauth_authorize_url = (
                f"{config.auth_server_url}/protocol/openid-connect/auth"
            )
        if not config.oauth_token_url:
            config.oauth_token_url = (
                f"{config.auth_server_url}/protocol/openid-connect/token"
            )

    # Validate required fields when auth is enabled
    if not config.auth_disabled:
        validate_required_fields(config)

    return config


def validate_required_fields(config: AuthServerConfig) -> None:
    """Validate that required configuration fields are present.

    Args:
        config: Configuration to validate.

    Raises:
        ValueError: If required fields are missing.
    """
    errors: list[str] = []

    if not config.client_id:
        errors.append("client_id is required when auth is enabled")
    if not config.client_secret:
        errors.append("client_secret is required when auth is enabled")
    if not config.jwks_uri and not config.auth_server_url:
        errors.append("jwks_uri or auth_server_url is required when auth is enabled")

    if errors:
        raise ValueError(
            "Configuration validation failed:\n  - " + "\n  - ".join(errors)
        )


def create_default_config(**overrides: Any) -> AuthServerConfig:
    """Create a default configuration for testing or development.

    Args:
        **overrides: Optional overrides for default values.

    Returns:
        AuthServerConfig with defaults.
    """
    defaults = {
        "host": "0.0.0.0",
        "port": 3001,
        "server_url": "http://localhost:3001",
        "auth_server_url": "",
        "jwks_uri": "",
        "issuer": "",
        "client_id": "",
        "client_secret": "",
        "token_endpoint": "",
        "oauth_authorize_url": "",
        "oauth_token_url": "",
        "allowed_scopes": "openid profile email mcp:read mcp:admin",
        "jwks_cache_duration": 3600,
        "jwks_auto_refresh": True,
        "request_timeout": 30,
        "auth_disabled": True,
    }
    defaults.update(overrides)
    return AuthServerConfig(**defaults)
