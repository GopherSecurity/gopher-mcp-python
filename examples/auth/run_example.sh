#!/bin/bash

# Run the Auth MCP Server example
# Usage:
#   ./run_example.sh           # Run with auth enabled (requires OAuth config)
#   ./run_example.sh --no-auth # Run without auth (development mode)
#   ./run_example.sh --help    # Show help

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# Check for help flag
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Auth MCP Server Example"
    echo ""
    echo "Usage:"
    echo "  ./run_example.sh           Run using server.config settings"
    echo "  ./run_example.sh --no-auth Override config to disable auth"
    echo "  ./run_example.sh --help    Show this help"
    echo ""
    echo "Options:"
    echo "  --no-auth    Disable OAuth authentication (overrides server.config)"
    echo "  --host HOST  Bind to specific host (default: 0.0.0.0)"
    echo "  --port PORT  Listen on specific port (default: 3001)"
    echo ""
    echo "Configuration:"
    echo "  Edit server.config to configure OAuth settings (auth_disabled=true/false)"
    echo "  See server.config.example for all available options"
    echo ""
    echo "Test endpoints:"
    echo "  curl http://localhost:3001/health"
    echo "  curl -X POST http://localhost:3001/mcp \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}'"
    exit 0
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found${NC}"
    exit 1
fi

# Check if dependencies are installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip3 install -r requirements.txt --quiet 2>/dev/null || pip3 install -r requirements.txt
fi

# Ensure PYTHONPATH includes the parent gopher-mcp-python package
PARENT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
export PYTHONPATH="${PARENT_DIR}:${PYTHONPATH}"

# Copy native library to lib/ if not present
LIB_DIR="${SCRIPT_DIR}/lib"
mkdir -p "${LIB_DIR}"

NATIVE_LIB="${PARENT_DIR}/native/lib"
if [ -d "${NATIVE_LIB}" ]; then
    # macOS
    if [ -f "${NATIVE_LIB}/libgopher-orch.dylib" ] && [ ! -f "${LIB_DIR}/libgopher-orch.dylib" ]; then
        echo -e "${YELLOW}Copying native library to lib/...${NC}"
        cp -P "${NATIVE_LIB}"/libgopher-orch*.dylib "${LIB_DIR}/" 2>/dev/null || true
    fi
    # Linux
    if [ -f "${NATIVE_LIB}/libgopher-orch.so" ] && [ ! -f "${LIB_DIR}/libgopher-orch.so" ]; then
        echo -e "${YELLOW}Copying native library to lib/...${NC}"
        cp -P "${NATIVE_LIB}"/libgopher-orch*.so* "${LIB_DIR}/" 2>/dev/null || true
    fi
fi

echo -e "${GREEN}Starting Auth MCP Server...${NC}"
echo -e "Configuration: ${YELLOW}server.config${NC}"
echo ""

# Run server with arguments (uses server.config by default)
exec python3 -m py_auth_mcp_server "$@"
