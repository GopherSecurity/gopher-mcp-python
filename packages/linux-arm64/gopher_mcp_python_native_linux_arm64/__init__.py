"""
Native library package for gopher-mcp-python (Linux ARM64).

This package contains the native gopher-mcp-python library for Linux on ARM64.
"""

import os
from pathlib import Path

__version__ = "0.1.1"

# Platform identifier
PLATFORM = "linux"
ARCH = "arm64"


def get_lib_path() -> Path:
    """Get the path to the native library directory."""
    return Path(__file__).parent / "lib"


def get_library_file() -> Path:
    """Get the path to the native library file."""
    return get_lib_path() / "libgopher-orch.so"
