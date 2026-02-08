#!/bin/bash

# Run the Python client example using API key with pip-installed SDK
# This demonstrates how to use GopherAgent.create_with_api_key() when installed via pip

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
WORK_DIR="$SCRIPT_DIR/test-project-api"

# SDK version to install (can be overridden via environment variable)
# Note: gopher-orch now uses non-self-contained builds with separate dependency libraries
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

# Check for GOPHER_API_KEY
if [ -z "$GOPHER_API_KEY" ]; then
    echo -e "${RED}Error: GOPHER_API_KEY environment variable is not set${NC}"
    echo ""
    echo "Please set your Gopher API key:"
    echo "  export GOPHER_API_KEY=your_api_key_here"
    echo ""
    echo "Get an API key from https://gopher.security"
    exit 1
fi

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Running pip SDK API Key Example${NC}"
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
cp "$SCRIPT_DIR/client_example_api.py" .

# Run the Python client
echo ""
echo -e "${YELLOW}Running Python client with API key...${NC}"
echo ""

# Run with Python
python client_example_api.py "$@"

echo ""
echo -e "${GREEN}Example completed${NC}"
echo ""
echo -e "${CYAN}To run this example manually:${NC}"
echo "  1. export GOPHER_API_KEY=your_api_key_here"
echo "  2. python3 -m venv venv && source venv/bin/activate"
echo "  3. pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ gopher-orch $NATIVE_PACKAGE"
echo "  4. python client_example_api.py"

exit 0
