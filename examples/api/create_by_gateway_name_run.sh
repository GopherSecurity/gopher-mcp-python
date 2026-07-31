#!/bin/bash

# Run the Python SDK example for GopherAgent.create_with_gateway_name
# against the PyPI-published gopher-mcp-python package.
#
# Set SDK_VERSION to pin to a specific release; otherwise the latest
# published version is installed. The routing factories require a
# release that includes the native routing factory symbols.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=examples/api/_run_common.sh
source "$SCRIPT_DIR/_run_common.sh"

detect_platform
print_banner "GopherAgent.create_with_gateway_name example"

warn_if_empty "GOPHER_API_KEY" "Set it with: export GOPHER_API_KEY=your_api_key"
warn_if_empty "GOPHER_MCP_GATEWAY_NAME" "Set it with: export GOPHER_MCP_GATEWAY_NAME=my-gateway"
warn_if_empty "LLM_MODEL" "Set it with: export LLM_MODEL=<your-model-id>"
warn_if_empty "ANTHROPIC_API_KEY" "(Required for the default AnthropicProvider.)"

run_api_example "test-project-create-by-gateway-name" "create_by_gateway_name.py" "$@"
