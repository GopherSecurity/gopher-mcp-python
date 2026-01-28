#!/usr/bin/env python3
"""
Simple MCP Server (No Authentication) - Weather Tools
"""

import os
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

from tools.get_weather import get_weather
from tools.get_forecast import get_forecast
from tools.get_alerts import get_alerts


SERVER_PORT = int(os.environ.get("SERVER_PORT", "3001"))
SERVER_URL = os.environ.get("SERVER_URL", f"http://127.0.0.1:{SERVER_PORT}")
SERVER_NAME = os.environ.get("SERVER_NAME", "mcp-server-3001")
SERVER_VERSION = os.environ.get("SERVER_VERSION", "1.0.0")

TOOLS = [
    {
        "name": "get-weather",
        "description": "Get current weather for a city",
        "inputSchema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
    {
        "name": "get-forecast",
        "description": "Get weather forecast for a city",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "days": {
                    "type": "number",
                    "description": "Days (1-7)",
                    "minimum": 1,
                    "maximum": 7,
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "get-weather-alerts",
        "description": "Get weather alerts for a region",
        "inputSchema": {
            "type": "object",
            "properties": {"region": {"type": "string", "description": "Region name"}},
            "required": ["region"],
        },
    },
]


app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


@app.route("/mcp", methods=["GET", "POST"])
def mcp():
    body = request.get_json() or {}
    method = body.get("method")
    params = body.get("params")
    id_ = body.get("id")

    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": params.get("protocolVersion", "2024-11-05")
                if params
                else "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
            "id": id_,
        }
    elif method == "tools/list":
        response = {"jsonrpc": "2.0", "result": {"tools": TOOLS}, "id": id_}
    elif method == "tools/call":
        try:
            tool_name = params.get("name") if params else None
            handlers = {
                "get-weather": get_weather,
                "get-forecast": get_forecast,
                "get-weather-alerts": get_alerts,
            }

            handler = handlers.get(tool_name)
            if handler:
                result = handler(body)
            else:
                result = {
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                    "isError": True,
                }
            response = {"jsonrpc": "2.0", "result": result, "id": id_}
        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": id_,
            }
    else:
        response = {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": id_,
        }

    return jsonify(response)


if __name__ == "__main__":
    print(f"MCP Server running at {SERVER_URL}")
    print(f"  POST {SERVER_URL}/mcp")
    print(f"  GET  {SERVER_URL}/health")
    app.run(host="127.0.0.1", port=SERVER_PORT, debug=False)
