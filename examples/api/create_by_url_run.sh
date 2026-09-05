#!/bin/bash

# Run the Python SDK example for GopherAgent.create_with_url
# against the PyPI-published gopher-mcp-python package.
#
# Set SDK_VERSION to pin to a specific release; otherwise the latest
# published version is installed.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=examples/api/_run_common.sh
source "$SCRIPT_DIR/_run_common.sh"

detect_platform
print_banner "GopherAgent.create_with_url example"

warn_if_empty "GOPHER_MCP_URL" "Set it with: export GOPHER_MCP_URL=http://127.0.0.1:8080/mcp"
warn_if_empty "LLM_MODEL" "Set it with: export LLM_MODEL=<your-model-id>"
warn_if_empty "ANTHROPIC_API_KEY" "(Required for the default AnthropicProvider.)"

if [ -z "${GOPHER_ACCESS_TOKEN:-}" ] && [ "${GOPHER_MCP_OAUTH:-auto}" = "disabled" ]; then
    echo -e "${YELLOW}Warning: GOPHER_ACCESS_TOKEN is empty and GOPHER_MCP_OAUTH=disabled; protected MCP URLs may fail.${NC}"
fi

run_api_example "test-project-create-by-url" "create_by_url.py" "$@"
