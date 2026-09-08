#!/bin/bash

# Run the Python SDK example for GopherAgent.create_with_url
# against the local checkout and locally built native libraries.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
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

NATIVE_LIBRARY_DIR="$PROJECT_DIR/native/${PLATFORM}-${ARCH}/lib"
if [ ! -d "$NATIVE_LIBRARY_DIR" ]; then
    NATIVE_LIBRARY_DIR="$PROJECT_DIR/native/lib"
fi
if [ ! -d "$NATIVE_LIBRARY_DIR" ]; then
    echo -e "${RED}Error: native library directory not found.${NC}"
    echo -e "${YELLOW}Expected $PROJECT_DIR/native/${PLATFORM}-${ARCH}/lib or $PROJECT_DIR/native/lib.${NC}"
    exit 1
fi

echo -e "${CYAN}SDK: local checkout at $PROJECT_DIR${NC}"
echo -e "${CYAN}Native library path: $NATIVE_LIBRARY_DIR${NC}"
echo -e "${CYAN}OAuth: ${GOPHER_MCP_OAUTH:-auto}${NC}"
echo ""
echo -e "${YELLOW}Running example...${NC}"
echo ""

cd "$PROJECT_DIR"
GOPHER_MCP_PYTHON_SDK_LABEL="local checkout at $PROJECT_DIR" \
GOPHER_ORCH_LIBRARY_PATH="$NATIVE_LIBRARY_DIR" \
DYLD_LIBRARY_PATH="$NATIVE_LIBRARY_DIR" \
LD_LIBRARY_PATH="$NATIVE_LIBRARY_DIR" \
PYTHONPATH="$PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
python3 examples/api/create_by_url.py "$@"

echo ""
echo -e "${GREEN}Example completed${NC}"
