#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

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
    echo -e "${CYAN}Detected platform: ${PLATFORM}-${ARCH}${NC}"
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
    local example_file="$1"
    shift

    "${PYTHON:-python3}" "$SCRIPT_DIR/_run_local.py" "$example_file" "$@"
}
