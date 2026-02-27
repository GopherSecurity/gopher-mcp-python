"""
Native library package for gopher-security-mcp (Windows x64).

This package contains the native gopher-security-mcp library for Windows on x64.
"""

import os
from pathlib import Path

__version__ = "0.1.0.dev20260226145002"

# Platform identifier
PLATFORM = "win32"
ARCH = "x64"


def get_lib_path() -> Path:
    """Get the path to the native library directory."""
    return Path(__file__).parent / "lib"


def get_library_file() -> Path:
    """Get the path to the native library file."""
    return get_lib_path() / "gopher-security-mcp.dll"
