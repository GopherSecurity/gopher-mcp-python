"""Tests for weather tools."""

import json

from py_auth_mcp_server.tools.weather_tools import (
    CONDITIONS,
    access_denied,
    get_condition_for_city,
    get_simulated_alerts,
    get_simulated_forecast,
    get_simulated_weather,
    get_temp_for_city,
    has_scope,
)


class TestHasScope:
    """Tests for has_scope function."""

    def test_scope_present(self):
        """Test returns True when scope is present."""
        assert has_scope("openid profile email mcp:read", "mcp:read") is True
        assert has_scope("openid profile", "openid") is True
        assert has_scope("mcp:admin", "mcp:admin") is True

    def test_scope_not_present(self):
        """Test returns False when scope is not present."""
        assert has_scope("openid profile email", "mcp:read") is False
        assert has_scope("mcp:read", "mcp:admin") is False

    def test_empty_scopes(self):
        """Test returns False for empty scopes."""
        assert has_scope("", "mcp:read") is False
        assert has_scope("   ", "mcp:read") is False

    def test_empty_required(self):
        """Test returns False for empty required scope."""
        assert has_scope("openid profile", "") is False

    def test_none_values(self):
        """Test returns False for None values."""
        assert has_scope(None, "mcp:read") is False
        assert has_scope("openid", None) is False

    def test_partial_match_not_accepted(self):
        """Test partial matches are not accepted."""
        assert has_scope("mcp:readonly", "mcp:read") is False
        assert has_scope("admin", "mcp:admin") is False


class TestGetConditionForCity:
    """Tests for get_condition_for_city function."""

    def test_returns_valid_condition(self):
        """Test returns a valid weather condition."""
        condition = get_condition_for_city("London")
        assert condition in CONDITIONS

    def test_deterministic(self):
        """Test same city always returns same condition."""
        condition1 = get_condition_for_city("Paris")
        condition2 = get_condition_for_city("Paris")
        assert condition1 == condition2

    def test_different_cities_may_differ(self):
        """Test different cities may have different conditions."""
        cities = ["London", "Paris", "Tokyo", "Sydney", "Cairo"]
        conditions = [get_condition_for_city(city) for city in cities]
        # Not all should be the same (statistically unlikely)
        assert len(set(conditions)) > 1

    def test_offset_changes_condition(self):
        """Test offset changes the condition."""
        conditions = [get_condition_for_city("London", offset=i) for i in range(6)]
        # With 6 conditions and 6 offsets, we should cycle through
        assert len(set(conditions)) > 1


class TestGetTempForCity:
    """Tests for get_temp_for_city function."""

    def test_returns_valid_temperature(self):
        """Test returns temperature in valid range (10-35)."""
        temp = get_temp_for_city("London")
        assert 10 <= temp <= 35

    def test_deterministic(self):
        """Test same city always returns same temperature."""
        temp1 = get_temp_for_city("Berlin")
        temp2 = get_temp_for_city("Berlin")
        assert temp1 == temp2

    def test_offset_changes_temperature(self):
        """Test offset changes the temperature."""
        temps = [get_temp_for_city("London", offset=i) for i in range(5)]
        # Different offsets should give different temperatures
        assert len(set(temps)) > 1


class TestGetSimulatedWeather:
    """Tests for get_simulated_weather function."""

    def test_returns_all_fields(self):
        """Test returns all expected fields."""
        weather = get_simulated_weather("London")
        assert "city" in weather
        assert "temperature" in weather
        assert "condition" in weather
        assert "humidity" in weather
        assert "windSpeed" in weather

    def test_city_is_correct(self):
        """Test city name is correct."""
        weather = get_simulated_weather("Tokyo")
        assert weather["city"] == "Tokyo"

    def test_humidity_in_range(self):
        """Test humidity is in valid range (40-80)."""
        weather = get_simulated_weather("Cairo")
        assert 40 <= weather["humidity"] <= 79

    def test_wind_speed_in_range(self):
        """Test wind speed is in valid range (5-30)."""
        weather = get_simulated_weather("Sydney")
        assert 5 <= weather["windSpeed"] <= 29

    def test_deterministic(self):
        """Test same city returns same weather."""
        weather1 = get_simulated_weather("Madrid")
        weather2 = get_simulated_weather("Madrid")
        assert weather1 == weather2


