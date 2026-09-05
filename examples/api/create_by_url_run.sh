#!/bin/bash

# Run the Python SDK example for GopherAgent.create_with_url
# against the local gopher-mcp-python checkout.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORK_DIR="$SCRIPT_DIR/test-project-create-by-url"
LOCAL_NATIVE_LIBRARY_PATH="$REPO_ROOT/native/current/lib"

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

echo -e "${CYAN}SDK: installing local checkout $REPO_ROOT${NC}"
if [ -z "${GOPHER_ORCH_LIBRARY_PATH:-}" ] && [ -d "$LOCAL_NATIVE_LIBRARY_PATH" ]; then
    local_native_file="$(python3 - "$LOCAL_NATIVE_LIBRARY_PATH" <<'PY'
import pathlib
import re
import sys

lib_dir = pathlib.Path(sys.argv[1])
patterns = ("libgopher-orch.*.dylib", "libgopher-orch.so.*", "gopher-orch-*.dll")
matches = [path for pattern in patterns for path in lib_dir.glob(pattern) if path.is_file()]

def version_key(path):
    return tuple(int(part) for part in re.findall(r"\d+", path.name))

if matches:
    print(max(matches, key=version_key))
PY
)"
    export GOPHER_ORCH_LIBRARY_PATH="${local_native_file:-$LOCAL_NATIVE_LIBRARY_PATH}"
fi
echo -e "${CYAN}Native: ${GOPHER_ORCH_LIBRARY_PATH:-using package/default resolution}${NC}"
echo ""

echo -e "${YELLOW}Setting up test project at $WORK_DIR...${NC}"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

activate_script=""
venv_python=""
if [ -x "venv/bin/python" ] && [ -f "venv/bin/activate" ]; then
    activate_script="venv/bin/activate"
    venv_python="venv/bin/python"
elif [ -x "venv/Scripts/python.exe" ] && [ -f "venv/Scripts/activate" ]; then
    activate_script="venv/Scripts/activate"
    venv_python="venv/Scripts/python.exe"
fi
if [ -z "$activate_script" ]; then
    echo -e "${RED}Error: virtualenv creation did not produce a usable Python.${NC}"
    echo -e "${YELLOW}Install python3-venv and python3-pip, then rerun this script.${NC}"
    exit 1
fi
if ! "$venv_python" -m pip --version >/dev/null 2>&1; then
    echo -e "${RED}Error: pip is not available in this virtual environment.${NC}"
    echo -e "${YELLOW}Install python3-venv and python3-pip, then rerun this script.${NC}"
    exit 1
fi

# shellcheck disable=SC1090
source "$activate_script"

if [ ! -f ".sdk-install-path" ] || [ "$(cat .sdk-install-path)" != "$REPO_ROOT" ]; then
    echo -e "${YELLOW}Installing local gopher-mcp-python...${NC}"
    python -m pip install --quiet -e "$REPO_ROOT"
    printf '%s' "$REPO_ROOT" > .sdk-install-path
else
    echo -e "${GREEN}Local SDK already installed${NC}"
fi

echo -e "${CYAN}Installed packages:${NC}"
python -m pip list | grep -i gopher || true

cp "$SCRIPT_DIR/create_by_url.py" .

echo ""
echo -e "${YELLOW}Running example...${NC}"
echo ""
python create_by_url.py "$@"

echo ""
echo -e "${GREEN}Example completed${NC}"
