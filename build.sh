#!/bin/bash

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NATIVE_DIR="${SCRIPT_DIR}/third_party/gopher-orch"
BUILD_DIR="${NATIVE_DIR}/build"
NATIVE_ROOT="${SCRIPT_DIR}/native"
ACTIVE_NATIVE_DIR="${NATIVE_ROOT}/current"
LINUX_X64_DOCKERFILE="${SCRIPT_DIR}/scripts/docker/Dockerfile.linux-x64-ubuntu20"
REQUESTED_TARGET=""
RESOLVED_TARGET=""
TARGET_NATIVE_DIR=""
SOURCE_STAMP_FILE=""
RUN_BUILD_AFTER_CLEAN=0

usage() {
    cat <<EOF
Usage: ./build.sh [target] [--clean] [--build]

Targets:
  macos        Build the local macOS native library (default on macOS)
  linux        Build Linux x64 native library locally on Linux or with Docker on macOS
  linux-x64    Same as linux

Options:
  --clean      Remove generated build artifacts
  --build      Continue building after --clean
EOF
}

parse_args() {
    for arg in "$@"; do
        case "$arg" in
            --clean)
                CLEAN_REQUESTED=1
                ;;
            --build)
                RUN_BUILD_AFTER_CLEAN=1
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            macos|darwin|darwin-arm64|darwin-x64|linux|linux-x64)
                if [ -n "${REQUESTED_TARGET}" ]; then
                    echo -e "${RED}Error: multiple build targets provided.${NC}"
                    usage
                    exit 1
                fi
                REQUESTED_TARGET="$arg"
                ;;
            *)
                echo -e "${RED}Error: unknown argument: $arg${NC}"
                usage
                exit 1
                ;;
        esac
    done
}

detect_host_target() {
    local os arch
    os="$(uname -s)"
    arch="$(uname -m)"

    if [ -z "${REQUESTED_TARGET}" ]; then
        case "$os" in
            Darwin) REQUESTED_TARGET="macos" ;;
            Linux) REQUESTED_TARGET="linux" ;;
            *)
                echo -e "${RED}Error: unsupported host OS: $os${NC}"
                usage
                exit 1
                ;;
        esac
    fi

    case "${REQUESTED_TARGET}" in
        macos|darwin)
            if [ "$os" != "Darwin" ]; then
                echo -e "${RED}Error: macOS target must be built on macOS.${NC}"
                exit 1
            fi
            case "$arch" in
                arm64) RESOLVED_TARGET="darwin-arm64" ;;
                x86_64|amd64) RESOLVED_TARGET="darwin-x64" ;;
                *)
                    echo -e "${RED}Error: unsupported macOS architecture: $arch${NC}"
                    exit 1
                    ;;
            esac
            ;;
        darwin-arm64|darwin-x64)
            if [ "$os" != "Darwin" ]; then
                echo -e "${RED}Error: ${REQUESTED_TARGET} must be built on macOS.${NC}"
                exit 1
            fi
            RESOLVED_TARGET="${REQUESTED_TARGET}"
            ;;
        linux|linux-x64)
            if [ "$os" != "Linux" ] && [ "$os" != "Darwin" ]; then
                echo -e "${RED}Error: Linux target must be built on Linux or macOS with Docker.${NC}"
                exit 1
            fi
            RESOLVED_TARGET="linux-x64"
            ;;
        *)
            echo -e "${RED}Error: unsupported build target: ${REQUESTED_TARGET}${NC}"
            usage
            exit 1
            ;;
    esac

    TARGET_NATIVE_DIR="${NATIVE_ROOT}/${RESOLVED_TARGET}"
    SOURCE_STAMP_FILE="${TARGET_NATIVE_DIR}/.gopher-orch-source"
}

clean_artifacts() {
    echo -e "${YELLOW}Cleaning build artifacts (preserving _deps)...${NC}"
    rm -rf "${NATIVE_ROOT}"
    rm -rf "${SCRIPT_DIR}/dist"
    rm -rf "${SCRIPT_DIR}/build"
    rm -rf "${SCRIPT_DIR}/*.egg-info"
    rm -f "${BUILD_DIR}/CMakeCache.txt"
    rm -rf "${BUILD_DIR}/CMakeFiles"
    rm -rf "${BUILD_DIR}/lib"
    rm -rf "${BUILD_DIR}/bin"
    echo -e "${GREEN}✓ Clean complete${NC}"
}

