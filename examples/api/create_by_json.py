#!/usr/bin/env python3
"""
SDK example for GopherAgent.create_with_server_config.

Python port of gopher-mcp-js/examples/api/create_by_json.ts, which
itself ports gopher-orch/examples/sdk/api/create_by_json.cc.

Builds a GopherAgent from an inline server JSON document, skipping the
remote /v1/mcp-servers fetch that create_with_api_key performs. Useful
when the caller already knows which MCP servers to bind to and wants
to skip the round-trip; the inline payload follows the
{ succeeded, code, message, data: { servers: [...] } } shape that
ConfigLoader on the C++ side accepts.

Provider defaults to AnthropicProvider; the model is taken from
LLM_MODEL. Edit SERVER_CONFIG below to point at your own MCP servers.

Configuration (env vars):
    LLM_PROVIDER  Optional. Defaults to "AnthropicProvider".
    LLM_MODEL     Required. Model identifier the provider accepts.
    DEBUG         When set, ctypes prints library-resolution diagnostics.

Usage:
    python3 create_by_json.py                              # built-in query
    python3 create_by_json.py "query one" "query two" ...  # supplied queries
"""

import json
import os
import sys
import traceback

from gopher_mcp_python import GopherAgent

MODEL_PLACEHOLDER = "{YOUR_LLM_MODEL}"
MISSING_ENV_MARKER = "ERROR: missing-required-env: LLM_MODEL"

SERVER_CONFIG = json.dumps(
    {
        "succeeded": True,
        "code": 200000000,
        "message": "success",
        "data": {
            "servers": [
                {
                    "version": "2025-01-09",
                    "serverId": "1877234567890123456",
                    "name": "gopher-auth-server",
                    "transport": "http_sse",
                    "config": {
                        "url": "http://127.0.0.1:3001/rpc",
                        "headers": {},
                    },
                    "connectTimeout": 5000,
                    "requestTimeout": 30000,
                }
            ]
        },
    }
)


def env_or(name: str, fallback: str) -> str:
    """Return os.environ[name] if non-empty, otherwise fallback."""
    value = os.environ.get(name, "")
    return value if value else fallback


def main() -> None:
    print("=== GopherAgent.create_with_server_config example ===")
    print(f"Usage: python3 {sys.argv[0]} [query1] [query2] ...")
    print("Env:   LLM_PROVIDER LLM_MODEL DEBUG")
    print("")

    queries = sys.argv[1:] if len(sys.argv) > 1 else ["What time is it in Tokyo?"]

    provider = env_or("LLM_PROVIDER", "AnthropicProvider")
    model = env_or("LLM_MODEL", MODEL_PLACEHOLDER)

    print(f"Provider: {provider}")
    model_label = f"{model}  (set LLM_MODEL)" if model == MODEL_PLACEHOLDER else model
    print(f"Model:    {model_label}")
    print(f"Queries:  {len(queries)}")

    if model == MODEL_PLACEHOLDER:
        print(MISSING_ENV_MARKER, file=sys.stderr)
        print("\nError: LLM_MODEL must be set.", file=sys.stderr)
        sys.exit(1)

    print("\nCreating agent via GopherAgent.create_with_server_config...")
    agent = GopherAgent.create_with_server_config(provider, model, SERVER_CONFIG)
    print("Agent created successfully!")

    try:
        for i, query in enumerate(queries):
            print(f"\nQuery {i + 1}: {query}")
            answer = agent.run(query)
            print(f"\nAgent Response {i + 1}:")
            print("--------------------------------")
            print(answer)
            print("--------------------------------")
    finally:
        agent.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
