"""Flask application factory using GopherAuth reusable module.

Creates and configures the Flask application for the Auth MCP Server.
Replaces manual auth setup with the GopherAuth module from
gopher_mcp_python.auth.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask_cors import CORS

from gopher_mcp_python.auth import GopherAuth

from .routes.mcp_handler import McpHandler
from .routes import register_mcp_routes
from .tools import register_weather_tools


def create_app(
    config_path: str | Path | None = None,
    auth_disabled: bool = False,
) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_path: Path to server.config file.
        auth_disabled: If True, disable authentication entirely.

    Returns:
        Configured Flask application.
    """
    # Initialize GopherAuth from config file
    auth = GopherAuth(
        config_path=str(config_path) if config_path else None,
        auth_disabled=auth_disabled,
    )
    auth.initialize()

    # Create Flask app
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["GOPHER_AUTH"] = auth

    # Enable CORS
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Register health endpoint
    @app.route("/health")
    def health():
        return {"status": "healthy", "service": "py-auth-mcp-server"}

    # Create and register MCP handler
    mcp_handler = McpHandler()
    app.config["MCP_HANDLER"] = mcp_handler
    register_mcp_routes(app, mcp_handler)

    # Register weather tools (scope checking can be added via middleware)
    register_weather_tools(mcp_handler, auth)

    return app


def cleanup_app(app: Flask) -> None:
    """Clean up application resources."""
    auth = app.config.get("GOPHER_AUTH")
    if auth is not None:
        auth.shutdown()
