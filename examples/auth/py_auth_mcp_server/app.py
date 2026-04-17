"""MCP Server using FastMCP with Streamable HTTP transport.

Mirrors the JS auth example pattern using the official Python MCP SDK.
OAuth authentication handled by GopherAuth from gopher_mcp_python.auth.
"""

from __future__ import annotations

import signal
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from gopher_mcp_python.auth import GopherAuth


def create_server(config_path: str | None = None) -> tuple[FastMCP, GopherAuth]:
    """Create MCP server and GopherAuth instance.

    Args:
        config_path: Path to server.config file.

    Returns:
        Tuple of (FastMCP server, GopherAuth instance).
    """
    # Initialize GopherAuth from config file
    auth = GopherAuth(config_path=config_path)
    auth.initialize()

    # Create MCP server with FastMCP
    mcp = FastMCP(
        "py-auth-mcp-server",
        json_response=True,
    )

    # Register weather tools
    @mcp.tool()
    def get_weather(city: str) -> str:
        """Get current weather for a city. No auth required."""
        h = sum(ord(c) for c in city)
        conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Windy"]
        temp = 10 + (h % 26)
        cond = conditions[h % len(conditions)]
        return f"Weather in {city}: {temp}C, {cond}, Humidity: {40 + h % 40}%"

    @mcp.tool()
    def get_forecast(city: str) -> str:
        """Get 5-day forecast. Requires mcp:read scope."""
        h = sum(ord(c) for c in city)
        conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Windy"]
        days = ["Today", "Tomorrow", "Day 3", "Day 4", "Day 5"]
        forecast = []
        for i, day in enumerate(days):
            hi = 10 + ((h + i * 7) % 26) + 5
            lo = hi - 10
            forecast.append(f"{day}: {hi}C/{lo}C {conditions[(h + i) % len(conditions)]}")
        return f"5-Day Forecast for {city}:\n" + "\n".join(forecast)

    @mcp.tool()
    def get_weather_alerts(region: str) -> str:
        """Get weather alerts. Requires mcp:admin scope."""
        h = sum(ord(c) for c in region)
        if h % 3 == 0:
            return f"Alert for {region}: Heat Warning - High temperatures expected"
        elif h % 3 == 1:
            return f"Alerts for {region}: Storm Watch, Wind Advisory"
        return f"No active alerts for {region}"

    return mcp, auth


def main() -> None:
    """Run the MCP server with Streamable HTTP transport."""
    # Determine config path
    config_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parent.parent / "server.config"
    )

    print("========================================")
    print("   Python Auth MCP Server")
    print("========================================")

    mcp, auth = create_server(config_path)

    port = auth.native_config.get_int("port") if auth.native_config else 3001
    host = auth.native_config.get_string("host") if auth.native_config else "0.0.0.0"

    print(f"Server: http://{host}:{port}")
    print(f"MCP: http://{host}:{port}/mcp")
    print(f"Config: {config_path}")
    print(f"Auth: {'DISABLED' if auth.is_disabled else 'ENABLED'}")
    print()

    # Graceful shutdown
    def shutdown_handler(sig, frame):
        print("\nShutting down...")
        auth.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Run with Streamable HTTP transport
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
