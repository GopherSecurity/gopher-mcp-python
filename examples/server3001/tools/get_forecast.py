"""
Get weather forecast for a city.
No authentication required - public tool.
"""

import random


def get_forecast(request: dict) -> dict:
    """Get weather forecast for a specific city."""
    params = request.get("params", {})
    city = params.get("city", "Unknown")
    days = params.get("days", 3)

    # Ensure days is within valid range
    days = max(1, min(7, days))

    conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Thunderstorms"]

    forecast_lines = [f"Weather forecast for {city}:"]
    for i in range(days):
        day_name = ["Today", "Tomorrow"][i] if i < 2 else f"Day {i + 1}"
        temp_high = random.randint(15, 35)
        temp_low = temp_high - random.randint(5, 12)
        condition = random.choice(conditions)
        forecast_lines.append(
            f"\n{day_name}:\n"
            f"  High: {temp_high}°C, Low: {temp_low}°C\n"
            f"  Condition: {condition}"
        )

    return {
        "content": [
            {
                "type": "text",
                "text": "".join(forecast_lines),
            }
        ],
    }
