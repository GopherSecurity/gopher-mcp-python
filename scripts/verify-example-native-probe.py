#!/usr/bin/env python3
"""Verify that the installed Python SDK can load the native gopher-orch library."""

import json
import sys

from gopher_mcp_python import AgentError, GopherAgent
from gopher_mcp_python.ffi.library import GopherOrchLibrary


def fail(message: str) -> None:
    print(f"[verify-native] error: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not GopherOrchLibrary.is_available():
        fail(GopherOrchLibrary.get_load_error_message())

    print("[verify-native] native library loaded")

    server_config = {
        "succeeded": True,
        "data": {
            "servers": [
                {
                    "version": "2026-01-11",
                    "serverId": "verify-native",
                    "name": "verify-native",
                    "transport": "http_sse",
                    "config": {
                        "url": "http://127.0.0.1:1/mcp",
                        "headers": {},
                    },
                    "connectTimeout": 1000,
                    "requestTimeout": 1000,
                }
            ]
        },
    }

    try:
        agent = GopherAgent.create_with_server_config(
            "AnthropicProvider",
            "verify-model",
            json.dumps(server_config),
        )
    except AgentError as exc:
        message = str(exc)
        if "Failed to load" in message or "Native library not available" in message:
            fail(message)
        print(f"[verify-native] native create path reached expected failure: {message}")
        return

    agent.dispose()
    print("[verify-native] native create path completed")


if __name__ == "__main__":
    main()
