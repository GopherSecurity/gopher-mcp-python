#!/usr/bin/env python3
"""
SDK example for GopherAgent.create_with_url.

Python port of gopher-mcp-js/examples/api/create_by_url.ts, which
itself ports gopher-orch/examples/sdk/api/create_by_url.cc.

Builds a GopherAgent from a single MCP server URL, skipping the
remote /v1/mcp-servers fetch that create_with_api_key performs and
the inline JSON shape that create_with_server_config requires.
Internally the factory synthesises an http_sse server entry around
the URL and delegates to create_by_json. Use this for local
development or one-off endpoints where the operator already knows
the URL.

Provider defaults to AnthropicProvider; the model is taken from
LLM_MODEL. Override either via env or by editing the constants in
main().

Configuration (env vars):
    GOPHER_MCP_URL  Full URL of the MCP server (e.g. http://127.0.0.1:8080/mcp)
    LLM_PROVIDER    Optional. Defaults to "AnthropicProvider".
    LLM_MODEL       Required. Model identifier the provider accepts.
    DEBUG           When set, ctypes prints library-resolution diagnostics.

Usage:
    python3 create_by_url.py                              # built-in query
    python3 create_by_url.py "query one" "query two" ...  # supplied queries
"""

import os
import sys
import traceback

from gopher_mcp_python import GopherAgent

URL_PLACEHOLDER = "{YOUR_MCP_URL}"
MODEL_PLACEHOLDER = "{YOUR_LLM_MODEL}"


def env_or(name: str, fallback: str) -> str:
    """Return os.environ[name] if non-empty, otherwise fallback."""
    value = os.environ.get(name, "")
    return value if value else fallback


def main() -> None:
    print("=== GopherAgent.create_with_url example ===")
    print(f"Usage: python3 {sys.argv[0]} [query1] [query2] ...")
    print("Env:   GOPHER_MCP_URL LLM_PROVIDER LLM_MODEL DEBUG")
    print("")

    queries = sys.argv[1:] if len(sys.argv) > 1 else ["What time is it in Tokyo?"]

    provider = env_or("LLM_PROVIDER", "AnthropicProvider")
    model = env_or("LLM_MODEL", MODEL_PLACEHOLDER)
    url = env_or("GOPHER_MCP_URL", URL_PLACEHOLDER)

    print(f"Provider: {provider}")
    model_label = (
        f"{model}  (set LLM_MODEL)" if model == MODEL_PLACEHOLDER else model
    )
    print(f"Model:    {model_label}")
    url_label = (
        f"{url}  (set GOPHER_MCP_URL)" if url == URL_PLACEHOLDER else url
    )
    print(f"MCP URL:  {url_label}")
    print(f"Queries:  {len(queries)}")

    if model == MODEL_PLACEHOLDER or url == URL_PLACEHOLDER:
        print(
            "\nError: LLM_MODEL and GOPHER_MCP_URL must both be set.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nCreating agent via GopherAgent.create_with_url...")
    agent = GopherAgent.create_with_url(provider, model, url)
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
