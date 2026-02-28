"""
Native library package for gopher-mcp-python (macOS ARM64).

This package contains the native gopher-mcp-python library for macOS on Apple Silicon.
"""

import os
from pathlib import Path

__version__ = "0.1.1"

# Platform identifier
PLATFORM = "darwin"
ARCH = "arm64"


def get_lib_path() -> Path:
    """Get the path to the native library directory."""
    return Path(__file__).parent / "lib"


def get_library_file() -> Path:
    """Get the path to the native library file."""
    return get_lib_path() / "libgopher-orch.dylib"
