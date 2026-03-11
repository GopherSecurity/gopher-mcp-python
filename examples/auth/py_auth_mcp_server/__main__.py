"""Entry point for py_auth_mcp_server.

OAuth-protected MCP server example using gopher-auth FFI bindings.
Demonstrates JWT token validation with Keycloak and scope-based
access control for MCP tools.
"""

import argparse
import signal
import sys
from pathlib import Path
from typing import NoReturn

from .app import cleanup_app, create_app
from .config import AuthServerConfig


def print_banner() -> None:
    """Print startup banner."""
    print("")
    print("========================================")
    print("    Python Auth MCP Server")
    print("    OAuth-Protected MCP Example")
    print("========================================")
    print("")


def print_endpoints(config: AuthServerConfig) -> None:
    """Print endpoint information.

    Args:
        config: Server configuration.
    """
    base_url = config.server_url

    print("Endpoints:")
    print(f"  Health:       GET  {base_url}/health")
    print(f"  OAuth Meta:   GET  {base_url}/.well-known/oauth-protected-resource")
    print(f"  Auth Server:  GET  {base_url}/.well-known/oauth-authorization-server")
    print(f"  OIDC Config:  GET  {base_url}/.well-known/openid-configuration")
    print(f"  OAuth Auth:   GET  {base_url}/oauth/authorize")
    print(f"  MCP:          POST {base_url}/mcp")
    print(f"  RPC:          POST {base_url}/rpc")
    print("")

    if config.auth_disabled:
        print("Authentication: DISABLED")
    else:
        print("Authentication: ENABLED")
        print(f"  JWKS URI:     {config.jwks_uri}")
        print(f"  Issuer:       {config.issuer}")
    print("")


def main() -> NoReturn:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Python Auth MCP Server - OAuth-Protected MCP Example"
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help="Path to configuration file (default: server.config in current directory)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Override host from config",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override port from config",
    )
    parser.add_argument(
        "--no-auth",
        action="store_true",
        help="Disable authentication",
    )
    args = parser.parse_args()

    print_banner()

    # Determine config path
    if args.config:
        config_path = Path(args.config)
    else:
        # Try current directory first, then package directory
        cwd_config = Path.cwd() / "server.config"
        pkg_config = Path(__file__).parent.parent / "server.config"

        if cwd_config.exists():
            config_path = cwd_config
        elif pkg_config.exists():
            config_path = pkg_config
        else:
            config_path = None

    # Create app
    try:
        if config_path and config_path.exists():
            print(f"Loading configuration from: {config_path}")
            app = create_app(config_path=config_path)
            print("Configuration loaded successfully")
        else:
            print("No configuration file found, using defaults")
            app = create_app()
        print("")
    except Exception as e:
        print(f"Failed to create application: {e}")
        sys.exit(1)

    # Get config
    config: AuthServerConfig = app.config["AUTH_SERVER_CONFIG"]

    # Apply command-line overrides
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.no_auth:
        config.auth_disabled = True

    # Print auth info
    if not config.auth_disabled:
        version = app.config.get("AUTH_LIBRARY_VERSION", "unknown")
        print(f"Auth library version: {version}")
        print("")

    # Setup signal handlers
    def signal_handler(signum: int, frame: object) -> None:
        print("")
        print("Shutting down...")
        cleanup_app(app)
        print("Goodbye!")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Print startup info
    print(f"Starting server on {config.host}:{config.port}")
    print("")
    print_endpoints(config)
    print("Press Ctrl+C to shutdown")
    print("")

    # Run server
    try:
        app.run(
            host=config.host,
            port=config.port,
            debug=False,
            use_reloader=False,
        )
    except Exception as e:
        print(f"Server error: {e}")
        cleanup_app(app)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
