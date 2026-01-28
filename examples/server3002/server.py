#!/usr/bin/env python3
"""
Simple MCP Server (No Authentication) - Utility Tools
"""

import os
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

from tools.get_time import get_time
from tools.generate_password import generate_password


SERVER_PORT = int(os.environ.get("SERVER_PORT", "3002"))
SERVER_URL = os.environ.get("SERVER_URL", f"http://127.0.0.1:{SERVER_PORT}")
SERVER_NAME = os.environ.get("SERVER_NAME", "mcp-server-3002")
SERVER_VERSION = os.environ.get("SERVER_VERSION", "1.0.0")

TOOLS = [
    {
        "name": "get-time",
        "description": "Get current time for a timezone or city",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": 'Timezone (e.g., "UTC", "America/New_York") or city name',
                },
            },
            "required": ["location"],
        },
    },
    {
        "name": "generate-password",
        "description": "Generate a secure password",
        "inputSchema": {
            "type": "object",
            "properties": {
                "length": {
                    "type": "number",
                    "description": "Length (8-128)",
                    "minimum": 8,
                    "maximum": 128,
                },
                "includeUppercase": {"type": "boolean", "description": "Include A-Z"},
                "includeLowercase": {"type": "boolean", "description": "Include a-z"},
                "includeNumbers": {"type": "boolean", "description": "Include 0-9"},
                "includeSymbols": {"type": "boolean", "description": "Include symbols"},
            },
            "required": [],
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
                "get-time": get_time,
                "generate-password": generate_password,
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
