#!/bin/bash

# Run the Python SDK example for GopherAgent.create_with_api_key against
# the PyPI-published gopher-mcp-python package. Bootstraps a fresh venv,
# installs the SDK plus the matching platform native package from PyPI,
# then runs the example.
#
# Set SDK_VERSION to pin to a specific release (e.g. SDK_VERSION=0.1.21);
# otherwise the latest published version is installed.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$SCRIPT_DIR/test-project-create-by-api-key"
SDK_VERSION="${SDK_VERSION:-}"

detect_platform() {
    local os arch
    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    arch=$(uname -m)
    case "$os" in
        darwin) PLATFORM="darwin" ;;
        linux) PLATFORM="linux" ;;
        mingw*|msys*|cygwin*) PLATFORM="win32" ;;
        *) echo -e "${RED}Unsupported OS: $os${NC}"; exit 1 ;;
    esac
    case "$arch" in
        x86_64|amd64) ARCH="x64" ;;
        arm64|aarch64) ARCH="arm64" ;;
        *) echo -e "${RED}Unsupported architecture: $arch${NC}"; exit 1 ;;
    esac
    NATIVE_PACKAGE="gopher-mcp-python-native-${PLATFORM}-${ARCH}"
    echo -e "${CYAN}Detected platform: ${PLATFORM}-${ARCH}${NC}"
    echo -e "${CYAN}Native package:    ${NATIVE_PACKAGE}${NC}"
}

detect_platform

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}GopherAgent.create_with_api_key example${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

if [ -z "$GOPHER_API_KEY" ]; then
    echo -e "${YELLOW}Warning: GOPHER_API_KEY environment variable is not set${NC}"
    echo -e "${YELLOW}Set it with: export GOPHER_API_KEY=your_api_key${NC}"
    echo ""
fi

if [ -z "$LLM_MODEL" ]; then
    echo -e "${YELLOW}Warning: LLM_MODEL environment variable is not set${NC}"
    echo -e "${YELLOW}Set it with: export LLM_MODEL=<your-model-id>${NC}"
    echo ""
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}Warning: ANTHROPIC_API_KEY environment variable is not set${NC}"
    echo -e "${YELLOW}(Required for the default AnthropicProvider.)${NC}"
    echo ""
fi

echo -e "${YELLOW}Setting up test project at $WORK_DIR...${NC}"
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

echo -e "${YELLOW}Installing gopher-mcp-python from PyPI...${NC}"
if [ -n "$SDK_VERSION" ]; then
    echo -e "${CYAN}Installing version: $SDK_VERSION${NC}"
    pip install --quiet "gopher-mcp-python==$SDK_VERSION" \
                        "${NATIVE_PACKAGE}==$SDK_VERSION"
else
    echo -e "${CYAN}Installing latest published version${NC}"
    pip install --quiet gopher-mcp-python "$NATIVE_PACKAGE"
fi

echo -e "${CYAN}Installed packages:${NC}"
pip list | grep -i gopher || true

cp "$SCRIPT_DIR/create_by_api_key.py" .

echo ""
echo -e "${YELLOW}Running example...${NC}"
echo ""
python create_by_api_key.py "$@"

echo ""
echo -e "${GREEN}Example completed${NC}"

exit 0
