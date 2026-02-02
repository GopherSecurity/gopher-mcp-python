#!/bin/bash

# Run the Python client example using pip-installed SDK
# This demonstrates how to use gopher-orch when installed via pip

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$EXAMPLES_DIR")"
WORK_DIR="$SCRIPT_DIR/test-project"

# SDK version to install (can be overridden via environment variable)
SDK_VERSION="${SDK_VERSION:-}"

# Detect platform and architecture
detect_platform() {
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)

    # Map OS
    case "$os" in
        darwin) PLATFORM="darwin" ;;
        linux) PLATFORM="linux" ;;
        mingw*|msys*|cygwin*) PLATFORM="win32" ;;
        *) echo -e "${RED}Unsupported OS: $os${NC}"; exit 1 ;;
    esac

    # Map architecture
    case "$arch" in
        x86_64|amd64) ARCH="x64" ;;
        arm64|aarch64) ARCH="arm64" ;;
        *) echo -e "${RED}Unsupported architecture: $arch${NC}"; exit 1 ;;
    esac

    NATIVE_PACKAGE="gopher-orch-native-${PLATFORM}-${ARCH}"
    echo -e "${CYAN}Detected platform: ${PLATFORM}-${ARCH}${NC}"
    echo -e "${CYAN}Native package: ${NATIVE_PACKAGE}${NC}"
}

detect_platform

# Kill any existing processes on ports 3001 and 3002
kill_port() {
    local port=$1
    local pids=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}Killing existing process on port $port${NC}"
        echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
}

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    kill_port 3001
    kill_port 3002
    # Deactivate virtual environment if active
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate 2>/dev/null || true
    fi
    echo -e "${GREEN}Done${NC}"
}

trap cleanup EXIT

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Running pip SDK Example${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Create test project directory
echo -e "${YELLOW}Setting up test project...${NC}"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Install SDK and native package from TestPyPI
echo -e "${YELLOW}Installing gopher-orch from TestPyPI...${NC}"
if [ -n "$SDK_VERSION" ]; then
    echo -e "${CYAN}Installing version: $SDK_VERSION${NC}"
    pip install --index-url https://test.pypi.org/simple/ \
                --extra-index-url https://pypi.org/simple/ \
                "gopher-orch==$SDK_VERSION" \
                "${NATIVE_PACKAGE}==$SDK_VERSION"
else
    echo -e "${CYAN}Installing latest version${NC}"
    pip install --index-url https://test.pypi.org/simple/ \
                --extra-index-url https://pypi.org/simple/ \
                gopher-orch \
                "$NATIVE_PACKAGE"
fi

# Show installed version
echo -e "${CYAN}Installed packages:${NC}"
pip list | grep -i gopher

# Copy the example Python file
cp "$SCRIPT_DIR/client_example_json.py" .

# Kill any existing processes on ports
kill_port 3001
kill_port 3002

# Start server3001
echo -e "${YELLOW}Starting server3001...${NC}"
cd "$EXAMPLES_DIR/server3001"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for server3001...${NC}"
    npm install
fi
npm run dev > /dev/null 2>&1 &
SERVER3001_PID=$!
echo -e "${GREEN}server3001 started (PID: $SERVER3001_PID)${NC}"

# Start server3002
echo -e "${YELLOW}Starting server3002...${NC}"
cd "$EXAMPLES_DIR/server3002"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies for server3002...${NC}"
    npm install
fi
npm run dev > /dev/null 2>&1 &
SERVER3002_PID=$!
echo -e "${GREEN}server3002 started (PID: $SERVER3002_PID)${NC}"

# Wait for servers to start
echo -e "${YELLOW}Waiting for servers to start...${NC}"
sleep 3

# Run the Python client
echo ""
echo -e "${YELLOW}Running Python client...${NC}"
echo ""
cd "$WORK_DIR"

# Run with Python
python client_example_json.py "$@"

echo ""
echo -e "${GREEN}Example completed${NC}"
echo ""
echo -e "${CYAN}To run this example manually:${NC}"
echo "  1. python3 -m venv venv && source venv/bin/activate"
echo "  2. pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ gopher-orch $NATIVE_PACKAGE"
echo "  3. python client_example_json.py"

exit 0
