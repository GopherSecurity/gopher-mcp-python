"""
Native library package for gopher-mcp-python (Linux x64).

This package contains the native gopher-mcp-python library for Linux on x64.
"""

import os
from pathlib import Path

__version__ = "0.1.0.dev20260227124047"

# Platform identifier
PLATFORM = "linux"
ARCH = "x64"


def get_lib_path() -> Path:
    """Get the path to the native library directory."""
    return Path(__file__).parent / "lib"


def get_library_file() -> Path:
    """Get the path to the native library file."""
    return get_lib_path() / "libgopher-orch.so"
