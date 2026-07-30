#!/usr/bin/env python3
"""
SDK example for GopherAgent.create_with_url with dynamic MCP headers.

Python port of gopher-mcp-js/examples/header/create_by_url.ts, which
itself ports gopher-orch/examples/sdk/header/access_token_create_by_url.cc.

Shows the runtime options object:

    GopherAgent.create_with_url(
        provider,
        model,
        mcp_url,
        runtime_options={"access_token": user_access_token},
    )

or:

    GopherAgent.create_with_url(
        provider,
        model,
        mcp_url,
        runtime_options={"headers": {"x-trace-id": "..."}},
    )

access_token is a convenience alias for Authorization: Bearer <token>
on MCP runtime traffic only. Explicit headers["Authorization"] takes
precedence on the native side.
"""

import os
import sys
import traceback

from gopher_mcp_python import GopherAgent


def env_or(name: str, fallback: str) -> str:
    """Return os.environ[name] if non-empty, otherwise fallback."""
    value = os.environ.get(name, "")
    return value if value else fallback


def queries_from_args() -> list[str]:
    """Return command-line queries or a default query."""
    return sys.argv[1:] if len(sys.argv) > 1 else ["What is the weather in Tokyo?"]


def runtime_options_from_env() -> dict[str, object]:
    """
    Build dynamic MCP runtime options for the example.

    Set GOPHER_HEADER_MODE=headers to demonstrate the headers-only form.
    The default token mode demonstrates the access_token convenience form.
    """
    mode = env_or("GOPHER_HEADER_MODE", "token")
    access_token = env_or("GOPHER_ACCESS_TOKEN", "")
    trace_id = env_or("GOPHER_TRACE_ID", "python-header-create-by-url")

    if mode == "headers":
        headers = {
            "x-gopher-example": "header-create-by-url",
            "x-trace-id": trace_id,
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return {"headers": headers}

    options: dict[str, object] = {
        "headers": {
            "x-gopher-example": "header-create-by-url",
            "x-trace-id": trace_id,
        },
    }
    if access_token:
        options["access_token"] = access_token
    return options


def main() -> None:
    print("=== GopherAgent.create_with_url dynamic header example ===")
    print(f"Usage: python3 {sys.argv[0]} [query1] [query2] ...")
    print(
        "Env:   GOPHER_MCP_URL GOPHER_ACCESS_TOKEN GOPHER_HEADER_MODE "
        "GOPHER_TRACE_ID LLM_PROVIDER LLM_MODEL"
    )
    print("")

    provider = env_or("LLM_PROVIDER", "AnthropicProvider")
    model = env_or("LLM_MODEL", "{YOUR_LLM_MODEL}")
    mcp_url = env_or("GOPHER_MCP_URL", "http://127.0.0.1:5001/mcp")
    access_token = env_or("GOPHER_ACCESS_TOKEN", "")
    queries = queries_from_args()
    runtime_options = runtime_options_from_env()

    print(f"Provider:     {provider}")
    model_label = f"{model}  (set LLM_MODEL)" if model == "{YOUR_LLM_MODEL}" else model
    print(f"Model:        {model_label}")
    print(f"MCP URL:      {mcp_url}")
    token_label = (
        "<empty; set GOPHER_ACCESS_TOKEN for protected MCP>"
        if not access_token
        else "<set via GOPHER_ACCESS_TOKEN>"
    )
    print(f"Access token: {token_label}")
    print(f"Header mode:  {env_or('GOPHER_HEADER_MODE', 'token')}")
    print(f"Queries:      {len(queries)}")

    if model == "{YOUR_LLM_MODEL}":
        print("\nError: LLM_MODEL must be set.", file=sys.stderr)
        sys.exit(1)

    print("\nCreating agent via GopherAgent.create_with_url(..., runtime_options=...)")
    agent = GopherAgent.create_with_url(
        provider,
        model,
        mcp_url,
        runtime_options=runtime_options,
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
        traceback.print_exc()
        sys.exit(1)
