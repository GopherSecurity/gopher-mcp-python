#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

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

print_banner() {
    local title="$1"
    local border
    border="$(printf '%*s' "${#title}" '' | tr ' ' '=')"
    echo -e "${GREEN}${border}${NC}"
    echo -e "${GREEN}${title}${NC}"
    echo -e "${GREEN}${border}${NC}"
    echo ""
}

warn_if_empty() {
    local name="$1"
    local guidance="$2"
    local note="${3:-}"
    if [ -z "${!name:-}" ]; then
        echo -e "${YELLOW}Warning: ${name} environment variable is not set${NC}"
        echo -e "${YELLOW}${guidance}${NC}"
        if [ -n "$note" ]; then
            echo -e "${YELLOW}${note}${NC}"
        fi
        echo ""
    fi
}

run_api_example() {
    local work_name="$1"
    local example_file="$2"
    shift 2

    local work_dir="$SCRIPT_DIR/$work_name"

    echo -e "${YELLOW}Setting up test project at $work_dir...${NC}"
    rm -rf "$work_dir"
    mkdir -p "$work_dir"
    cd "$work_dir"

    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv

    local activate_script=""
    if [ -x "venv/bin/python" ] && [ -f "venv/bin/activate" ]; then
        activate_script="venv/bin/activate"
    elif [ -x "venv/Scripts/python.exe" ] && [ -f "venv/Scripts/activate" ]; then
        activate_script="venv/Scripts/activate"
    fi
    if [ -z "$activate_script" ]; then
        echo -e "${RED}Error: virtualenv creation did not produce a usable Python.${NC}"
        echo -e "${YELLOW}Install python3-venv and python3-pip, then rerun this script.${NC}"
        exit 1
    fi

    # shellcheck disable=SC1090
    source "$activate_script"

    echo -e "${YELLOW}Installing gopher-mcp-python from PyPI...${NC}"
    if [ -n "$SDK_VERSION" ]; then
        echo -e "${CYAN}Installing version: $SDK_VERSION${NC}"
        python -m pip install --quiet "gopher-mcp-python==$SDK_VERSION" \
                                    "${NATIVE_PACKAGE}==$SDK_VERSION"
    else
        echo -e "${CYAN}Installing latest published version${NC}"
        python -m pip install --quiet gopher-mcp-python "$NATIVE_PACKAGE"
    fi

    echo -e "${CYAN}Installed packages:${NC}"
    python -m pip list | grep -i gopher || true

    cp "$SCRIPT_DIR/$example_file" .

    echo ""
    echo -e "${YELLOW}Running example...${NC}"
    echo ""
    python "$example_file" "$@"

    echo ""
    echo -e "${GREEN}Example completed${NC}"
}
