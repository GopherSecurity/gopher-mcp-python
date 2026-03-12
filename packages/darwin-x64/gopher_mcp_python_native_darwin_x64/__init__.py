"""
Native library package for gopher-mcp-python (macOS Intel).

This package contains the native gopher-mcp-python library for macOS on Intel.
"""

import os
from pathlib import Path

__version__ = "0.1.2"

# Platform identifier
PLATFORM = "darwin"
ARCH = "x64"


def get_lib_path() -> Path:
    """Get the path to the native library directory."""
    return Path(__file__).parent / "lib"


def get_library_file() -> Path:
    """Get the path to the native library file."""
    return get_lib_path() / "libgopher-orch.dylib"
