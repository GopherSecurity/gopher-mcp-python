#!/usr/bin/env python3
"""
SDK example for GopherAgent.create_with_gateway_id.

Python port of gopher-mcp-js/examples/api/create_by_gateway_id.ts,
which itself ports
gopher-orch/examples/sdk/api/create_by_gateway_id.cc.

Scopes a GopherAgent to a single MCP gateway in the caller's
workspace. Internally this hits the same GET /v1/mcp-servers endpoint
as create_with_api_key under the Bearer api key, but adds the
"?gatewayId={id}" routing query so the response carries the backing
MCP servers for that gateway. Use this when the api key owns several
gateways and the agent should bind to exactly one.

Provider defaults to AnthropicProvider and the model is taken from
LLM_MODEL so the example stays runnable against any Anthropic-served
model without hardcoding a specific identifier in source. Override
either via env or by editing the constants in main().

Configuration (env vars):
    GOPHER_API_KEY         Gopher API key for /v1/mcp-servers
    GOPHER_MCP_GATEWAY_ID  MCP gateway id to scope the agent to
    LLM_PROVIDER           Optional. Defaults to "AnthropicProvider".
    LLM_MODEL              Required. Model identifier the provider accepts.
    DEBUG                  When set, ctypes prints library-resolution diagnostics.

Usage:
    python3 create_by_gateway_id.py                              # built-in query
    python3 create_by_gateway_id.py "query one" "query two" ...  # supplied queries
"""

import os
import sys
import traceback

from gopher_mcp_python import GopherAgent

API_KEY_PLACEHOLDER = "{YOUR_GOPHER_API_KEY}"
GATEWAY_ID_PLACEHOLDER = "{YOUR_MCP_GATEWAY_ID}"
MODEL_PLACEHOLDER = "{YOUR_LLM_MODEL}"
MISSING_ENV_MARKER = (
    "ERROR: missing-required-env: GOPHER_API_KEY,GOPHER_MCP_GATEWAY_ID,LLM_MODEL"
)


def env_or(name: str, fallback: str) -> str:
    """Return os.environ[name] if non-empty, otherwise fallback."""
    value = os.environ.get(name, "")
    return value if value else fallback


def main() -> None:
    print("=== GopherAgent.create_with_gateway_id example ===")
    print(f"Usage: python3 {sys.argv[0]} [query1] [query2] ...")
    print("Env:   GOPHER_API_KEY GOPHER_MCP_GATEWAY_ID LLM_PROVIDER LLM_MODEL DEBUG")
    print("")

    queries = sys.argv[1:] if len(sys.argv) > 1 else ["What time is it in Tokyo?"]

    provider = env_or("LLM_PROVIDER", "AnthropicProvider")
    model = env_or("LLM_MODEL", MODEL_PLACEHOLDER)
    api_key = env_or("GOPHER_API_KEY", API_KEY_PLACEHOLDER)
    gateway_id = env_or("GOPHER_MCP_GATEWAY_ID", GATEWAY_ID_PLACEHOLDER)

    print(f"Provider:       {provider}")
    model_label = f"{model}  (set LLM_MODEL)" if model == MODEL_PLACEHOLDER else model
    print(f"Model:          {model_label}")
    api_key_label = (
        f"{api_key}  (set GOPHER_API_KEY)"
        if api_key == API_KEY_PLACEHOLDER
        else "<set via GOPHER_API_KEY>"
    )
    print(f"API key:        {api_key_label}")
    gateway_id_label = (
        f"{gateway_id}  (set GOPHER_MCP_GATEWAY_ID)"
        if gateway_id == GATEWAY_ID_PLACEHOLDER
        else gateway_id
    )
    print(f"MCP gateway id: {gateway_id_label}")
    print(f"Queries:        {len(queries)}")

    if (
        model == MODEL_PLACEHOLDER
        or api_key == API_KEY_PLACEHOLDER
        or gateway_id == GATEWAY_ID_PLACEHOLDER
    ):
        print(MISSING_ENV_MARKER, file=sys.stderr)
        print(
            "\nError: LLM_MODEL, GOPHER_API_KEY, and GOPHER_MCP_GATEWAY_ID "
            "must all be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nCreating agent via GopherAgent.create_with_gateway_id...")
    agent = GopherAgent.create_with_gateway_id(provider, model, api_key, gateway_id)
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
