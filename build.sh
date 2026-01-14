#!/bin/bash

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Building gopher-orch TypeScript SDK${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NATIVE_DIR="${SCRIPT_DIR}/third_party/gopher-orch"
BUILD_DIR="${NATIVE_DIR}/build"

# Step 1: Update submodules recursively
echo -e "${YELLOW}Step 1: Updating submodules recursively...${NC}"
git submodule update --init --recursive
echo -e "${GREEN}✓ Submodules updated${NC}"
echo ""

# Step 2: Check if gopher-orch exists
if [ ! -d "${NATIVE_DIR}" ]; then
    echo -e "${RED}Error: gopher-orch submodule not found at ${NATIVE_DIR}${NC}"
    echo -e "${RED}Run: git submodule update --init --recursive${NC}"
    exit 1
fi

# Step 3: Build gopher-orch native library
echo -e "${YELLOW}Step 2: Building gopher-orch native library...${NC}"
cd "${NATIVE_DIR}"

# Create build directory
if [ ! -d "${BUILD_DIR}" ]; then
    mkdir -p "${BUILD_DIR}"
fi

cd "${BUILD_DIR}"

# Configure with CMake
echo -e "${YELLOW}  Configuring CMake...${NC}"
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${SCRIPT_DIR}/native" \
    -DBUILD_SHARED_LIBS=ON \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON

# Build
echo -e "${YELLOW}  Compiling...${NC}"
cmake --build . --config Release -j$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)

# Install to native directory
echo -e "${YELLOW}  Installing...${NC}"
cmake --install .

echo -e "${GREEN}✓ Native library built successfully${NC}"
echo ""

# Step 4: Verify build artifacts
echo -e "${YELLOW}Step 3: Verifying build artifacts...${NC}"

NATIVE_LIB_DIR="${SCRIPT_DIR}/native/lib"
NATIVE_INCLUDE_DIR="${SCRIPT_DIR}/native/include"

if [ -d "${NATIVE_LIB_DIR}" ]; then
    echo -e "${GREEN}✓ Libraries installed to: ${NATIVE_LIB_DIR}${NC}"
    ls -lh "${NATIVE_LIB_DIR}"/*.dylib 2>/dev/null || ls -lh "${NATIVE_LIB_DIR}"/*.so 2>/dev/null || true
else
    echo -e "${YELLOW}⚠ Library directory not found: ${NATIVE_LIB_DIR}${NC}"
fi

if [ -d "${NATIVE_INCLUDE_DIR}" ]; then
    echo -e "${GREEN}✓ Headers installed to: ${NATIVE_INCLUDE_DIR}${NC}"
else
    echo -e "${YELLOW}⚠ Include directory not found: ${NATIVE_INCLUDE_DIR}${NC}"
fi

echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Build completed successfully!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Install TypeScript dependencies: ${YELLOW}npm install${NC}"
echo -e "  2. Build TypeScript SDK: ${YELLOW}npm run build${NC}"
echo -e "  3. Run tests: ${YELLOW}npm test${NC}"
