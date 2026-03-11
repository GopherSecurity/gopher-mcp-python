"""Weather Tools.

Example MCP tools demonstrating OAuth scope-based access control.
Mirrors the weather tools from the C++ auth example.
"""

from __future__ import annotations

import json
from typing import Any

from ..middleware.oauth_auth import OAuthAuthMiddleware
from ..routes.mcp_handler import McpHandler, ToolContentItem, ToolResult


def has_scope(scopes: str, required: str) -> bool:
    """Check if a scope is present in a space-separated scope string.

    Args:
        scopes: Space-separated scope string.
        required: Required scope to check for.

    Returns:
        True if the required scope is present.
    """
    if not scopes or not required:
        return False
    return required in scopes.split()


# Weather conditions for simulation
CONDITIONS = [
    "Sunny",
    "Cloudy",
    "Rainy",
    "Partly Cloudy",
    "Windy",
    "Stormy",
]


def _hash_string(s: str) -> int:
    """Get a deterministic hash for a string."""
    return sum(ord(c) for c in s)


def get_condition_for_city(city: str, offset: int = 0) -> str:
    """Get a deterministic but varying condition based on city name.

    Args:
        city: City name.
        offset: Day offset for variation.

    Returns:
        Weather condition string.
    """
    h = _hash_string(city)
    return CONDITIONS[(h + offset) % len(CONDITIONS)]


def get_temp_for_city(city: str, offset: int = 0) -> int:
    """Get a deterministic but varying temperature based on city name.

    Args:
        city: City name.
        offset: Day offset for variation.

    Returns:
        Temperature in Celsius.
    """
    h = _hash_string(city)
    # Temperature between 10-35 Celsius
    return 10 + ((h + offset * 7) % 26)


def get_simulated_weather(city: str) -> dict[str, Any]:
    """Get simulated current weather for a city.

    Args:
        city: City name.

    Returns:
        Weather data dictionary.
    """
    h = _hash_string(city)

    return {
        "city": city,
        "temperature": get_temp_for_city(city),
        "condition": get_condition_for_city(city),
        "humidity": 40 + (h % 40),  # 40-80%
        "windSpeed": 5 + (h % 25),  # 5-30 km/h
    }


def get_simulated_forecast(city: str) -> list[dict[str, Any]]:
    """Get simulated 5-day forecast for a city.

    Args:
        city: City name.

    Returns:
        List of daily forecasts.
    """
    days = ["Today", "Tomorrow", "Day 3", "Day 4", "Day 5"]

    return [
        {
            "day": day,
            "high": get_temp_for_city(city, index) + 5,
            "low": get_temp_for_city(city, index) - 5,
            "condition": get_condition_for_city(city, index),
        }
        for index, day in enumerate(days)
    ]


def get_simulated_alerts(region: str) -> list[dict[str, Any]]:
    """Get simulated weather alerts for a region.

    Args:
        region: Region name.

    Returns:
        List of weather alerts.
    """
    h = _hash_string(region)

    # Return different alerts based on region
    if h % 3 == 0:
        return [
            {
                "type": "Heat Warning",
                "severity": "moderate",
                "message": f"High temperatures expected in {region}. Stay hydrated.",
            },
        ]
    elif h % 3 == 1:
        return [
            {
                "type": "Storm Watch",
                "severity": "high",
                "message": (
                    f"Severe thunderstorms possible in {region}. "
                    "Seek shelter if needed."
                ),
            },
            {
                "type": "Wind Advisory",
                "severity": "low",
                "message": (
                    f"Strong winds expected in {region}. Secure loose objects."
                ),
            },
        ]
    else:
        return []  # No alerts


def access_denied(scope: str) -> ToolResult:
    """Create an access denied error result.

    Args:
        scope: Required scope that was missing.

    Returns:
        ToolResult with error.
    """
    return ToolResult(
        content=[
            ToolContentItem(
                type="text",
                text=json.dumps(
                    {
                        "error": "access_denied",
                        "message": f"Access denied. Required scope: {scope}",
                    }
                ),
            ),
        ],
        is_error=True,
    )


def register_weather_tools(
    mcp: McpHandler,
    auth_middleware: OAuthAuthMiddleware | None,
) -> None:
    """Register weather tools with the MCP handler.

    Args:
        mcp: MCP handler instance.
        auth_middleware: OAuth auth middleware instance (None if auth disabled).
    """

    # get-weather - No authentication required
    @mcp.tool(
        name="get-weather",
        description="Get current weather for a city. No authentication required.",
        input_schema={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name to get weather for",
                },
            },
            "required": ["city"],
        },
    )
    def get_weather(args: dict[str, Any]) -> ToolResult:
        city = str(args.get("city", "Unknown"))
        weather = get_simulated_weather(city)

        return ToolResult(
            content=[
                ToolContentItem(
                    type="text",
                    text=json.dumps(weather, indent=2),
                ),
            ],
        )

    # get-forecast - Requires mcp:read scope
    @mcp.tool(
        name="get-forecast",
        description="Get 5-day weather forecast for a city. Requires mcp:read scope.",
        input_schema={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name to get forecast for",
                },
            },
            "required": ["city"],
        },
    )
    def get_forecast(args: dict[str, Any]) -> ToolResult:
        # Check scope if auth is enabled
        if auth_middleware and not auth_middleware.is_auth_disabled():
            context = auth_middleware.get_auth_context()
            if not has_scope(context.scopes, "mcp:read"):
                return access_denied("mcp:read")

        city = str(args.get("city", "Unknown"))
        forecast = get_simulated_forecast(city)

        return ToolResult(
            content=[
                ToolContentItem(
                    type="text",
                    text=json.dumps({"city": city, "forecast": forecast}, indent=2),
                ),
            ],
        )

    # get-weather-alerts - Requires mcp:admin scope
    @mcp.tool(
        name="get-weather-alerts",
        description="Get weather alerts for a region. Requires mcp:admin scope.",
        input_schema={
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Region name to get alerts for",
                },
            },
            "required": ["region"],
        },
    )
    def get_weather_alerts(args: dict[str, Any]) -> ToolResult:
        # Check scope if auth is enabled
        if auth_middleware and not auth_middleware.is_auth_disabled():
            context = auth_middleware.get_auth_context()
            if not has_scope(context.scopes, "mcp:admin"):
                return access_denied("mcp:admin")

        region = str(args.get("region", "Unknown"))
        alerts = get_simulated_alerts(region)

        return ToolResult(
            content=[
                ToolContentItem(
                    type="text",
                    text=json.dumps({"region": region, "alerts": alerts}, indent=2),
                ),
            ],
        )
