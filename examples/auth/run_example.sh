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

# Find Python 3.10+ (try versioned first, then generic python3)
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    if command -v python3 &> /dev/null; then
        PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
        if [ "$PY_MINOR" -ge 10 ]; then
            PYTHON="python3"
        fi
    fi
fi

if [ -z "$PYTHON" ]; then
    echo -e "${RED}Error: Python 3.10+ required${NC}"
    echo "Install with: brew install python@3.12"
    exit 1
fi

echo -e "Using: ${YELLOW}$($PYTHON --version)${NC}"

# Check dependencies
if ! $PYTHON -c "import mcp" 2>/dev/null; then
    echo -e "${YELLOW}Installing mcp SDK...${NC}"
    $PYTHON -m pip install "mcp>=1.0.0"
fi

if ! $PYTHON -c "import gopher_mcp_python" 2>/dev/null; then
    echo -e "${YELLOW}Installing gopher-mcp-python...${NC}"
    $PYTHON -m pip install -e "${SCRIPT_DIR}/../.."
fi

echo -e "${GREEN}Starting Auth MCP Server (Streamable HTTP)...${NC}"
echo -e "Configuration: ${YELLOW}server.config${NC}"
echo ""

# Run server
CONFIG="${1:-${SCRIPT_DIR}/server.config}"
exec $PYTHON -m py_auth_mcp_server "$CONFIG"