CLEAN_REQUESTED=0
parse_args "$@"
detect_host_target

if [ "${CLEAN_REQUESTED}" = 1 ]; then
    clean_artifacts
    if [ "${RUN_BUILD_AFTER_CLEAN}" != 1 ]; then
        exit 0
    fi
fi

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Building gopher-orch Python SDK${NC}"
echo -e "${GREEN}======================================${NC}"
echo -e "${CYAN}Requested target: ${REQUESTED_TARGET}${NC}"
echo -e "${CYAN}Resolved target:  ${RESOLVED_TARGET}${NC}"
echo ""

# Step 1: Update submodules recursively
echo -e "${YELLOW}Step 1: Updating submodules...${NC}"

# Support custom SSH host for multiple GitHub accounts
# Usage: GITHUB_SSH_HOST=my-ssh-alias ./build.sh
SSH_HOST="${GITHUB_SSH_HOST:-github.com}"
if [ -n "${GITHUB_SSH_HOST}" ]; then
    echo -e "${YELLOW}  Using custom SSH host: ${GITHUB_SSH_HOST}${NC}"
fi

# Configure SSH URL rewrite for GopherSecurity repos
# Clear any existing rewrites first to avoid conflicts
git config --local --unset-all url."git@github.com:GopherSecurity/".insteadOf 2>/dev/null || true
git config --local --unset-all url."git@${SSH_HOST}:GopherSecurity/".insteadOf 2>/dev/null || true
# Set up URL rewrites - both https and default git@github.com should map to custom SSH host
git config --local --add url."git@${SSH_HOST}:GopherSecurity/".insteadOf "https://github.com/GopherSecurity/"
git config --local --add url."git@${SSH_HOST}:GopherSecurity/".insteadOf "git@github.com:GopherSecurity/"
git submodule sync -- third_party/gopher-orch
git config --local submodule.third_party/gopher-orch.url "git@${SSH_HOST}:GopherSecurity/gopher-orch.git"

# Preserve an existing local debug checkout. This mirrors the JS SDK behavior:
# if the submodule is dirty or intentionally moved away from the parent SHA,
# do not overwrite it with git submodule update.
if [ -f "${NATIVE_DIR}/CMakeLists.txt" ] && git -C "${NATIVE_DIR}" rev-parse --git-dir >/dev/null 2>&1; then
    RECORDED_COMMIT="$(git ls-tree HEAD third_party/gopher-orch | awk '{print $3}')"
    CURRENT_COMMIT="$(git -C "${NATIVE_DIR}" rev-parse HEAD 2>/dev/null || true)"
    SUBMODULE_STATUS="$(git -C "${NATIVE_DIR}" status --short 2>/dev/null || true)"

    if [ -n "${SUBMODULE_STATUS}" ] || { [ -n "${RECORDED_COMMIT}" ] && [ "${CURRENT_COMMIT}" != "${RECORDED_COMMIT}" ]; }; then
        echo -e "${YELLOW}  Using existing local gopher-orch checkout:${NC}"
        echo -e "${YELLOW}    recorded: ${RECORDED_COMMIT:-<unknown>}${NC}"
        echo -e "${YELLOW}    current:  ${CURRENT_COMMIT:-<unknown>}${NC}"
        if [ -n "${SUBMODULE_STATUS}" ]; then
            echo -e "${YELLOW}    local changes present; not running git submodule update for gopher-orch.${NC}"
        fi
        SKIP_GOPHER_ORCH_UPDATE=1
    else
        SKIP_GOPHER_ORCH_UPDATE=0
    fi
else
    SKIP_GOPHER_ORCH_UPDATE=0
fi

