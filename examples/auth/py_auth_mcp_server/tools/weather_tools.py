"""Weather Tools.

Example MCP tools demonstrating OAuth scope-based access control.
Scope checking is handled by middleware configuration, so tool
handlers focus on business logic.
"""

from __future__ import annotations

import json
from typing import Any

from gopher_mcp_python.auth import GopherAuth

from ..routes.mcp_handler import McpHandler, ToolContentItem, ToolResult


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
    return sum(ord(c) for c in s)


def get_condition_for_city(city: str, offset: int = 0) -> str:
    h = _hash_string(city)
    return CONDITIONS[(h + offset) % len(CONDITIONS)]


def get_temp_for_city(city: str, offset: int = 0) -> int:
    h = _hash_string(city)
    return 10 + ((h + offset * 7) % 26)


def get_simulated_weather(city: str) -> dict[str, Any]:
    h = _hash_string(city)
    return {
        "city": city,
        "temperature": get_temp_for_city(city),
        "condition": get_condition_for_city(city),
        "humidity": 40 + (h % 40),
        "windSpeed": 5 + (h % 25),
    }


def get_simulated_forecast(city: str) -> list[dict[str, Any]]:
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
    h = _hash_string(region)
    if h % 3 == 0:
        return [{"type": "Heat Warning", "severity": "moderate",
                 "message": f"High temperatures in {region}."}]
    elif h % 3 == 1:
        return [
            {"type": "Storm Watch", "severity": "high",
             "message": f"Thunderstorms possible in {region}."},
            {"type": "Wind Advisory", "severity": "low",
             "message": f"Strong winds in {region}."},
        ]
    return []


def register_weather_tools(
    mcp: McpHandler,
    _auth: GopherAuth,
) -> None:
    """Register weather tools with the MCP handler."""

    @mcp.tool(
        name="get-weather",
        description="Get current weather for a city. No auth required.",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    )
    def get_weather(args: dict[str, Any]) -> ToolResult:
        city = str(args.get("city", "Unknown"))
        return ToolResult(
            content=[ToolContentItem(type="text", text=json.dumps(get_simulated_weather(city), indent=2))],
        )

    @mcp.tool(
        name="get-forecast",
        description="Get 5-day forecast. Requires mcp:read scope.",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    )
    def get_forecast(args: dict[str, Any]) -> ToolResult:
        city = str(args.get("city", "Unknown"))
        return ToolResult(
            content=[ToolContentItem(type="text", text=json.dumps({"city": city, "forecast": get_simulated_forecast(city)}, indent=2))],
        )

    @mcp.tool(
        name="get-weather-alerts",
        description="Get weather alerts. Requires mcp:admin scope.",
        input_schema={
            "type": "object",
            "properties": {"region": {"type": "string", "description": "Region name"}},
            "required": ["region"],
        },
    )
    def get_weather_alerts(args: dict[str, Any]) -> ToolResult:
        region = str(args.get("region", "Unknown"))
        return ToolResult(
            content=[ToolContentItem(type="text", text=json.dumps({"region": region, "alerts": get_simulated_alerts(region)}, indent=2))],
        )
