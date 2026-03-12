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

    package_name = f"gopher_mcp_python_native_{platform_name}_{normalized_arch}"

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


# ============================================================================
# FFI Function Bindings
# ============================================================================

# Track if functions are set up
_functions_setup: bool = False
_auth_functions_available: bool = False

# Function binding specifications: (name, argtypes, restype)
_FUNCTION_SPECS = [
    # Library lifecycle
    ("gopher_auth_init", [], c_int32),
    ("gopher_auth_shutdown", [], c_int32),
    ("gopher_auth_version", [], c_char_p),
    # Client
    ("gopher_auth_client_create", [POINTER(c_void_p), c_char_p, c_char_p], c_int32),
    ("gopher_auth_client_destroy", [c_void_p], c_int32),
    ("gopher_auth_client_set_option", [c_void_p, c_char_p, c_char_p], c_int32),
    # Options
    ("gopher_auth_validation_options_create", [POINTER(c_void_p)], c_int32),
    ("gopher_auth_validation_options_destroy", [c_void_p], c_int32),
    ("gopher_auth_validation_options_set_scopes", [c_void_p, c_char_p], c_int32),
    ("gopher_auth_validation_options_set_audience", [c_void_p, c_char_p], c_int32),
    ("gopher_auth_validation_options_set_clock_skew", [c_void_p, c_int64], c_int32),
    # Validation
    ("gopher_auth_validate_token", [c_void_p, c_char_p, c_void_p, POINTER(GopherAuthValidationResult)], c_int32),
    ("gopher_auth_extract_payload", [c_char_p, POINTER(c_void_p)], c_int32),
    # Payload
    ("gopher_auth_payload_get_subject", [c_void_p, POINTER(c_char_p)], c_int32),
    ("gopher_auth_payload_get_scopes", [c_void_p, POINTER(c_char_p)], c_int32),
    ("gopher_auth_payload_get_audience", [c_void_p, POINTER(c_char_p)], c_int32),
    ("gopher_auth_payload_get_expiration", [c_void_p, POINTER(c_int64)], c_int32),
    ("gopher_auth_payload_get_issuer", [c_void_p, POINTER(c_char_p)], c_int32),
    ("gopher_auth_payload_destroy", [c_void_p], c_int32),
    # Utility
    ("gopher_auth_free_string", [c_char_p], None),
    ("gopher_auth_generate_www_authenticate", [c_char_p, c_char_p, c_char_p, POINTER(c_char_p)], c_int32),
    ("gopher_auth_generate_www_authenticate_v2", [c_char_p, c_char_p, c_char_p, c_char_p, c_char_p, POINTER(c_char_p)], c_int32),
]


def _setup_functions() -> bool:
    """
    Setup FFI function bindings for all gopher_auth_* functions.

    This configures argument types and return types for all exported
    C functions in the library. Functions that don't exist in the
    library are skipped.

    Returns:
        True if at least gopher_auth_init is available, False otherwise.
    """
    global _functions_setup, _auth_functions_available

    if _functions_setup:
        return _auth_functions_available

    if _lib is None:
        return False

    bound_count = 0
    for name, argtypes, restype in _FUNCTION_SPECS:
        try:
            func = getattr(_lib, name)
            func.argtypes = argtypes
            func.restype = restype
            bound_count += 1
        except AttributeError:
            if _debug:
                print(f"Function not found: {name}", file=sys.stderr)

    _functions_setup = True
    # Consider auth available if we bound at least the init function
    _auth_functions_available = bound_count > 0 and _has_function("gopher_auth_init")

    if _debug:
        print(f"Bound {bound_count}/{len(_FUNCTION_SPECS)} auth functions", file=sys.stderr)

    return _auth_functions_available


def _has_function(name: str) -> bool:
    """
    Check if a specific function exists in the library.

    Args:
        name: The function name to check.

    Returns:
        True if function exists, False otherwise.
    """
    if _lib is None:
        return False
    try:
        getattr(_lib, name)
        return True
    except AttributeError:
        return False


def _get_function(name: str) -> Optional[Any]:
    """
    Get a function from the library if it exists.

    Args:
        name: The function name to get.

    Returns:
        The function object if found, None otherwise.
    """
    if _lib is None:
        return None
    try:
        return getattr(_lib, name)
    except AttributeError:
        return None


def is_auth_available() -> bool:
    """
    Check if auth functions are available in the loaded library.

    Returns:
        True if auth functions are available, False otherwise.
    """
    if not load_library():
        return False
    _setup_functions()
    return _auth_functions_available


def get_auth_functions() -> Dict[str, Any]:
    """
    Get dictionary of all auth function references.

    This ensures the library is loaded and functions are set up,
    then returns references to all the C functions. Functions that
    don't exist in the library will have None as their value.

    Returns:
        Dictionary mapping function names to ctypes function objects
        or None for unavailable functions.
    """
    if not load_library():
        return {}

    _setup_functions()

    return {
        # Library lifecycle
        "auth_init": _get_function("gopher_auth_init"),
        "auth_shutdown": _get_function("gopher_auth_shutdown"),
        "auth_version": _get_function("gopher_auth_version"),
        # Client
        "client_create": _get_function("gopher_auth_client_create"),
        "client_destroy": _get_function("gopher_auth_client_destroy"),
        "client_set_option": _get_function("gopher_auth_client_set_option"),
        # Options
        "options_create": _get_function("gopher_auth_validation_options_create"),
        "options_destroy": _get_function("gopher_auth_validation_options_destroy"),
        "options_set_scopes": _get_function("gopher_auth_validation_options_set_scopes"),
        "options_set_audience": _get_function("gopher_auth_validation_options_set_audience"),
        "options_set_clock_skew": _get_function("gopher_auth_validation_options_set_clock_skew"),
        # Validation
        "validate_token": _get_function("gopher_auth_validate_token"),
        "extract_payload": _get_function("gopher_auth_extract_payload"),
        # Payload
        "payload_get_subject": _get_function("gopher_auth_payload_get_subject"),
        "payload_get_scopes": _get_function("gopher_auth_payload_get_scopes"),
        "payload_get_audience": _get_function("gopher_auth_payload_get_audience"),
        "payload_get_expiration": _get_function("gopher_auth_payload_get_expiration"),
        "payload_get_issuer": _get_function("gopher_auth_payload_get_issuer"),
        "payload_destroy": _get_function("gopher_auth_payload_destroy"),
        # Utility
        "free_string": _get_function("gopher_auth_free_string"),
        "generate_www_authenticate": _get_function("gopher_auth_generate_www_authenticate"),
        "generate_www_authenticate_v2": _get_function("gopher_auth_generate_www_authenticate_v2"),
    }
