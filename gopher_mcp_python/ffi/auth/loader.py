"""
Auth Library Loader - ctypes bindings for libgopher-orch.

Provides FFI bindings to the gopher-auth native library for
JWT token validation and OAuth support.

Note: The gopher_auth_* functions are part of libgopher-orch,
not a separate library.
"""

import ctypes
import os
import platform
import sys
from ctypes import (
    POINTER,
    Structure,
    c_bool,
    c_char_p,
    c_int,
    c_int32,
    c_int64,
    c_void_p,
)
from pathlib import Path
from typing import Dict, List, Optional, Any

# Track if library is loaded
_lib: Optional[ctypes.CDLL] = None
_lib_available: bool = False
_debug: bool = False

# Opaque pointer types
GopherAuthClientPtr = c_void_p
GopherAuthPayloadPtr = c_void_p
GopherAuthOptionsPtr = c_void_p


class GopherAuthValidationResult(Structure):
    """Validation result structure from C API."""

    _fields_ = [
        ("valid", c_bool),
        ("error_code", c_int32),
        ("error_message", c_char_p),
    ]


def _get_library_name() -> str:
    """
    Get the library name for the current platform.

    Returns:
        Library filename appropriate for the current OS.
    """
    system = platform.system().lower()
    if system == "darwin":
        return "libgopher-orch.dylib"
    elif system == "windows":
        return "gopher-orch.dll"
    else:
        return "libgopher-orch.so"


def _get_platform_package_path() -> Optional[str]:
    """
    Get the path to the platform-specific optional dependency package.

    This supports pip-distributed native packages with architecture-specific
    binaries.

    Returns:
        Path to the library directory if found, None otherwise.
    """
    system = platform.system().lower()
    arch = platform.machine().lower()

    # Normalize architecture names
    arch_map = {
        "x86_64": "x64",
        "amd64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    normalized_arch = arch_map.get(arch, arch)

    # Platform names
    platform_map = {
        "darwin": "darwin",
        "linux": "linux",
        "windows": "win32",
    }
    platform_name = platform_map.get(system)
    if not platform_name:
        return None

    package_name = f"gopher_orch_{platform_name}_{normalized_arch}"

    # Try to find the package in site-packages
    for site_path in sys.path:
        package_dir = Path(site_path) / package_name
        if package_dir.exists():
            lib_path = package_dir / "lib"
            if lib_path.exists():
                return str(lib_path)

    return None


def _get_search_paths() -> List[str]:
    """
    Get search paths for the native library.

    Returns:
        List of directory paths to search for the library.
    """
    paths: List[str] = []

    # Platform-specific optional dependency package
    platform_package_path = _get_platform_package_path()
    if platform_package_path:
        paths.append(platform_package_path)

    # Get the directory containing this module
    module_dir = Path(__file__).parent.parent.parent.parent

    # Development paths
    paths.extend([
        str(Path.cwd() / "native" / "lib"),
        str(Path.cwd() / "lib"),
        str(module_dir / "native" / "lib"),
        str(module_dir.parent / "native" / "lib"),
    ])

    # System paths
    system = platform.system().lower()
    if system == "darwin":
        paths.extend(["/usr/local/lib", "/opt/homebrew/lib"])
    paths.append("/usr/lib")

    return paths


def load_library() -> bool:
    """
    Load the gopher-orch native library.

    Searches for the library in the following order:
    1. Path specified by GOPHER_ORCH_LIBRARY_PATH environment variable
    2. Platform-specific pip package
    3. Development paths (native/lib, lib)
    4. System paths (/usr/local/lib, /usr/lib, etc.)

    Returns:
        True if library loaded successfully, False otherwise.
    """
    global _lib, _lib_available, _debug

    if _lib is not None:
        return _lib_available

    _debug = os.environ.get("DEBUG") is not None
    library_name = _get_library_name()
    search_paths = _get_search_paths()

    # Try environment variable path first
    env_path = os.environ.get("GOPHER_ORCH_LIBRARY_PATH") or os.environ.get(
        "GOPHER_AUTH_LIBRARY_PATH"
    )
    if env_path and os.path.exists(env_path):
        try:
            _lib = ctypes.CDLL(env_path)
            _lib_available = True
            return True
        except OSError as e:
            if _debug:
                print(f"Failed to load from environment path: {e}", file=sys.stderr)

    # Try search paths
    for search_path in search_paths:
        lib_file = os.path.join(search_path, library_name)
        if os.path.exists(lib_file):
            try:
                _lib = ctypes.CDLL(lib_file)
                _lib_available = True
                return True
            except OSError as e:
                if _debug:
                    print(f"Failed to load from {search_path}: {e}", file=sys.stderr)

    # Try system paths (let the OS find it)
    try:
        _lib = ctypes.CDLL(library_name)
        _lib_available = True
        return True
    except OSError as e:
        if _debug:
            print(f"Failed to load gopher-orch library: {e}", file=sys.stderr)
            print("Searched paths:", file=sys.stderr)
            for p in search_paths:
                print(f"  - {p}", file=sys.stderr)

    _lib_available = False
    return False


def is_library_loaded() -> bool:
    """
    Check if the library is loaded and available.

    Returns:
        True if the library is loaded, False otherwise.
    """
    return _lib_available


def get_library() -> Optional[ctypes.CDLL]:
    """
    Get the loaded library instance.

    Returns:
        The loaded CDLL instance, or None if not loaded.
    """
    return _lib
