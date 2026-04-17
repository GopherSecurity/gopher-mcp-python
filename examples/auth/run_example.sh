#!/bin/bash

# Run the Auth MCP Server example
# Usage:
#   ./run_example.sh                    # Run using server.config
#   ./run_example.sh /path/to/config    # Run with custom config

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Python Auth MCP Server (FastMCP + Streamable HTTP)"
    echo ""
    echo "Usage:"
    echo "  ./run_example.sh                 Run using server.config"
    echo "  ./run_example.sh /path/config    Run with custom config"
    echo ""
    echo "Requires: Python 3.10+, mcp>=1.0.0, gopher-mcp-python"
    exit 0
fi

# Check Python 3.10+
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found${NC}"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PY_VERSION" -lt 10 ]; then
    echo -e "${RED}Error: Python 3.10+ required (found 3.${PY_VERSION})${NC}"
    exit 1
fi

# Check dependencies
if ! python3 -c "import mcp" 2>/dev/null; then
    echo -e "${YELLOW}Installing mcp SDK...${NC}"
    pip3 install "mcp>=1.0.0"
fi

if ! python3 -c "import gopher_mcp_python" 2>/dev/null; then
    echo -e "${YELLOW}Installing gopher-mcp-python...${NC}"
    pip3 install gopher-mcp-python
fi

echo -e "${GREEN}Starting Auth MCP Server (Streamable HTTP)...${NC}"
echo -e "Configuration: ${YELLOW}server.config${NC}"
echo ""

# Run server
CONFIG="${1:-${SCRIPT_DIR}/server.config}"
exec python3 -m py_auth_mcp_server "$CONFIG"
