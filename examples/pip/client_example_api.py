#!/usr/bin/env python3
"""
Example using Gopher API key with pip-installed SDK.

This example shows how to use GopherAgent.create_with_api_key() when
the gopher-orch SDK is installed via pip. The API key is used to
fetch MCP server configurations from the Gopher API.
"""

import os
import sys

from gopher_orch import GopherAgent


def main():
    # Your Gopher API key - get one from https://gopher.security
    api_key = os.environ.get("GOPHER_API_KEY", "{YOUR_GOPHER_API_KEY}")
    provider = os.environ.get("LLM_PROVIDER", "AnthropicProvider")
    model = os.environ.get("LLM_MODEL", "claude-3-haiku-20240307")

    if api_key == "{YOUR_GOPHER_API_KEY}":
        print("Error: Please set GOPHER_API_KEY environment variable", file=sys.stderr)
        print("  export GOPHER_API_KEY=your_api_key_here", file=sys.stderr)
        sys.exit(1)

    print("=== Gopher Agent API Example (pip) ===")
    print("")

    try:
        # Create agent with API key - fetches server config from Gopher API
        print("Creating agent with API key...")
        print(f'  Calling create_with_api_key("{provider}", "{model}", "{api_key[:10]}...")')
        agent = GopherAgent.create_with_api_key(provider, model, api_key)
        print("GopherAgent created successfully!")
        print(f"  Agent handle: {'valid' if agent else 'null'}")
        print("")

        # Get question from command line args or use default
        args = sys.argv[1:]
        question = " ".join(args) if args else "List all my Gmail drafts."

        print(f"Question: {question}")
        print("")

        # Run the query
        print("Running query...")
        answer = agent.run(question)

        print("Answer:")
        print("--------------------------------")
        print(answer)
        print("--------------------------------")

        # Cleanup
        agent.dispose()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