class TestGetSimulatedForecast:
    """Tests for get_simulated_forecast function."""

    def test_returns_five_days(self):
        """Test returns 5-day forecast."""
        forecast = get_simulated_forecast("London")
        assert len(forecast) == 5

    def test_day_names(self):
        """Test forecast has correct day names."""
        forecast = get_simulated_forecast("London")
        days = [day["day"] for day in forecast]
        assert days == ["Today", "Tomorrow", "Day 3", "Day 4", "Day 5"]

    def test_each_day_has_fields(self):
        """Test each day has required fields."""
        forecast = get_simulated_forecast("Paris")
        for day in forecast:
            assert "day" in day
            assert "high" in day
            assert "low" in day
            assert "condition" in day

    def test_high_greater_than_low(self):
        """Test high temperature is greater than low."""
        forecast = get_simulated_forecast("Berlin")
        for day in forecast:
            assert day["high"] > day["low"]
            assert day["high"] - day["low"] == 10  # Offset is +5 and -5

    def test_deterministic(self):
        """Test same city returns same forecast."""
        forecast1 = get_simulated_forecast("Rome")
        forecast2 = get_simulated_forecast("Rome")
        assert forecast1 == forecast2


class TestGetSimulatedAlerts:
    """Tests for get_simulated_alerts function."""

    def test_returns_list(self):
        """Test returns a list."""
        alerts = get_simulated_alerts("California")
        assert isinstance(alerts, list)

    def test_alert_structure(self):
        """Test alerts have correct structure."""
        # Try multiple regions to get one with alerts
        for region in ["California", "Texas", "Florida", "Alaska", "Hawaii"]:
            alerts = get_simulated_alerts(region)
            if alerts:
                for alert in alerts:
                    assert "type" in alert
                    assert "severity" in alert
                    assert "message" in alert
                break

    def test_region_in_message(self):
        """Test region name appears in alert message."""
        for region in ["California", "Texas", "Florida", "Alaska", "Hawaii"]:
            alerts = get_simulated_alerts(region)
            if alerts:
                for alert in alerts:
                    assert region in alert["message"]
                break

    def test_deterministic(self):
        """Test same region returns same alerts."""
        alerts1 = get_simulated_alerts("Oregon")
        alerts2 = get_simulated_alerts("Oregon")
        assert alerts1 == alerts2

    def test_some_regions_have_no_alerts(self):
        """Test some regions have no alerts."""
        # Test many regions to find one with no alerts
        no_alerts_found = False
        for i in range(100):
            region = f"Region{i}"
            alerts = get_simulated_alerts(region)
            if not alerts:
                no_alerts_found = True
                break
        assert no_alerts_found


class TestAccessDenied:
    """Tests for access_denied function."""

    def test_returns_tool_result(self):
        """Test returns a ToolResult."""
        result = access_denied("mcp:read")
        assert hasattr(result, "content")
        assert hasattr(result, "is_error")

    def test_is_error_true(self):
        """Test is_error is True."""
        result = access_denied("mcp:read")
        assert result.is_error is True

    def test_content_has_error(self):
        """Test content contains error message."""
        result = access_denied("mcp:admin")
        assert len(result.content) == 1
        content = json.loads(result.content[0].text)
        assert content["error"] == "access_denied"
        assert "mcp:admin" in content["message"]

    def test_scope_in_message(self):
        """Test scope appears in error message."""
        result = access_denied("custom:scope")
        content = json.loads(result.content[0].text)
        assert "custom:scope" in content["message"]