# Check if submodule directory exists but is empty/broken (missing CMakeLists.txt)
if [ -d "${NATIVE_DIR}" ] && [ ! -f "${NATIVE_DIR}/CMakeLists.txt" ]; then
    echo -e "${YELLOW}  Submodule directory exists but appears incomplete, reinitializing...${NC}"
    # Deinitialize and remove the submodule directory
    git submodule deinit -f third_party/gopher-orch 2>/dev/null || true
    rm -rf "${NATIVE_DIR}"
    rm -rf .git/modules/third_party/gopher-orch 2>/dev/null || true
fi

# Update the main submodule to the parent-recorded SHA by default so builds are
# reproducible. Developers can opt into branch-tip tracking when refreshing the
# pinned native dependency.
SUBMODULE_UPDATE_ARGS=(--init --checkout)
if [ "${GOPHER_ORCH_TRACK_REMOTE:-}" = "1" ]; then
    echo -e "${YELLOW}  GOPHER_ORCH_TRACK_REMOTE=1: tracking configured remote branch tips${NC}"
    SUBMODULE_UPDATE_ARGS+=(--remote)
fi

if [ "${SKIP_GOPHER_ORCH_UPDATE}" != 1 ]; then
    if ! git submodule update "${SUBMODULE_UPDATE_ARGS[@]}" third_party/gopher-orch; then
        echo -e "${RED}Error: Failed to update gopher-orch submodule${NC}"
        echo -e "${YELLOW}If you have multiple GitHub accounts, use:${NC}"
        echo -e "  GITHUB_SSH_HOST=your-ssh-alias ./build.sh"
        exit 1
    fi
fi

# Update nested submodule (gopher-mcp inside gopher-orch)
if [ -d "${NATIVE_DIR}" ]; then
    cd "${NATIVE_DIR}"
    git config --local --unset-all url."git@github.com:GopherSecurity/".insteadOf 2>/dev/null || true
    git config --local --unset-all url."git@${SSH_HOST}:GopherSecurity/".insteadOf 2>/dev/null || true
    git config --local url."git@${SSH_HOST}:GopherSecurity/".insteadOf "https://github.com/GopherSecurity/"
    git submodule sync -- third_party/gopher-mcp
    git config --local submodule.third_party/gopher-mcp.url "git@${SSH_HOST}:GopherSecurity/gopher-mcp.git"

    if [ -f "third_party/gopher-mcp/CMakeLists.txt" ] && git -C "third_party/gopher-mcp" rev-parse --git-dir >/dev/null 2>&1; then
        NESTED_STATUS="$(git -C "third_party/gopher-mcp" status --short 2>/dev/null || true)"
    else
        NESTED_STATUS=""
    fi
    if [ -n "${NESTED_STATUS}" ]; then
        echo -e "${YELLOW}    local changes present; not running git submodule update for gopher-mcp.${NC}"
    else
        # Keep the nested submodule pinned unless GOPHER_ORCH_TRACK_REMOTE=1
        # was requested above.
        if ! git submodule update "${SUBMODULE_UPDATE_ARGS[@]}" third_party/gopher-mcp; then
            echo -e "${RED}Error: Failed to update gopher-mcp submodule${NC}"
            echo -e "${YELLOW}If you have multiple GitHub accounts, use:${NC}"
            echo -e "  GITHUB_SSH_HOST=your-ssh-alias ./build.sh"
            exit 1
        fi
    fi
    # Also update gopher-mcp's nested submodules recursively
    if [ -d "third_party/gopher-mcp" ]; then
        cd third_party/gopher-mcp
        git config --local --unset-all url."git@github.com:GopherSecurity/".insteadOf 2>/dev/null || true
        git config --local --unset-all url."git@${SSH_HOST}:GopherSecurity/".insteadOf 2>/dev/null || true
        git config --local url."git@${SSH_HOST}:GopherSecurity/".insteadOf "https://github.com/GopherSecurity/"
        git submodule update --init --recursive 2>/dev/null || true
    fi
    cd "${SCRIPT_DIR}"
fi

echo -e "${GREEN}✓ Submodules updated${NC}"
echo ""

# Step 2: Check if gopher-orch exists
if [ ! -d "${NATIVE_DIR}" ]; then
    echo -e "${RED}Error: gopher-orch submodule not found at ${NATIVE_DIR}${NC}"
    echo -e "${RED}Run: git submodule update --init --recursive${NC}"
    exit 1
