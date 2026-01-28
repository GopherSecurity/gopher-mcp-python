"""
Get current weather for a city.
No authentication required - public tool.
"""

import random


def get_weather(request: dict) -> dict:
    """Get current weather information for a specific city."""
    params = request.get("params", {})
    city = params.get("city", "")

    # Simulate weather data (in a real app, you'd call a weather API)
    weather_data = {
        "London": {"temp": 15, "condition": "Cloudy", "humidity": 75},
        "New York": {"temp": 22, "condition": "Sunny", "humidity": 60},
        "Tokyo": {"temp": 18, "condition": "Rainy", "humidity": 80},
        "Paris": {"temp": 17, "condition": "Partly Cloudy", "humidity": 70},
        "Sydney": {"temp": 25, "condition": "Sunny", "humidity": 55},
    }

    weather = weather_data.get(city)
    if weather is None:
        weather = {
            "temp": random.randint(10, 40),
            "condition": random.choice(["Sunny", "Cloudy", "Rainy", "Partly Cloudy"]),
            "humidity": random.randint(50, 90),
        }

    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Weather in {city}:\n"
                    f"Temperature: {weather['temp']}°C\n"
                    f"Condition: {weather['condition']}\n"
                    f"Humidity: {weather['humidity']}%"
                ),
            }
        ],
    }
