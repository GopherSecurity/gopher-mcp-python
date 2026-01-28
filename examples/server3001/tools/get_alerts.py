"""
Get weather alerts for a region.
No authentication required - public tool.
"""

import random
from datetime import datetime, timedelta


def get_alerts(request: dict) -> dict:
    """Get weather alerts for a specific region."""
    params = request.get("params", {})
    region = params.get("region", "Unknown Region")

    # Simulate alerts (most of the time there are none)
    has_alert = random.random() < 0.3

    if not has_alert:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"No active weather alerts for {region}.",
                }
            ],
        }

    alert_types = [
        ("Heat Advisory", "High temperatures expected. Stay hydrated and avoid prolonged outdoor activities."),
        ("Severe Thunderstorm Warning", "Dangerous thunderstorms approaching. Seek shelter immediately."),
        ("Flash Flood Watch", "Potential for flash flooding. Avoid low-lying areas."),
        ("Winter Storm Warning", "Heavy snow expected. Travel may be hazardous."),
        ("High Wind Advisory", "Strong winds expected. Secure loose outdoor objects."),
    ]

    alert_type, description = random.choice(alert_types)
    expires = datetime.now() + timedelta(hours=random.randint(6, 48))

    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Weather Alert for {region}:\n\n"
                    f"⚠️ {alert_type}\n\n"
                    f"{description}\n\n"
                    f"Expires: {expires.strftime('%Y-%m-%d %H:%M')}"
                ),
            }
        ],
    }
