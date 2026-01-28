"""
ctypes interface to the gopher-orch native library.
"""

import ctypes
import os
import sys
from ctypes import c_char_p, c_void_p, c_int32, c_int64, POINTER, Structure
from pathlib import Path
from typing import Optional, Any

# Type alias for opaque handle
GopherOrchHandle = c_void_p


class GopherOrchErrorInfo(Structure):
    """
    Error info structure matching C:
    typedef struct {
        gopher_orch_error_t code;
        const char* message;
        const char* details;
        const char* file;
        int32_t line;
    } gopher_orch_error_info_t;
    """

    _fields_ = [
        ("code", c_int32),
        ("message", c_char_p),
        ("details", c_char_p),
        ("file", c_char_p),
        ("line", c_int32),
    ]


class GopherOrchLibrary:
    """
    Wrapper for the gopher-orch native library using ctypes.
    """

    _instance: Optional["GopherOrchLibrary"] = None
    _lib: Optional[ctypes.CDLL] = None
    _available: bool = False
    _debug: bool = False

    def __init__(self) -> None:
        self._load_library()

    @classmethod
    def get_instance(cls) -> Optional["GopherOrchLibrary"]:
        """
        Get the library instance, loading it if necessary.
        """
        if cls._instance is None:
            cls._instance = GopherOrchLibrary()
        return cls._instance if cls._instance._available else None

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if the library is available.
        """
        instance = cls.get_instance()
        return instance is not None and instance._available

    def _load_library(self) -> None:
        self._debug = os.environ.get("DEBUG") is not None

        library_name = self._get_library_name()
        search_paths = self._get_search_paths()

        # Try custom path from environment variable
        env_path = os.environ.get("GOPHER_ORCH_LIBRARY_PATH")
        if env_path and os.path.exists(env_path):
            try:
                self._lib = ctypes.CDLL(env_path)
                self._setup_functions()
                self._available = True
                return
            except OSError as e:
                if self._debug:
                    print(
                        f"Failed to load from GOPHER_ORCH_LIBRARY_PATH: {e}",
                        file=sys.stderr,
                    )

        # Try search paths
        for search_path in search_paths:
            lib_file = os.path.join(search_path, library_name)
            if os.path.exists(lib_file):
                try:
                    self._lib = ctypes.CDLL(lib_file)
                    self._setup_functions()
                    self._available = True
                    return
                except OSError as e:
                    if self._debug:
                        print(f"Failed to load from {search_path}: {e}", file=sys.stderr)

        # Try loading by name (system paths)
        try:
            self._lib = ctypes.CDLL(library_name)
            self._setup_functions()
            self._available = True
            return
        except OSError as e:
            if self._debug:
                print(f"Failed to load gopher-orch library: {e}", file=sys.stderr)
                print("Searched paths:", file=sys.stderr)
                for p in search_paths:
                    print(f"  - {p}", file=sys.stderr)

        self._available = False

    def _setup_functions(self) -> None:
        if self._lib is None:
            return

        # Agent functions
        self._lib.gopher_orch_agent_create_by_json.argtypes = [
            c_char_p,
            c_char_p,
            c_char_p,
        ]
        self._lib.gopher_orch_agent_create_by_json.restype = c_void_p

        self._lib.gopher_orch_agent_create_by_api_key.argtypes = [
            c_char_p,
            c_char_p,
            c_char_p,
        ]
        self._lib.gopher_orch_agent_create_by_api_key.restype = c_void_p

        self._lib.gopher_orch_agent_run.argtypes = [c_void_p, c_char_p, c_int64]
        self._lib.gopher_orch_agent_run.restype = c_char_p

        self._lib.gopher_orch_agent_add_ref.argtypes = [c_void_p]
        self._lib.gopher_orch_agent_add_ref.restype = None

        self._lib.gopher_orch_agent_release.argtypes = [c_void_p]
        self._lib.gopher_orch_agent_release.restype = None

        # API functions
        self._lib.gopher_orch_api_fetch_servers.argtypes = [c_char_p]
        self._lib.gopher_orch_api_fetch_servers.restype = c_char_p

        # Error functions
        self._lib.gopher_orch_last_error.argtypes = []
        self._lib.gopher_orch_last_error.restype = POINTER(GopherOrchErrorInfo)

        self._lib.gopher_orch_clear_error.argtypes = []
        self._lib.gopher_orch_clear_error.restype = None

        self._lib.gopher_orch_free.argtypes = [c_void_p]
        self._lib.gopher_orch_free.restype = None

    def _get_library_name(self) -> str:
        if sys.platform == "darwin":
            return "libgopher-orch.dylib"
        elif sys.platform == "win32":
            return "gopher-orch.dll"
        else:
            return "libgopher-orch.so"

    def _get_search_paths(self) -> list:
        # Get the directory containing this module
        module_dir = Path(__file__).parent.parent.parent

        paths = [
            # Project root native/lib
            os.path.join(os.getcwd(), "native", "lib"),
            # Relative to module location
            os.path.join(module_dir, "native", "lib"),
            os.path.join(module_dir.parent, "native", "lib"),
        ]

        # System paths
        if sys.platform == "darwin":
            paths.extend(["/usr/local/lib", "/opt/homebrew/lib"])
        paths.append("/usr/lib")

        return paths

    # Agent functions
    def agent_create_by_json(
        self, provider: str, model: str, server_json: str
    ) -> Optional[GopherOrchHandle]:
        """Create an agent using JSON server configuration."""
        if not self._available or self._lib is None:
            return None
        return self._lib.gopher_orch_agent_create_by_json(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            server_json.encode("utf-8"),
        )

    def agent_create_by_api_key(
        self, provider: str, model: str, api_key: str
    ) -> Optional[GopherOrchHandle]:
        """Create an agent using API key."""
        if not self._available or self._lib is None:
            return None
        return self._lib.gopher_orch_agent_create_by_api_key(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
        )

    def agent_run(
        self, agent: GopherOrchHandle, query: str, timeout_ms: int
    ) -> Optional[str]:
        """Run a query against the agent."""
        if not self._available or self._lib is None:
            return None
        result = self._lib.gopher_orch_agent_run(
            agent, query.encode("utf-8"), timeout_ms
        )
        if result:
            return result.decode("utf-8")
        return None

    def agent_add_ref(self, agent: GopherOrchHandle) -> None:
        """Add a reference to the agent."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_agent_add_ref(agent)

    def agent_release(self, agent: GopherOrchHandle) -> None:
        """Release the agent."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_agent_release(agent)

    # API functions
    def api_fetch_servers(self, api_key: str) -> Optional[str]:
        """Fetch server configuration from API."""
        if not self._available or self._lib is None:
            return None
        result = self._lib.gopher_orch_api_fetch_servers(api_key.encode("utf-8"))
        if result:
            return result.decode("utf-8")
        return None

    # Error functions
    def last_error(self) -> Optional[GopherOrchErrorInfo]:
        """Get the last error info."""
        if not self._available or self._lib is None:
            return None
        error_ptr = self._lib.gopher_orch_last_error()
        if error_ptr and error_ptr.contents:
            return error_ptr.contents
        return None

    def get_last_error_message(self) -> Optional[str]:
        """Get the last error message."""
        error_info = self.last_error()
        if error_info and error_info.message:
            return error_info.message.decode("utf-8")
        return None

    def clear_error(self) -> None:
        """Clear the last error."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_clear_error()

    def free(self, ptr: Any) -> None:
        """Free memory allocated by the library."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_free(ptr)
