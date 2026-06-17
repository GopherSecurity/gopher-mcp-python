#!/usr/bin/env python3
"""
SDK example for GopherAgent.create_with_server_name.

Python port of gopher-mcp-js/examples/api/create_by_server_name.ts,
which itself ports
gopher-orch/examples/sdk/api/create_by_server_name.cc.

Scopes a GopherAgent to a single MCP server in the caller's workspace
by human-readable name. Internally this hits the same GET
/v1/mcp-servers endpoint as create_with_api_key under the Bearer api
key, but adds the "?serverName={name}" routing query so the response
carries only the matching server entry. Use this when the api key
owns several MCP servers and the agent should bind to exactly one
identified by name rather than id.

Provider defaults to AnthropicProvider; the model is taken from
LLM_MODEL. Override either via env or by editing the constants in
main().

Configuration (env vars):
    GOPHER_API_KEY          Gopher API key for /v1/mcp-servers
    GOPHER_MCP_SERVER_NAME  MCP server name to scope the agent to
    LLM_PROVIDER            Optional. Defaults to "AnthropicProvider".
    LLM_MODEL               Required. Model identifier the provider accepts.
    DEBUG                   When set, ctypes prints library-resolution diagnostics.

Usage:
    python3 create_by_server_name.py                              # built-in query
    python3 create_by_server_name.py "query one" "query two" ...  # supplied queries
"""

import os
import sys
import traceback

from gopher_mcp_python import GopherAgent

API_KEY_PLACEHOLDER = "{YOUR_GOPHER_API_KEY}"
SERVER_NAME_PLACEHOLDER = "{YOUR_MCP_SERVER_NAME}"
MODEL_PLACEHOLDER = "{YOUR_LLM_MODEL}"


def env_or(name: str, fallback: str) -> str:
    """Return os.environ[name] if non-empty, otherwise fallback."""
    value = os.environ.get(name, "")
    return value if value else fallback


def main() -> None:
    print("=== GopherAgent.create_with_server_name example ===")
    print(f"Usage: python3 {sys.argv[0]} [query1] [query2] ...")
    print(
        "Env:   GOPHER_API_KEY GOPHER_MCP_SERVER_NAME LLM_PROVIDER LLM_MODEL DEBUG"
    )
    print("")

    queries = sys.argv[1:] if len(sys.argv) > 1 else ["What time is it in Tokyo?"]

    provider = env_or("LLM_PROVIDER", "AnthropicProvider")
    model = env_or("LLM_MODEL", MODEL_PLACEHOLDER)
    api_key = env_or("GOPHER_API_KEY", API_KEY_PLACEHOLDER)
    server_name = env_or("GOPHER_MCP_SERVER_NAME", SERVER_NAME_PLACEHOLDER)

    print(f"Provider:        {provider}")
    model_label = (
        f"{model}  (set LLM_MODEL)" if model == MODEL_PLACEHOLDER else model
    )
    print(f"Model:           {model_label}")
    api_key_label = (
        f"{api_key}  (set GOPHER_API_KEY)"
        if api_key == API_KEY_PLACEHOLDER
        else "<set via GOPHER_API_KEY>"
    )
    print(f"API key:         {api_key_label}")
    server_name_label = (
        f"{server_name}  (set GOPHER_MCP_SERVER_NAME)"
        if server_name == SERVER_NAME_PLACEHOLDER
        else server_name
    )
    print(f"MCP server name: {server_name_label}")
    print(f"Queries:         {len(queries)}")

    if (
        model == MODEL_PLACEHOLDER
        or api_key == API_KEY_PLACEHOLDER
        or server_name == SERVER_NAME_PLACEHOLDER
    ):
        print(
            "\nError: LLM_MODEL, GOPHER_API_KEY, and GOPHER_MCP_SERVER_NAME "
            "must all be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nCreating agent via GopherAgent.create_with_server_name...")
    agent = GopherAgent.create_with_server_name(
        provider, model, api_key, server_name
    )
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
