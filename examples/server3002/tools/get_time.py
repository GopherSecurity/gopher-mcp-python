"""
Get current time for a timezone or location.
No authentication required - public tool.
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo


# Map common city names to timezones
CITY_TO_TIMEZONE = {
    "london": "Europe/London",
    "new york": "America/New_York",
    "tokyo": "Asia/Tokyo",
    "paris": "Europe/Paris",
    "france": "Europe/Paris",
    "sydney": "Australia/Sydney",
    "los angeles": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "dubai": "Asia/Dubai",
    "singapore": "Asia/Singapore",
    "mumbai": "Asia/Kolkata",
    "beijing": "Asia/Shanghai",
    "moscow": "Europe/Moscow",
    "berlin": "Europe/Berlin",
    "toronto": "America/Toronto",
}


def get_time(request: dict) -> dict:
    """Get current time and date for a specific timezone or city."""
    # Handle different parameter structures
    location = None

    params = request.get("params", {})
    arguments = params.get("arguments")

    if arguments:
        if isinstance(arguments, str):
            # Gopher-orch sends arguments as JSON string
            try:
                parsed_args = json.loads(arguments)
                location = parsed_args.get("location")
            except json.JSONDecodeError:
                pass
        elif isinstance(arguments, dict):
            # Direct calls send arguments as object
            location = arguments.get("location")

    if location is None:
        location = params.get("location")

    if not location:
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error: No location parameter provided",
                }
            ],
            "isError": True,
        }

    # Determine timezone
    timezone = location
    normalized_location = location.lower()

    if normalized_location in CITY_TO_TIMEZONE:
        timezone = CITY_TO_TIMEZONE[normalized_location]

    try:
        # Get current time in specified timezone
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)

        time_in_timezone = now.strftime("%B %d, %Y at %I:%M:%S %p %Z")
        date_only = now.strftime("%A, %B %d, %Y")
        time_only = now.strftime("%I:%M:%S %p %Z")

        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Current time in {location}:\n\n"
                        f"Full Date & Time: {time_in_timezone}\n"
                        f"Date: {date_only}\n"
                        f"Time: {time_only}\n"
                        f"Timezone: {timezone}"
                    ),
                }
            ],
        }
    except Exception:
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f'Error: Invalid timezone or location "{location}". '
                        'Please use a valid timezone (e.g., "UTC", "America/New_York") '
                        'or city name (e.g., "London", "Tokyo").'
                    ),
                }
            ],
            "isError": True,
        }
