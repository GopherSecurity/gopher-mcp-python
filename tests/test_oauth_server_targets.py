"""Tests for OAuth MCP server target extraction."""

import json

import pytest

from gopher_mcp_python.oauth_server_targets import extract_mcp_server_targets


def test_extracts_direct_url() -> None:
    assert extract_mcp_server_targets(url="https://mcp.example.com/mcp") == [
        {"url": "https://mcp.example.com/mcp"}
    ]


def test_extracts_nested_config_url_with_identity_metadata() -> None:
    config = json.dumps(
        {
            "data": {
                "servers": [
                    {
                        "serverId": "srv-1",
                        "name": "weather",
                        "serverName": "weather-tools",
                        "transport": "http_sse",
                        "config": {"url": "https://mcp.example.com/mcp"},
                    }
                ]
            }
        }
    )

    assert extract_mcp_server_targets(server_config=config) == [
        {
            "server_id": "srv-1",
            "name": "weather",
            "server_name": "weather-tools",
            "url": "https://mcp.example.com/mcp",
        }
    ]


def test_ignores_stdio_and_missing_url() -> None:
    config = json.dumps(
        {
            "servers": [
                {"transport": "stdio", "config": {"url": "ignored"}},
                {"transport": "http_sse", "config": {}},
            ]
        }
    )

    assert extract_mcp_server_targets(server_config=config) == []


def test_malformed_json_has_useful_error() -> None:
    with pytest.raises(ValueError, match="Failed to parse MCP server config"):
        extract_mcp_server_targets(server_config="{")
