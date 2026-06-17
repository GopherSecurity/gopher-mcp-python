#!/usr/bin/env python3
"""
SDK example for GopherAgent.create_with_api_key.

Python port of gopher-mcp-js/examples/api/create_by_api_key.ts, which
itself ports gopher-orch/examples/sdk/api/create_by_api_key.cc.

Uses a Gopher API key to fetch the caller's full MCP server inventory
via GET /v1/mcp-servers; the agent gets every server the api key owns
with no extra routing. Smallest of the seven create_by_* examples and
a good first sanity check that the toolchain (pip install -e ., the
right native lib, env vars) is wired correctly.

Provider defaults to AnthropicProvider; the model is taken from
LLM_MODEL. Override either via env or by editing the constants in
main().

Configuration (env vars):
    GOPHER_API_KEY  Gopher API key for /v1/mcp-servers
    LLM_PROVIDER    Optional. Defaults to "AnthropicProvider".
    LLM_MODEL       Required. Model identifier the provider accepts.
    DEBUG           When set, ctypes prints library-resolution diagnostics.

Usage:
    python3 create_by_api_key.py                              # built-in query
    python3 create_by_api_key.py "query one" "query two" ...  # supplied queries
"""

import os
import sys
import traceback

from gopher_mcp_python import GopherAgent

API_KEY_PLACEHOLDER = "{YOUR_GOPHER_API_KEY}"
MODEL_PLACEHOLDER = "{YOUR_LLM_MODEL}"


def env_or(name: str, fallback: str) -> str:
    """Return os.environ[name] if non-empty, otherwise fallback."""
    value = os.environ.get(name, "")
    return value if value else fallback


def main() -> None:
    print("=== GopherAgent.create_with_api_key example ===")
    print(f"Usage: python3 {sys.argv[0]} [query1] [query2] ...")
    print("Env:   GOPHER_API_KEY LLM_PROVIDER LLM_MODEL DEBUG")
    print("")

    queries = sys.argv[1:] if len(sys.argv) > 1 else ["What time is it in Tokyo?"]

    provider = env_or("LLM_PROVIDER", "AnthropicProvider")
    model = env_or("LLM_MODEL", MODEL_PLACEHOLDER)
    api_key = env_or("GOPHER_API_KEY", API_KEY_PLACEHOLDER)

    print(f"Provider: {provider}")
    model_label = (
        f"{model}  (set LLM_MODEL)" if model == MODEL_PLACEHOLDER else model
    )
    print(f"Model:    {model_label}")
    api_key_label = (
        f"{api_key}  (set GOPHER_API_KEY)"
        if api_key == API_KEY_PLACEHOLDER
        else "<set via GOPHER_API_KEY>"
    )
    print(f"API key:  {api_key_label}")
    print(f"Queries:  {len(queries)}")

    if model == MODEL_PLACEHOLDER or api_key == API_KEY_PLACEHOLDER:
        print(
            "\nError: LLM_MODEL and GOPHER_API_KEY must both be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nCreating agent via GopherAgent.create_with_api_key...")
    agent = GopherAgent.create_with_api_key(provider, model, api_key)
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
