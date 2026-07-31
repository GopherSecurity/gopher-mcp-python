#!/bin/bash

# Run the Python SDK example for GopherAgent.create_with_server_config
# against the PyPI-published gopher-mcp-python package.
#
# Set SDK_VERSION to pin to a specific release; otherwise the latest
# published version is installed.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=examples/api/_run_common.sh
source "$SCRIPT_DIR/_run_common.sh"

detect_platform
print_banner "GopherAgent.create_with_server_config example"

warn_if_empty "LLM_MODEL" "Set it with: export LLM_MODEL=<your-model-id>"
warn_if_empty "ANTHROPIC_API_KEY" "(Required for the default AnthropicProvider.)"

run_api_example "test-project-create-by-json" "create_by_json.py" "$@"
