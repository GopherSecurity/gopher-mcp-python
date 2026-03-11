"""Flask application factory.

Creates and configures the Flask application for the Auth MCP Server.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask_cors import CORS

from gopher_mcp_python.ffi.auth import (
    AuthClient,
    get_auth_library_version,
    init_auth_library,
    is_auth_available,
    shutdown_auth_library,
)

from .config import (
    AuthServerConfig,
    create_default_config,
    load_config_from_file,
)
from .middleware import OAuthAuthMiddleware
from .routes import register_health_routes, register_mcp_routes, register_oauth_routes
from .routes.mcp_handler import McpHandler
from .tools import register_weather_tools


def create_app(
    config: AuthServerConfig | None = None,
    config_path: str | Path | None = None,
) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional pre-built configuration.
        config_path: Optional path to configuration file.

    Returns:
        Configured Flask application.
    """
    # Load configuration
    if config is None:
        if config_path is not None:
            config = load_config_from_file(config_path)
        else:
            config = create_default_config()

    # Create Flask app
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # Enable CORS
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Store config in app context
    app.config["AUTH_SERVER_CONFIG"] = config

    # Initialize auth library if auth is enabled
    auth_client: AuthClient | None = None

    if not config.auth_disabled:
        if is_auth_available():
            try:
                init_auth_library()
                version = get_auth_library_version()
                app.config["AUTH_LIBRARY_VERSION"] = version

                # Create auth client
                auth_client = AuthClient(config.jwks_uri, config.issuer)

                # Set client options
                if config.jwks_cache_duration > 0:
                    auth_client.set_option(
                        "cache_duration", str(config.jwks_cache_duration)
                    )
                if config.jwks_auto_refresh:
                    auth_client.set_option("auto_refresh", "true")
                if config.request_timeout > 0:
                    auth_client.set_option(
                        "request_timeout", str(config.request_timeout)
                    )

                app.config["AUTH_CLIENT"] = auth_client
            except Exception as e:
                app.logger.error(f"Failed to initialize auth library: {e}")
                # Continue without auth
                config.auth_disabled = True
        else:
            app.logger.warning(
                "Auth functions not available - running without authentication"
            )
            config.auth_disabled = True

    # Create auth middleware
    auth_middleware = OAuthAuthMiddleware(auth_client, config)
    app.config["AUTH_MIDDLEWARE"] = auth_middleware

    # Register before_request handler for auth
    app.before_request(auth_middleware.before_request)

    # Get server version
    server_version = (
        app.config.get("AUTH_LIBRARY_VERSION", "1.0.0")
        if not config.auth_disabled
        else "1.0.0"
    )

    # Register health endpoint
    register_health_routes(app, version=server_version)

    # Register OAuth discovery endpoints
    register_oauth_routes(app, config)

    # Create and register MCP handler
    mcp_handler = McpHandler()
    app.config["MCP_HANDLER"] = mcp_handler
    register_mcp_routes(app, mcp_handler)

    # Register weather tools
    register_weather_tools(mcp_handler, auth_middleware)

    # Register teardown handler for cleanup
    @app.teardown_appcontext
    def cleanup(exception: BaseException | None = None) -> None:
        """Clean up resources on app context teardown."""
        pass  # Per-request cleanup if needed

    return app


def cleanup_app(app: Flask) -> None:
    """Clean up application resources.

    Call this when shutting down the application.

    Args:
        app: Flask application to clean up.
    """
    # Destroy auth client
    auth_client = app.config.get("AUTH_CLIENT")
    if auth_client is not None:
        try:
            auth_client.destroy()
        except Exception:
            pass

    # Shutdown auth library
    config = app.config.get("AUTH_SERVER_CONFIG")
    if config and not config.auth_disabled:
        try:
            shutdown_auth_library()
        except Exception:
            pass