fi

build_linux_x64_docker() {
    echo -e "${YELLOW}Step 2: Building Ubuntu 20-compatible gopher-orch native library for linux-x64 with Docker...${NC}"

    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${RED}Error: Docker is required for ./build.sh linux on macOS.${NC}"
        echo "Please install Docker Desktop from https://www.docker.com/products/docker-desktop/"
        exit 1
    fi

    if [ ! -f "${LINUX_X64_DOCKERFILE}" ]; then
        echo -e "${RED}Error: Linux Dockerfile not found: ${LINUX_X64_DOCKERFILE}${NC}"
        exit 1
    fi

    local output_dir="${NATIVE_DIR}/build-output/linux-x64"
    local build_cache_dir="${NATIVE_DIR}/build-cache/linux-x64"
    rm -rf "${output_dir}"
    mkdir -p "${output_dir}" "${build_cache_dir}"

    echo -e "${YELLOW}  Building Docker image from Ubuntu 20.04...${NC}"
    docker build \
        --platform linux/amd64 \
        -t gopher-orch-python:linux-x64-ubuntu20 \
        -f "${LINUX_X64_DOCKERFILE}" \
        "${SCRIPT_DIR}"

    echo -e "${YELLOW}  Building and extracting Linux x64 artifacts...${NC}"
    echo -e "${YELLOW}    Reusing CMake cache: ${build_cache_dir}${NC}"
    docker run --rm \
        --platform linux/amd64 \
        -v "${NATIVE_DIR}:/source:ro" \
        -v "${build_cache_dir}:/build/cmake-build" \
        -v "${output_dir}:/host-output" \
        gopher-orch-python:linux-x64-ubuntu20

    if [ ! -f "${output_dir}/libgopher-orch.so" ] && [ -z "$(find "${output_dir}" -maxdepth 1 -name 'libgopher-orch.so*' -type f 2>/dev/null | head -n 1)" ]; then
        echo -e "${RED}Error: Linux Docker build did not produce libgopher-orch.so${NC}"
        exit 1
    fi

    rm -rf "${TARGET_NATIVE_DIR}.tmp"
    mkdir -p "${TARGET_NATIVE_DIR}.tmp/lib" "${TARGET_NATIVE_DIR}.tmp/bin"
    cp -P "${output_dir}"/*.so* "${TARGET_NATIVE_DIR}.tmp/lib/" 2>/dev/null || true
    cp -P "${output_dir}"/*.a "${TARGET_NATIVE_DIR}.tmp/lib/" 2>/dev/null || true
    if [ -d "${output_dir}/include" ]; then
        cp -R "${output_dir}/include" "${TARGET_NATIVE_DIR}.tmp/include"
    fi
    if [ -f "${output_dir}/verify_orch" ]; then
        cp "${output_dir}/verify_orch" "${TARGET_NATIVE_DIR}.tmp/bin/"
        chmod +x "${TARGET_NATIVE_DIR}.tmp/bin/verify_orch"
    fi

    rm -rf "${TARGET_NATIVE_DIR}"
    mv "${TARGET_NATIVE_DIR}.tmp" "${TARGET_NATIVE_DIR}"

    echo -e "${GREEN}✓ Native library built successfully for linux-x64${NC}"
    printf "%s\n" "${SOURCE_STAMP}" > "${SOURCE_STAMP_FILE}"
    echo ""
}

verify_linux_x64_docker_output() {
    if [ "${RESOLVED_TARGET}" != "linux-x64" ] || [ "$(uname -s)" != "Darwin" ]; then
        return
    fi

    if [ -x "${TARGET_NATIVE_DIR}/bin/verify_orch" ]; then
        echo -e "${YELLOW}  Verifying Linux artifact inside Ubuntu 20.04...${NC}"
        docker run --rm \
            --platform linux/amd64 \
            -v "${TARGET_NATIVE_DIR}:/work" \
            -w /work/lib \
            ubuntu:20.04 \
            sh -c 'LD_LIBRARY_PATH=/work/lib /work/bin/verify_orch'
    fi
}

# Step 3: Build gopher-orch native library
# Skip build only when the installed native lib matches the current submodule
# revisions and has the required auth symbols.
SKIP_NATIVE_BUILD=false
EXISTING_LIB="${TARGET_NATIVE_DIR}/lib/libgopher-orch.dylib"
if [ ! -f "${EXISTING_LIB}" ]; then
    EXISTING_LIB="${TARGET_NATIVE_DIR}/lib/libgopher-orch.so"
fi
if [ ! -f "${EXISTING_LIB}" ]; then
    EXISTING_LIB="${SCRIPT_DIR}/native/lib/libgopher-orch.dylib"
fi
if [ ! -f "${EXISTING_LIB}" ]; then
    EXISTING_LIB="${SCRIPT_DIR}/native/lib/libgopher-orch.so"
fi

SOURCE_STAMP="gopher-orch=$(git -C "${NATIVE_DIR}" rev-parse HEAD)"
if [ -d "${NATIVE_DIR}/third_party/gopher-mcp" ]; then
    SOURCE_STAMP="${SOURCE_STAMP}
gopher-mcp=$(git -C "${NATIVE_DIR}/third_party/gopher-mcp" rev-parse HEAD)"
fi

if [ -f "${EXISTING_LIB}" ]; then
    if [ -f "${SOURCE_STAMP_FILE}" ] && [ "$(cat "${SOURCE_STAMP_FILE}")" = "${SOURCE_STAMP}" ]; then
        if [ "${RESOLVED_TARGET}" = "linux-x64" ] && [ "$(uname -s)" = "Darwin" ]; then
            echo -e "${GREEN}✓ Linux native library already matches latest submodule revisions — skipping rebuild${NC}"
            echo -e "  (To force rebuild, delete ${TARGET_NATIVE_DIR}/lib/ first)"
            SKIP_NATIVE_BUILD=true
        elif (nm -gU "${EXISTING_LIB}" 2>/dev/null || nm -g "${EXISTING_LIB}" 2>/dev/null) | grep -q "gopher_auth_config_create"; then
            echo -e "${GREEN}✓ Native library already matches latest submodule revisions — skipping rebuild${NC}"
            echo -e "  (To force rebuild, delete ${TARGET_NATIVE_DIR}/lib/ first)"
            SKIP_NATIVE_BUILD=true
        fi
    else
        echo -e "${YELLOW}  Native source revision changed; rebuilding libgopher-orch${NC}"
    fi
fi

if [ "${SKIP_NATIVE_BUILD}" = false ]; then
if [ "${RESOLVED_TARGET}" = "linux-x64" ] && [ "$(uname -s)" = "Darwin" ]; then
    build_linux_x64_docker
else
echo -e "${YELLOW}Step 2: Building gopher-orch native library...${NC}"
cd "${NATIVE_DIR}"

# Create build directory
if [ ! -d "${BUILD_DIR}" ]; then
    mkdir -p "${BUILD_DIR}"
fi

cd "${BUILD_DIR}"

# Configure with CMake
# BUILD_BUNDLED_SHARED=OFF means we need to copy all dependency libraries separately
echo -e "${YELLOW}  Configuring CMake...${NC}"
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${TARGET_NATIVE_DIR}" \
    -DBUILD_SHARED_LIBS=ON \
    -DBUILD_BUNDLED_SHARED=OFF \
    -DBUILD_TESTS=OFF \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON

# Build
echo -e "${YELLOW}  Compiling...${NC}"
cmake --build . --config Release -j$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)

# Install to native directory
echo -e "${YELLOW}  Installing...${NC}"
cmake --install .

# Copy dependency libraries (since BUILD_BUNDLED_SHARED=OFF)
echo -e "${YELLOW}  Copying dependency libraries...${NC}"
NATIVE_LIB="${TARGET_NATIVE_DIR}/lib"
mkdir -p "${NATIVE_LIB}"

# Copy gopher-mcp libraries
cp -P "${BUILD_DIR}"/lib/libgopher-mcp*.dylib "${NATIVE_LIB}/" 2>/dev/null || true
cp -P "${BUILD_DIR}"/lib/libgopher-mcp*.so* "${NATIVE_LIB}/" 2>/dev/null || true
cp -P "${BUILD_DIR}"/lib/libgopher-mcp-event*.dylib "${NATIVE_LIB}/" 2>/dev/null || true
cp -P "${BUILD_DIR}"/lib/libgopher-mcp-event*.so* "${NATIVE_LIB}/" 2>/dev/null || true
cp -P "${BUILD_DIR}"/lib/libgopher-mcp-logging*.dylib "${NATIVE_LIB}/" 2>/dev/null || true
cp -P "${BUILD_DIR}"/lib/libgopher-mcp-logging*.so* "${NATIVE_LIB}/" 2>/dev/null || true

# Copy fmt and llhttp static libraries
cp -P "${BUILD_DIR}"/lib/libfmt*.a "${NATIVE_LIB}/" 2>/dev/null || true
cp -P "${BUILD_DIR}"/lib/libllhttp*.a "${NATIVE_LIB}/" 2>/dev/null || true
cp -P "${BUILD_DIR}"/_deps/fmt-build/libfmt*.a "${NATIVE_LIB}/" 2>/dev/null || true

cd "${SCRIPT_DIR}"

echo -e "${GREEN}✓ Native library built successfully${NC}"
printf "%s\n" "${SOURCE_STAMP}" > "${SOURCE_STAMP_FILE}"
echo ""

fi
fi  # end SKIP_NATIVE_BUILD

# Step 4: Verify build artifacts
echo -e "${YELLOW}Step 3: Verifying native build artifacts...${NC}"

NATIVE_LIB_DIR="${TARGET_NATIVE_DIR}/lib"
NATIVE_INCLUDE_DIR="${TARGET_NATIVE_DIR}/include"

if [ -d "${TARGET_NATIVE_DIR}" ]; then
    rm -rf "${ACTIVE_NATIVE_DIR}"
    ln -s "${RESOLVED_TARGET}" "${ACTIVE_NATIVE_DIR}"

    mkdir -p "${NATIVE_ROOT}/lib"
    mkdir -p "${NATIVE_ROOT}/include"
    cp -P "${TARGET_NATIVE_DIR}"/lib/* "${NATIVE_ROOT}/lib/" 2>/dev/null || true
    cp -R "${TARGET_NATIVE_DIR}"/include/* "${NATIVE_ROOT}/include/" 2>/dev/null || true
    printf "%s\n" "${SOURCE_STAMP}" > "${NATIVE_ROOT}/.gopher-orch-source"
fi

if [ -d "${NATIVE_LIB_DIR}" ]; then
    echo -e "${GREEN}✓ Libraries installed to: ${NATIVE_LIB_DIR}${NC}"
    ls -lh "${NATIVE_LIB_DIR}"/lib*.dylib 2>/dev/null || \
    ls -lh "${NATIVE_LIB_DIR}"/lib*.so 2>/dev/null || \
    ls -lh "${NATIVE_LIB_DIR}"/*.dll 2>/dev/null || true
else
    echo -e "${YELLOW}⚠ Library directory not found: ${NATIVE_LIB_DIR}${NC}"
fi

verify_linux_x64_docker_output

if [ -d "${NATIVE_INCLUDE_DIR}" ]; then
    echo -e "${GREEN}✓ Headers installed to: ${NATIVE_INCLUDE_DIR}${NC}"
else
    echo -e "${YELLOW}⚠ Include directory not found: ${NATIVE_INCLUDE_DIR}${NC}"
fi

echo ""

# Step 5: Set up Python environment
echo -e "${YELLOW}Step 4: Setting up Python environment...${NC}"
cd "${SCRIPT_DIR}"

if [ "${RESOLVED_TARGET}" = "linux-x64" ] && [ "$(uname -s)" = "Darwin" ]; then
    echo -e "${YELLOW}Skipping Python environment setup for Linux native output on macOS.${NC}"
else

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found. Please install Python 3.8+ first.${NC}"
    echo -e "${YELLOW}  macOS: brew install python${NC}"
    echo -e "${YELLOW}  Linux: sudo apt-get install python3 python3-pip${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo -e "${RED}Error: Python 3.8+ required. Current version: ${PYTHON_VERSION}${NC}"
    exit 1
fi

# Install dependencies
echo -e "${YELLOW}  Installing pip dependencies...${NC}"

# Check if we're in a virtual environment
if [ -n "$VIRTUAL_ENV" ]; then
    pip3 install -e ".[dev]" --quiet 2>/dev/null || pip3 install -e ".[dev]"
else
    # Try user install first, then fall back to regular install
    pip3 install --user -e ".[dev]" --quiet 2>/dev/null || \
    pip3 install --user -e ".[dev]" 2>/dev/null || \
    echo -e "${YELLOW}  Note: Could not install in editable mode. You can manually run: pip3 install --user -e '.[dev]'${NC}"
fi

echo -e "${GREEN}✓ Python environment set up successfully${NC}"
echo ""

fi

# Step 6: Run tests
echo -e "${YELLOW}Step 5: Running tests...${NC}"

if [ "${RESOLVED_TARGET}" = "linux-x64" ] && [ "$(uname -s)" = "Darwin" ]; then
    echo -e "${YELLOW}Skipping host Python tests for Linux native output on macOS.${NC}"
else

# Use PYTHONPATH to ensure gopher_orch module can be found even without editable install
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

# Use the freshly built native library (not a stale pip-installed version)
export GOPHER_MCP_PYTHON_LIBRARY_PATH="${NATIVE_LIB_DIR}/libgopher-orch.dylib"
if [ ! -f "${GOPHER_MCP_PYTHON_LIBRARY_PATH}" ]; then
    # Try .so for Linux
    export GOPHER_MCP_PYTHON_LIBRARY_PATH="${NATIVE_LIB_DIR}/libgopher-orch.so"
fi
export GOPHER_ORCH_LIBRARY_PATH="${GOPHER_MCP_PYTHON_LIBRARY_PATH}"
export DYLD_LIBRARY_PATH="${NATIVE_LIB_DIR}:${DYLD_LIBRARY_PATH}"
export LD_LIBRARY_PATH="${NATIVE_LIB_DIR}:${LD_LIBRARY_PATH}"

# Try to run pytest, handling different installation scenarios
if python3 -c "import pytest" 2>/dev/null; then
    python3 -m pytest tests/ -v && echo -e "${GREEN}✓ Tests passed${NC}" || echo -e "${YELLOW}⚠ Some tests failed${NC}"
elif [ -f "$HOME/Library/Python/3.9/bin/pytest" ]; then
    # macOS user-installed pytest
    "$HOME/Library/Python/3.9/bin/pytest" tests/ -v && echo -e "${GREEN}✓ Tests passed${NC}" || echo -e "${YELLOW}⚠ Some tests failed${NC}"
else
    echo -e "${YELLOW}⚠ pytest not found. Install with: pip3 install --user pytest${NC}"
fi

fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Build completed successfully!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "Native libraries: ${YELLOW}${NATIVE_LIB_DIR}${NC}"
echo -e "Native headers:   ${YELLOW}${NATIVE_INCLUDE_DIR}${NC}"
echo ""
echo -e "${GREEN}Run tests:${NC}"
echo -e "  ${YELLOW}python3 -m pytest tests/${NC}"
echo ""
echo -e "${GREEN}Run examples:${NC}"
echo -e "  ${YELLOW}python3 examples/client_example.py${NC}"
echo ""
echo -e "${GREEN}Run Auth MCP Server example:${NC}"
echo -e "  ${YELLOW}cd examples/auth && ./run_example.sh${NC}           # Uses server.config settings"
echo -e "  ${YELLOW}cd examples/auth && ./run_example.sh --no-auth${NC} # Override to disable auth"
echo -e "  ${YELLOW}cd examples/auth && ./run_example.sh --help${NC}    # Show all options"
echo ""
echo -e "  Test endpoints:"
echo -e "    ${YELLOW}curl http://localhost:3001/health${NC}"
echo -e "    ${YELLOW}curl -X POST http://localhost:3001/mcp -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}'${NC}"
