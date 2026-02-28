#!/usr/bin/env python3
"""
Example using JSON server configuration.
"""

import json
import sys

from gopher_mcp_python import GopherAgent


# Server configuration for local MCP servers
SERVER_CONFIG = json.dumps({
    "succeeded": True,
    "code": 200000000,
    "message": "success",
    "data": {
        "servers": [
            {
                "version": "2025-01-09",
                "serverId": "1",
                "name": "server1",
                "transport": "http_sse",
                "config": {"url": "http://127.0.0.1:3001/mcp", "headers": {}},
                "connectTimeout": 5000,
                "requestTimeout": 30000,
            },
            {
                "version": "2025-01-09",
                "serverId": "2",
                "name": "server2",
                "transport": "http_sse",
                "config": {"url": "http://127.0.0.1:3002/mcp", "headers": {}},
                "connectTimeout": 5000,
                "requestTimeout": 30000,
            },
        ],
    },
})


def main():
    provider = "AnthropicProvider"
    model = "claude-3-haiku-20240307"

    try:
        # Create agent with JSON server configuration
        agent = GopherAgent.create_with_server_config(provider, model, SERVER_CONFIG)
        print("GopherAgent created!")

        # Get question from command line args or use default
        args = sys.argv[1:]
        question = " ".join(args) if args else "What is the weather like in New York?"
        print(f"Question: {question}")

        # Run the query
        answer = agent.run(question)
        print("Answer:")
        print(answer)

        # Cleanup
        agent.dispose()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
