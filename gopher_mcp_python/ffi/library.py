"""
ctypes interface to the gopher-mcp-python native library.
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
    Wrapper for the gopher-mcp-python native library using ctypes.
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
        env_path = os.environ.get("GOPHER_MCP_PYTHON_LIBRARY_PATH")
        if env_path and os.path.exists(env_path):
            try:
                self._lib = ctypes.CDLL(env_path)
                self._setup_functions()
                self._available = True
                return
            except OSError as e:
                if self._debug:
                    print(
                        f"Failed to load from GOPHER_MCP_PYTHON_LIBRARY_PATH: {e}",
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
                        print(
                            f"Failed to load from {search_path}: {e}", file=sys.stderr
                        )

        # Try loading by name (system paths)
        try:
            self._lib = ctypes.CDLL(library_name)
            self._setup_functions()
            self._available = True
            return
        except OSError as e:
            if self._debug:
                print(f"Failed to load gopher-mcp-python library: {e}", file=sys.stderr)
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

        # Routing factories: scope the agent to a single MCP server or gateway
        # selected by id / name, or to a known MCP URL. These C symbols landed
        # in gopher-orch 0.1.23, so bind each one independently to keep the SDK
        # loadable against older libgopher-orch builds while still configuring
        # every symbol that is present.
        routing_factories = [
            (
                "gopher_orch_agent_create_by_server_id",
                [c_char_p, c_char_p, c_char_p, c_char_p],
                c_void_p,
            ),
            (
                "gopher_orch_agent_create_by_server_name",
                [c_char_p, c_char_p, c_char_p, c_char_p],
                c_void_p,
            ),
            (
                "gopher_orch_agent_create_by_gateway_id",
                [c_char_p, c_char_p, c_char_p, c_char_p],
                c_void_p,
            ),
            (
                "gopher_orch_agent_create_by_gateway_name",
                [c_char_p, c_char_p, c_char_p, c_char_p],
                c_void_p,
            ),
            (
                "gopher_orch_agent_create_by_url",
                [c_char_p, c_char_p, c_char_p],
                c_void_p,
            ),
        ]
        for name, argtypes, restype in routing_factories:
            try:
                fn = getattr(self._lib, name)
            except AttributeError:
                continue
            fn.argtypes = argtypes
            fn.restype = restype

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

        # Logging functions (optional - may not exist in all versions)
        try:
            self._lib.gopher_orch_set_log_level.argtypes = [c_int32]
            self._lib.gopher_orch_set_log_level.restype = None
            # Set default log level to Warning (3) for production use
            # This suppresses debug and info logs that appear during normal operation
            self._lib.gopher_orch_set_log_level(3)
        except AttributeError:
            # Function not available in this version of the library
            pass

    def _get_library_name(self) -> str:
        if sys.platform == "darwin":
            return "libgopher-orch.dylib"
        elif sys.platform == "win32":
            return "gopher-orch.dll"
        else:
            return "libgopher-orch.so"

    def _get_platform_package_path(self) -> Optional[str]:
        """
        Get the path to the platform-specific native package.
        These packages are published as gopher-mcp-python-native-{platform}-{arch}
        and contain the native library for that specific platform.
        """
        import platform as plat

        # Determine platform and architecture
        system = sys.platform  # 'darwin', 'linux', 'win32'
        machine = plat.machine().lower()  # 'arm64', 'x86_64', 'amd64'

        # Map machine names to our arch names
        arch_map = {
            "arm64": "arm64",
            "aarch64": "arm64",
            "x86_64": "x64",
            "amd64": "x64",
            "x64": "x64",
        }
        arch = arch_map.get(machine)
        if not arch:
            if self._debug:
                print(f"Unsupported architecture: {machine}", file=sys.stderr)
            return None

        # Map platform names
        platform_map = {
            "darwin": "darwin",
            "linux": "linux",
            "win32": "win32",
        }
        platform_name = platform_map.get(system)
        if not platform_name:
            if self._debug:
                print(f"Unsupported platform: {system}", file=sys.stderr)
            return None

        # Construct the package name
        package_name = f"gopher_mcp_python_native_{platform_name}_{arch}"

        try:
            # Try to import the platform-specific package
            native_pkg = __import__(package_name)
            lib_path = native_pkg.get_lib_path()
            if lib_path.exists():
                if self._debug:
                    print(f"Found platform package at: {lib_path}", file=sys.stderr)
                return str(lib_path)
        except ImportError:
            # Package not installed - this is expected on platforms where
            # the package wasn't installed
            if self._debug:
                print(f"Platform package {package_name} not found", file=sys.stderr)

        return None

    def _get_search_paths(self) -> list:
        paths = []

        # 1. Try platform-specific package first (pip distribution)
        platform_path = self._get_platform_package_path()
        if platform_path:
            paths.append(platform_path)

        # 2. Get the directory containing this module for development fallbacks
        module_dir = Path(__file__).parent.parent.parent

        # Development paths (native/lib in various locations)
        paths.extend(
            [
                # Project root native/lib
                os.path.join(os.getcwd(), "native", "lib"),
                # Relative to module location
                os.path.join(module_dir, "native", "lib"),
                os.path.join(module_dir.parent, "native", "lib"),
            ]
        )

        # 3. System paths as last resort
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

    def agent_create_by_server_id(
        self, provider: str, model: str, api_key: str, server_id: str
    ) -> Optional[GopherOrchHandle]:
        """Create an agent scoped to a single MCP server by id.

        The native side fetches server config from the Gopher API using the
        Bearer api key, appending "?serverId={server_id}" so the response
        carries only the matching MCP server entry.
        """
        if not self._available or self._lib is None:
            return None
        fn = getattr(self._lib, "gopher_orch_agent_create_by_server_id", None)
        if fn is None:
            return None
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
            server_id.encode("utf-8"),
        )

    def agent_create_by_server_name(
        self, provider: str, model: str, api_key: str, server_name: str
    ) -> Optional[GopherOrchHandle]:
        """Create an agent scoped to a single MCP server by name.

        Mirrors agent_create_by_server_id but routes via "?serverName=".
        """
        if not self._available or self._lib is None:
            return None
        fn = getattr(self._lib, "gopher_orch_agent_create_by_server_name", None)
        if fn is None:
            return None
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
            server_name.encode("utf-8"),
        )

    def agent_create_by_gateway_id(
        self, provider: str, model: str, api_key: str, gateway_id: str
    ) -> Optional[GopherOrchHandle]:
        """Create an agent scoped to a single MCP gateway by id.

        The native side appends "?gatewayId={gateway_id}" to the Gopher API
        fetch so the response carries the backing MCP servers for that
        gateway.
        """
        if not self._available or self._lib is None:
            return None
        fn = getattr(self._lib, "gopher_orch_agent_create_by_gateway_id", None)
        if fn is None:
            return None
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
            gateway_id.encode("utf-8"),
        )

    def agent_create_by_gateway_name(
        self, provider: str, model: str, api_key: str, gateway_name: str
    ) -> Optional[GopherOrchHandle]:
        """Create an agent scoped to a single MCP gateway by name.

        Mirrors agent_create_by_gateway_id but routes via "?gatewayName=".
        """
        if not self._available or self._lib is None:
            return None
        fn = getattr(self._lib, "gopher_orch_agent_create_by_gateway_name", None)
        if fn is None:
            return None
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
            gateway_name.encode("utf-8"),
        )

    def agent_create_by_url(
        self, provider: str, model: str, url: str
    ) -> Optional[GopherOrchHandle]:
        """Create an agent for a single MCP server reachable at a URL.

        Skips the remote config fetch: the native side synthesises an
        http_sse server entry around the URL. Useful for local development
        or one-off endpoints where the operator already knows the URL.
        """
        if not self._available or self._lib is None:
            return None
        fn = getattr(self._lib, "gopher_orch_agent_create_by_url", None)
        if fn is None:
            return None
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            url.encode("utf-8"),
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

    def set_log_level(self, level: int) -> None:
        """
        Set the global log level for the native library.

        Log levels:
            0 = Debug (most verbose)
            1 = Info
            2 = Notice
            3 = Warning (default for production)
            4 = Error
            5 = Critical
            6 = Alert
            7 = Emergency
            8 = Off (no logging)

        Args:
            level: Log level (0-8)
        """
        if self._available and self._lib is not None:
            self._lib.gopher_orch_set_log_level(level)
