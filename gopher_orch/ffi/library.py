"""ctypes interface to the gopher-orch native library."""

import ctypes
import os
import sys
from ctypes import POINTER, Structure, c_char_p, c_int32, c_int64, c_void_p
from pathlib import Path
from typing import Optional

# Type aliases
GopherOrchHandle = c_void_p


class GopherOrchErrorInfo(Structure):
    """Error info structure matching C:
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
    """Wrapper for the gopher-orch native library using ctypes."""

    _instance: Optional["GopherOrchLibrary"] = None
    _lib: Optional[ctypes.CDLL] = None
    _available: bool = False
    _debug: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_library()
        return cls._instance

    @classmethod
    def get_instance(cls) -> Optional["GopherOrchLibrary"]:
        """Get the library instance, loading it if necessary."""
        try:
            return cls()
        except Exception:
            return None

    @classmethod
    def is_available(cls) -> bool:
        """Check if the library is available."""
        instance = cls.get_instance()
        return instance is not None and instance._available

    def _load_library(self) -> None:
        """Load the native library from various search paths."""
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
        for path in search_paths:
            lib_file = Path(path) / library_name
            if lib_file.exists():
                try:
                    self._lib = ctypes.CDLL(str(lib_file))
                    self._setup_functions()
                    self._available = True
                    return
                except OSError as e:
                    if self._debug:
                        print(f"Failed to load from {path}: {e}", file=sys.stderr)

        # Try loading by name (system paths)
        try:
            self._lib = ctypes.CDLL(
                f"libgopher-orch.{'dylib' if sys.platform == 'darwin' else 'so'}"
            )
            self._setup_functions()
            self._available = True
            return
        except OSError as e:
            if self._debug:
                print(f"Failed to load gopher-orch library: {e}", file=sys.stderr)
                print("Searched paths:", file=sys.stderr)
                for path in search_paths:
                    print(f"  - {path}", file=sys.stderr)

        self._available = False

    def _setup_functions(self) -> None:
        """Set up function signatures for the native library."""
        if self._lib is None:
            return

        # Agent functions
        self._lib.gopher_orch_agent_create_by_json.argtypes = [
            c_char_p,
            c_char_p,
            c_char_p,
        ]
        self._lib.gopher_orch_agent_create_by_json.restype = GopherOrchHandle

        self._lib.gopher_orch_agent_create_by_api_key.argtypes = [
            c_char_p,
            c_char_p,
            c_char_p,
        ]
        self._lib.gopher_orch_agent_create_by_api_key.restype = GopherOrchHandle

        self._lib.gopher_orch_agent_run.argtypes = [GopherOrchHandle, c_char_p, c_int64]
        self._lib.gopher_orch_agent_run.restype = c_char_p

        self._lib.gopher_orch_agent_add_ref.argtypes = [GopherOrchHandle]
        self._lib.gopher_orch_agent_add_ref.restype = None

        self._lib.gopher_orch_agent_release.argtypes = [GopherOrchHandle]
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
        """Get the platform-specific library name."""
        if sys.platform == "darwin":
            return "libgopher-orch.dylib"
        elif sys.platform == "win32":
            return "gopher-orch.dll"
        else:
            return "libgopher-orch.so"

    def _get_search_paths(self) -> list:
        """Get the list of search paths for the native library."""
        # Get the directory containing this module
        module_dir = Path(__file__).parent.parent.parent

        paths = [
            # Project root native/lib
            str(Path.cwd() / "native" / "lib"),
            # Relative to module location
            str(module_dir / "native" / "lib"),
            str(module_dir.parent / "native" / "lib"),
        ]

        # System paths
        if sys.platform == "darwin":
            paths.extend(
                [
                    "/usr/local/lib",
                    "/opt/homebrew/lib",
                ]
            )
        paths.append("/usr/lib")

        return paths

    # Agent functions
    def agent_create_by_json(
        self, provider: str, model: str, server_json: str
    ) -> Optional[GopherOrchHandle]:
        """Create an agent with JSON server configuration."""
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
        """Create an agent with API key for fetching remote server config."""
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
        """Get the last error information."""
        if not self._available or self._lib is None:
            return None
        error_ptr = self._lib.gopher_orch_last_error()
        if error_ptr and error_ptr.contents:
            return error_ptr.contents
        return None

    def get_last_error_message(self) -> Optional[str]:
        """Get the last error message as a string."""
        error_info = self.last_error()
        if error_info and error_info.message:
            return error_info.message.decode("utf-8")
        return None

    def clear_error(self) -> None:
        """Clear the last error."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_clear_error()

    def free(self, ptr: c_void_p) -> None:
        """Free memory allocated by the native library."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_free(ptr)
