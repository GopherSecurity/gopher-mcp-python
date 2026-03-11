"""MCP tools for the server."""

from .weather_tools import (
    access_denied,
    get_condition_for_city,
    get_simulated_alerts,
    get_simulated_forecast,
    get_simulated_weather,
    get_temp_for_city,
    has_scope,
    register_weather_tools,
)

__all__ = [
    "register_weather_tools",
    "has_scope",
    "access_denied",
    "get_simulated_weather",
    "get_simulated_forecast",
    "get_simulated_alerts",
    "get_condition_for_city",
    "get_temp_for_city",
]
