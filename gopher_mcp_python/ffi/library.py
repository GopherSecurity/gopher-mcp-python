"""
ctypes interface to the gopher-mcp-python native library.
"""

import ctypes
import os
import re
import sys
from ctypes import (
    CFUNCTYPE,
    POINTER,
    Structure,
    c_char_p,
    c_int32,
    c_int64,
    c_size_t,
    c_uint64,
    c_void_p,
)
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from gopher_mcp_python.errors import AgentError
from gopher_mcp_python.elicitation_runtime import (
    ELICITATION_ACTION_CANCEL,
    native_action_from_elicitation_action,
    resolve_elicitation_action_sync,
    to_elicitation_request,
)
from gopher_mcp_python.runtime_options import (
    GopherAgentRuntimeOptions,
    RuntimeOptionsInput,
    normalize_runtime_options,
)

# Type alias for opaque handle
GopherOrchHandle = c_void_p
MIN_ELICITATION_NATIVE_PACKAGE_VERSION = "0.1.35"


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


class GopherOrchHeader(Structure):
    """
    Header pair structure matching C:
    typedef struct {
        const char* name;
        const char* value;
    } gopher_orch_header_t;
    """

    _fields_ = [
        ("name", c_char_p),
        ("value", c_char_p),
    ]


class GopherOrchElicitationRequest(Structure):
    """
    Elicitation request structure matching C:
    typedef struct {
        const char* request_id_json;
        const char* elicitation_id;
        const char* mode;
        const char* message;
        const char* url;
        const char* raw_json;
        const char* raw_params_json;
    } gopher_orch_elicitation_request_t;
    """

    _fields_ = [
        ("request_id_json", c_char_p),
        ("elicitation_id", c_char_p),
        ("mode", c_char_p),
        ("message", c_char_p),
        ("url", c_char_p),
        ("raw_json", c_char_p),
        ("raw_params_json", c_char_p),
    ]


GopherOrchElicitationCallback = CFUNCTYPE(
    c_int32,
    POINTER(GopherOrchElicitationRequest),
    c_void_p,
)


class GopherOrchAgentOptions(Structure):
    """
    Agent runtime options structure matching C:
    typedef struct {
        const char* access_token;
        const gopher_orch_header_t* headers;
        gopher_orch_size_t header_count;
        const gopher_orch_server_agent_options_t* server_options;
        gopher_orch_size_t server_option_count;
        gopher_orch_elicitation_callback_t elicitation_callback;
        void* elicitation_user_data;
        gopher_orch_duration_ms_t elicitation_timeout_ms;
    } gopher_orch_agent_options_t;
    """

    _fields_ = [
        ("access_token", c_char_p),
        ("headers", POINTER(GopherOrchHeader)),
        ("header_count", c_size_t),
        ("server_options", c_void_p),
        ("server_option_count", c_size_t),
        ("elicitation_callback", c_void_p),
        ("elicitation_user_data", c_void_p),
        ("elicitation_timeout_ms", c_uint64),
    ]


class _AgentOptionsStorage:
    """Owns ctypes memory for a gopher_orch_agent_options_t call."""

    def __init__(
        self,
        options: GopherAgentRuntimeOptions,
        supports_elicitation: bool,
    ) -> None:
        self._bytes = []
        self.elicitation_callback = None

        access_token = options.access_token
        if access_token is not None:
            access_token_bytes = access_token.encode("utf-8")
            self._bytes.append(access_token_bytes)
        else:
            access_token_bytes = None

        header_items = list(options.headers.items())
        self.header_count = len(header_items)
        if header_items:
            self.header_array = (GopherOrchHeader * len(header_items))()
            for i, (name, value) in enumerate(header_items):
                name_bytes = name.encode("utf-8")
                value_bytes = value.encode("utf-8")
                # Keep c_char_p backing bytes alive; assigning the struct into
                # the array slot copies pointers, not Python-owned buffers.
                self._bytes.extend([name_bytes, value_bytes])
                self.header_array[i] = GopherOrchHeader(name_bytes, value_bytes)
            headers_ptr = self.header_array
        else:
            self.header_array = None
            headers_ptr = None

        elicitation = options.elicitation
        if elicitation is not None:
            if not supports_elicitation:
                raise AgentError(
                    "The loaded gopher-orch native library does not expose MCP "
                    "elicitation callback support. Rebuild or update "
                    "gopher-orch before using provider OAuth elicitation."
                )
            self.elicitation_callback = _create_elicitation_callback(elicitation)
            elicitation_timeout_ms = elicitation.timeout_ms or 0
        else:
            elicitation_timeout_ms = 0
        elicitation_callback_ptr = (
            ctypes.cast(self.elicitation_callback, c_void_p)
            if self.elicitation_callback is not None
            else None
        )

        self.options = GopherOrchAgentOptions(
            access_token_bytes,
            headers_ptr,
            self.header_count,
            None,
            0,
            elicitation_callback_ptr,
            None,
            elicitation_timeout_ms,
        )

    @property
    def pointer(self):
        return ctypes.byref(self.options)


class _RetainedAgentOptionsStorage:
    def __init__(self, storage: _AgentOptionsStorage) -> None:
        self.storage = storage
        self.ref_count = 1


class GopherOrchLibrary:
    """
    Wrapper for the gopher-mcp-python native library using ctypes.
    """

    _instance: Optional["GopherOrchLibrary"] = None
    _lib: Optional[ctypes.CDLL] = None
    _available: bool = False
    _debug: bool = False

    def __init__(self) -> None:
        self._load_errors = []
        self._loaded_library_path: Optional[str] = None
        self._loaded_native_package_version: Optional[str] = None
        self._agent_option_storage: Dict[int, _RetainedAgentOptionsStorage] = {}
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

    @classmethod
    def get_load_error_message(cls) -> str:
        """Return native library load diagnostics from the last load attempt."""
        instance = cls._instance
        if instance is None or not instance._load_errors:
            return "Native library not loaded."
        return "\n".join(instance._load_errors)

    def _load_library(self) -> None:
        self._debug = os.environ.get("DEBUG") is not None
        self._load_errors = []

        library_name = self._get_library_name()
        search_paths = self._get_search_paths()

        # Try custom path from environment variable. It may be either the
        # library file itself or a directory containing the platform library.
        env_path = os.environ.get("GOPHER_MCP_PYTHON_LIBRARY_PATH") or os.environ.get(
            "GOPHER_ORCH_LIBRARY_PATH"
        )
        env_lib_file = (
            self._resolve_library_path(env_path, library_name) if env_path else None
        )
        if env_lib_file:
            try:
                self._lib = ctypes.CDLL(env_lib_file)
                self._loaded_library_path = env_lib_file
                self._loaded_native_package_version = _native_version_from_path(
                    env_lib_file
                )
                self._setup_functions()
                self._available = True
                return
            except OSError as e:
                self._record_load_error(
                    f"Failed to load environment library path {env_lib_file}: {e}"
                )
                if self._debug:
                    print(
                        f"Failed to load from environment library path: {e}",
                        file=sys.stderr,
                    )
        elif env_path:
            self._record_load_error(
                f"Environment library path does not contain {library_name}: {env_path}"
            )

        # Try search paths
        for search_path in search_paths:
            lib_file = os.path.join(search_path, library_name)
            if os.path.exists(lib_file):
                try:
                    self._lib = ctypes.CDLL(lib_file)
                    self._loaded_library_path = lib_file
                    if self._loaded_native_package_version is None:
                        self._loaded_native_package_version = _native_version_from_path(
                            lib_file
                        )
                    self._setup_functions()
                    self._available = True
                    return
                except OSError as e:
                    self._record_load_error(f"Failed to load {lib_file}: {e}")
                    if self._debug:
                        print(
                            f"Failed to load from {search_path}: {e}", file=sys.stderr
                        )

        # Try loading by name (system paths)
        try:
            self._lib = ctypes.CDLL(library_name)
            self._loaded_library_path = library_name
            self._loaded_native_package_version = _native_version_from_path(
                library_name
            )
            self._setup_functions()
            self._available = True
            return
        except OSError as e:
            self._record_load_error(
                f"Failed to load {library_name} from system library paths: {e}"
            )
            if self._debug:
                print(f"Failed to load gopher-mcp-python library: {e}", file=sys.stderr)
                print("Searched paths:", file=sys.stderr)
                for p in search_paths:
                    print(f"  - {p}", file=sys.stderr)

        self._available = False

    def _resolve_library_path(self, candidate: str, library_name: str) -> Optional[str]:
        """Resolve a library file or a directory containing the library."""
        if not os.path.exists(candidate):
            return None

        if os.path.isfile(candidate):
            return candidate

        if not os.path.isdir(candidate):
            return None

        direct = os.path.join(candidate, library_name)
        if os.path.exists(direct):
            return direct

        matches = [
            name
            for name in os.listdir(candidate)
            if _library_version_key(name, library_name) is not None
        ]
        if not matches:
            return None

        matches.sort(
            key=lambda name: _library_version_key(name, library_name),
            reverse=True,
        )
        return os.path.join(candidate, matches[0])

    def _record_load_error(self, message: str) -> None:
        self._load_errors.append(message)

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
        self._bind_optional_agent_options_symbol(
            "gopher_orch_agent_create_by_json_with_options",
            [c_char_p, c_char_p, c_char_p, POINTER(GopherOrchAgentOptions)],
        )
        self._bind_optional_int_symbol(
            "gopher_orch_agent_options_supports_elicitation",
            [],
        )

        self._lib.gopher_orch_agent_create_by_api_key.argtypes = [
            c_char_p,
            c_char_p,
            c_char_p,
        ]
        self._lib.gopher_orch_agent_create_by_api_key.restype = c_void_p
        self._bind_optional_agent_options_symbol(
            "gopher_orch_agent_create_by_api_key_with_options",
            [c_char_p, c_char_p, c_char_p, POINTER(GopherOrchAgentOptions)],
        )

        # Routing factories: scope the agent to a single MCP server or gateway
        # selected by id / name, or to a known MCP URL. These C symbols landed
        # after the initial factories, so bind each one independently to keep
        # the SDK loadable against older libgopher-orch builds while still
        # configuring every symbol that is present.
        routing_factories = [
            (
                "gopher_orch_agent_create_by_server_id",
                [c_char_p, c_char_p, c_char_p, c_char_p],
                "gopher_orch_agent_create_by_server_id_with_options",
                [
                    c_char_p,
                    c_char_p,
                    c_char_p,
                    c_char_p,
                    POINTER(GopherOrchAgentOptions),
                ],
            ),
            (
                "gopher_orch_agent_create_by_server_name",
                [c_char_p, c_char_p, c_char_p, c_char_p],
                "gopher_orch_agent_create_by_server_name_with_options",
                [
                    c_char_p,
                    c_char_p,
                    c_char_p,
                    c_char_p,
                    POINTER(GopherOrchAgentOptions),
                ],
            ),
            (
                "gopher_orch_agent_create_by_gateway_id",
                [c_char_p, c_char_p, c_char_p, c_char_p],
                "gopher_orch_agent_create_by_gateway_id_with_options",
                [
                    c_char_p,
                    c_char_p,
                    c_char_p,
                    c_char_p,
                    POINTER(GopherOrchAgentOptions),
                ],
            ),
            (
                "gopher_orch_agent_create_by_gateway_name",
                [c_char_p, c_char_p, c_char_p, c_char_p],
                "gopher_orch_agent_create_by_gateway_name_with_options",
                [
                    c_char_p,
                    c_char_p,
                    c_char_p,
                    c_char_p,
                    POINTER(GopherOrchAgentOptions),
                ],
            ),
            (
                "gopher_orch_agent_create_by_url",
                [c_char_p, c_char_p, c_char_p],
                "gopher_orch_agent_create_by_url_with_options",
                [c_char_p, c_char_p, c_char_p, POINTER(GopherOrchAgentOptions)],
            ),
        ]
        for name, argtypes, options_name, options_argtypes in routing_factories:
            try:
                fn = getattr(self._lib, name)
            except AttributeError:
                pass
            else:
                fn.argtypes = argtypes
                fn.restype = c_void_p
            self._bind_optional_agent_options_symbol(options_name, options_argtypes)

        self._lib.gopher_orch_agent_run.argtypes = [c_void_p, c_char_p, c_int64]
        self._lib.gopher_orch_agent_run.restype = c_void_p

        self._lib.gopher_orch_agent_add_ref.argtypes = [c_void_p]
        self._lib.gopher_orch_agent_add_ref.restype = None

        self._lib.gopher_orch_agent_release.argtypes = [c_void_p]
        self._lib.gopher_orch_agent_release.restype = None

        # API functions
        self._lib.gopher_orch_api_fetch_servers.argtypes = [c_char_p]
        self._lib.gopher_orch_api_fetch_servers.restype = c_void_p

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

    def _bind_optional_agent_options_symbol(self, name: str, argtypes: list) -> None:
        if self._lib is None:
            return
        try:
            fn = getattr(self._lib, name)
            fn.argtypes = argtypes
            fn.restype = c_void_p
        except AttributeError:
            pass

    def _bind_optional_int_symbol(self, name: str, argtypes: list) -> None:
        if self._lib is None:
            return
        try:
            fn = getattr(self._lib, name)
            fn.argtypes = argtypes
            fn.restype = c_int32
        except AttributeError:
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
            self._loaded_native_package_version = getattr(native_pkg, "__version__", None)
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

    def _get_platform_native_dir_name(self) -> str:
        """Return the native build output directory name for this platform."""
        import platform as plat

        arch_map = {
            "arm64": "arm64",
            "aarch64": "arm64",
            "x86_64": "x64",
            "amd64": "x64",
            "x64": "x64",
        }
        arch = arch_map.get(plat.machine().lower(), plat.machine().lower())
        platform_map = {
            "darwin": "darwin",
            "linux": "linux",
            "win32": "win32",
        }
        platform_name = platform_map.get(sys.platform, sys.platform)
        return f"{platform_name}-{arch}"

    def _get_search_paths(self) -> list:
        paths = []

        # 1. Try platform-specific package (pip distribution)
        platform_path = self._get_platform_package_path()
        if platform_path:
            paths.append(platform_path)

        # 2. Get the directory containing this module for development fallbacks
        module_dir = Path(__file__).parent.parent.parent
        platform_native_dir = self._get_platform_native_dir_name()

        # Development paths (native/lib in various locations). Explicitly set
        # GOPHER_MCP_PYTHON_LIBRARY_PATH to force a local build.
        paths.extend(
            [
                os.path.join(os.getcwd(), "native", platform_native_dir, "lib"),
                os.path.join(os.getcwd(), "native", "current", "lib"),
                os.path.join(os.getcwd(), "native", "lib"),
                os.path.join(module_dir, "native", platform_native_dir, "lib"),
                os.path.join(module_dir, "native", "current", "lib"),
                os.path.join(module_dir, "native", "lib"),
                os.path.join(module_dir.parent, "native", platform_native_dir, "lib"),
                os.path.join(module_dir.parent, "native", "current", "lib"),
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
        self,
        provider: str,
        model: str,
        server_json: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> Optional[GopherOrchHandle]:
        """Create an agent using JSON server configuration."""
        if not self._available or self._lib is None:
            return None
        options = self._build_agent_options(runtime_options)
        if options is not None:
            fn = getattr(
                self._lib, "gopher_orch_agent_create_by_json_with_options", None
            )
            if fn is None:
                raise AgentError(self._missing_options_symbol_message())
            handle = fn(
                provider.encode("utf-8"),
                model.encode("utf-8"),
                server_json.encode("utf-8"),
                options.pointer,
            )
            self._retain_agent_option_storage(handle, options)
            return handle
        return self._lib.gopher_orch_agent_create_by_json(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            server_json.encode("utf-8"),
        )

    def agent_create_by_api_key(
        self,
        provider: str,
        model: str,
        api_key: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> Optional[GopherOrchHandle]:
        """Create an agent using API key."""
        if not self._available or self._lib is None:
            return None
        options = self._build_agent_options(runtime_options)
        if options is not None:
            fn = getattr(
                self._lib, "gopher_orch_agent_create_by_api_key_with_options", None
            )
            if fn is None:
                raise AgentError(self._missing_options_symbol_message())
            handle = fn(
                provider.encode("utf-8"),
                model.encode("utf-8"),
                api_key.encode("utf-8"),
                options.pointer,
            )
            self._retain_agent_option_storage(handle, options)
            return handle
        return self._lib.gopher_orch_agent_create_by_api_key(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
        )

    def agent_create_by_server_id(
        self,
        provider: str,
        model: str,
        api_key: str,
        server_id: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> Optional[GopherOrchHandle]:
        """Create an agent scoped to a single MCP server by id.

        The native side fetches server config from the Gopher API using the
        Bearer api key, appending "?serverId={server_id}" so the response
        carries only the matching MCP server entry.
        """
        if not self._available or self._lib is None:
            return None
        options = self._build_agent_options(runtime_options)
        if options is not None:
            fn = getattr(
                self._lib, "gopher_orch_agent_create_by_server_id_with_options", None
            )
            if fn is None:
                raise AgentError(self._missing_options_symbol_message())
            handle = fn(
                provider.encode("utf-8"),
                model.encode("utf-8"),
                api_key.encode("utf-8"),
                server_id.encode("utf-8"),
                options.pointer,
            )
            self._retain_agent_option_storage(handle, options)
            return handle
        fn = getattr(self._lib, "gopher_orch_agent_create_by_server_id", None)
        if fn is None:
            raise AgentError(_missing_routing_factory_message())
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
            server_id.encode("utf-8"),
        )

    def agent_create_by_server_name(
        self,
        provider: str,
        model: str,
        api_key: str,
        server_name: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> Optional[GopherOrchHandle]:
        """Create an agent scoped to a single MCP server by name.

        Mirrors agent_create_by_server_id but routes via "?serverName=".
        """
        if not self._available or self._lib is None:
            return None
        options = self._build_agent_options(runtime_options)
        if options is not None:
            fn = getattr(
                self._lib, "gopher_orch_agent_create_by_server_name_with_options", None
            )
            if fn is None:
                raise AgentError(self._missing_options_symbol_message())
            handle = fn(
                provider.encode("utf-8"),
                model.encode("utf-8"),
                api_key.encode("utf-8"),
                server_name.encode("utf-8"),
                options.pointer,
            )
            self._retain_agent_option_storage(handle, options)
            return handle
        fn = getattr(self._lib, "gopher_orch_agent_create_by_server_name", None)
        if fn is None:
            raise AgentError(_missing_routing_factory_message())
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
            server_name.encode("utf-8"),
        )

    def agent_create_by_gateway_id(
        self,
        provider: str,
        model: str,
        api_key: str,
        gateway_id: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> Optional[GopherOrchHandle]:
        """Create an agent scoped to a single MCP gateway by id.

        The native side appends "?gatewayId={gateway_id}" to the Gopher API
        fetch so the response carries the backing MCP servers for that
        gateway.
        """
        if not self._available or self._lib is None:
            return None
        options = self._build_agent_options(runtime_options)
        if options is not None:
            fn = getattr(
                self._lib, "gopher_orch_agent_create_by_gateway_id_with_options", None
            )
            if fn is None:
                raise AgentError(self._missing_options_symbol_message())
            handle = fn(
                provider.encode("utf-8"),
                model.encode("utf-8"),
                api_key.encode("utf-8"),
                gateway_id.encode("utf-8"),
                options.pointer,
            )
            self._retain_agent_option_storage(handle, options)
            return handle
        fn = getattr(self._lib, "gopher_orch_agent_create_by_gateway_id", None)
        if fn is None:
            raise AgentError(_missing_routing_factory_message())
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
            gateway_id.encode("utf-8"),
        )

    def agent_create_by_gateway_name(
        self,
        provider: str,
        model: str,
        api_key: str,
        gateway_name: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> Optional[GopherOrchHandle]:
        """Create an agent scoped to a single MCP gateway by name.

        Mirrors agent_create_by_gateway_id but routes via "?gatewayName=".
        """
        if not self._available or self._lib is None:
            return None
        options = self._build_agent_options(runtime_options)
        if options is not None:
            fn = getattr(
                self._lib,
                "gopher_orch_agent_create_by_gateway_name_with_options",
                None,
            )
            if fn is None:
                raise AgentError(self._missing_options_symbol_message())
            handle = fn(
                provider.encode("utf-8"),
                model.encode("utf-8"),
                api_key.encode("utf-8"),
                gateway_name.encode("utf-8"),
                options.pointer,
            )
            self._retain_agent_option_storage(handle, options)
            return handle
        fn = getattr(self._lib, "gopher_orch_agent_create_by_gateway_name", None)
        if fn is None:
            raise AgentError(_missing_routing_factory_message())
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            api_key.encode("utf-8"),
            gateway_name.encode("utf-8"),
        )

    def agent_create_by_url(
        self,
        provider: str,
        model: str,
        url: str,
        runtime_options: RuntimeOptionsInput = None,
    ) -> Optional[GopherOrchHandle]:
        """Create an agent for a single MCP server reachable at a URL.

        Skips the remote config fetch: the native side synthesises an
        http_sse server entry around the URL. Useful for local development
        or one-off endpoints where the operator already knows the URL.
        """
        if not self._available or self._lib is None:
            return None
        options = self._build_agent_options(runtime_options)
        if options is not None:
            fn = getattr(self._lib, "gopher_orch_agent_create_by_url_with_options", None)
            if fn is None:
                raise AgentError(self._missing_options_symbol_message())
            handle = fn(
                provider.encode("utf-8"),
                model.encode("utf-8"),
                url.encode("utf-8"),
                options.pointer,
            )
            self._retain_agent_option_storage(handle, options)
            return handle
        fn = getattr(self._lib, "gopher_orch_agent_create_by_url", None)
        if fn is None:
            raise AgentError(_missing_routing_factory_message())
        return fn(
            provider.encode("utf-8"),
            model.encode("utf-8"),
            url.encode("utf-8"),
        )

    def _build_agent_options(
        self, runtime_options: RuntimeOptionsInput
    ) -> Optional[_AgentOptionsStorage]:
        options = normalize_runtime_options(runtime_options)
        if options is None:
            return None
        # Native BuildAgentOptions deep-copies this struct into C++ strings/maps
        # during creation. Elicitation callback storage is retained separately
        # for the agent lifetime because native stores that function pointer.
        return _AgentOptionsStorage(
            options,
            self._supports_elicitation_callback_options(),
        )

    def _supports_elicitation_callback_options(self) -> bool:
        if self._lib is not None:
            fn = getattr(
                self._lib,
                "gopher_orch_agent_options_supports_elicitation",
                None,
            )
            if fn is not None:
                return bool(fn())
        return _version_at_least(
            getattr(self, "_loaded_native_package_version", None),
            MIN_ELICITATION_NATIVE_PACKAGE_VERSION,
        )

    def _retain_agent_option_storage(
        self,
        handle: Optional[GopherOrchHandle],
        options: Optional[_AgentOptionsStorage],
    ) -> None:
        if handle is None or options is None or options.elicitation_callback is None:
            return
        storage = getattr(self, "_agent_option_storage", None)
        if storage is None:
            storage = {}
            self._agent_option_storage = storage
        key = _handle_key(handle)
        if key is not None:
            storage[key] = _RetainedAgentOptionsStorage(options)

    def _add_ref_agent_option_storage(self, handle: GopherOrchHandle) -> None:
        storage = getattr(self, "_agent_option_storage", None)
        if storage is None:
            return
        key = _handle_key(handle)
        if key is None:
            return
        retained = storage.get(key)
        if retained is not None:
            retained.ref_count += 1

    def _release_agent_option_storage(self, handle: GopherOrchHandle) -> None:
        storage = getattr(self, "_agent_option_storage", None)
        if storage is None:
            return
        key = _handle_key(handle)
        if key is not None:
            retained = storage.get(key)
            if retained is None:
                return
            retained.ref_count -= 1
            if retained.ref_count <= 0:
                storage.pop(key, None)

    def _missing_options_symbol_message(self) -> str:
        return (
            "The loaded gopher-orch native library does not expose agent runtime "
            "options. Rebuild or update gopher-orch before passing access_token "
            "or headers."
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
        return self._decode_owned_c_string(result)

    def agent_add_ref(self, agent: GopherOrchHandle) -> None:
        """Add a reference to the agent."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_agent_add_ref(agent)
            self._add_ref_agent_option_storage(agent)

    def agent_release(self, agent: GopherOrchHandle) -> None:
        """Release the agent."""
        if self._available and self._lib is not None:
            try:
                self._lib.gopher_orch_agent_release(agent)
            finally:
                self._release_agent_option_storage(agent)

    # API functions
    def api_fetch_servers(self, api_key: str) -> Optional[str]:
        """Fetch server configuration from API."""
        if not self._available or self._lib is None:
            return None
        result = self._lib.gopher_orch_api_fetch_servers(api_key.encode("utf-8"))
        return self._decode_owned_c_string(result)

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
            message = error_info.message.decode("utf-8")
            if error_info.details:
                details = error_info.details.decode("utf-8")
                return f"{message}: {details}"
            return message
        return None

    def clear_error(self) -> None:
        """Clear the last error."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_clear_error()

    def free(self, ptr: Any) -> None:
        """Free memory allocated by the library."""
        if self._available and self._lib is not None:
            self._lib.gopher_orch_free(ptr)

    def _decode_owned_c_string(self, ptr: Any) -> Optional[str]:
        """Decode an owned native string and always release it."""
        if not ptr:
            return None
        try:
            return ctypes.string_at(ptr).decode("utf-8")
        finally:
            self.free(ptr)

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


def _missing_routing_factory_message() -> str:
    return (
        "this build of libgopher-orch predates the routing factories; "
        "upgrade to a native gopher-orch library release that includes them"
    )


def _create_elicitation_callback(options):
    @GopherOrchElicitationCallback
    def callback(request_ptr, user_data):
        try:
            if not request_ptr:
                return ELICITATION_ACTION_CANCEL
            request = request_ptr.contents
            action = resolve_elicitation_action_sync(
                options,
                to_elicitation_request(
                    {
                        "request_id_json": _decode_optional_c_string(
                            request.request_id_json
                        ),
                        "elicitation_id": _decode_optional_c_string(
                            request.elicitation_id
                        ),
                        "mode": _decode_optional_c_string(request.mode),
                        "message": _decode_optional_c_string(request.message),
                        "url": _decode_optional_c_string(request.url),
                        "raw_json": _decode_optional_c_string(request.raw_json),
                        "raw_params_json": _decode_optional_c_string(
                            request.raw_params_json
                        ),
                    }
                ),
            )
            return native_action_from_elicitation_action(action)
        except Exception as exc:
            print(f"MCP elicitation handler failed: {exc}", file=sys.stderr)
            return ELICITATION_ACTION_CANCEL

    return callback


def _decode_optional_c_string(value) -> Optional[str]:
    if not value:
        return None
    return value.decode("utf-8")


def _handle_key(handle: Any) -> Optional[int]:
    if handle is None:
        return None
    if isinstance(handle, c_void_p):
        return int(handle.value) if handle.value else None
    try:
        return int(handle)
    except (TypeError, ValueError):
        return None


def _native_version_from_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    name = os.path.basename(path)
    parts = _parse_library_version(name)
    return ".".join(str(part) for part in parts) if parts != (0,) else None


def _version_at_least(
    version: Optional[str],
    minimum: str,
) -> bool:
    actual_parts = _parse_library_version(version or "")
    minimum_parts = _parse_library_version(minimum)
    length = max(len(actual_parts), len(minimum_parts))
    actual = actual_parts + (0,) * (length - len(actual_parts))
    required = minimum_parts + (0,) * (length - len(minimum_parts))
    return actual >= required


def _library_version_key(
    filename: str, library_name: str
) -> Optional[Tuple[int, Tuple[int, ...], str]]:
    """
    Return a sortable key for versioned variants of library_name.

    Exact library_name is handled before this helper. Linux uses
    libname.so.X.Y.Z; macOS uses libname.X.Y.Z.dylib.
    """
    linux_prefix = f"{library_name}."
    if filename.startswith(linux_prefix):
        version = filename[len(linux_prefix) :]
        return (1, _parse_library_version(version), filename)

    dylib_suffix = ".dylib"
    if library_name.endswith(dylib_suffix) and filename.endswith(dylib_suffix):
        stem = library_name[: -len(dylib_suffix)]
        versioned_prefix = f"{stem}."
        if filename.startswith(versioned_prefix):
            version = filename[len(versioned_prefix) : -len(dylib_suffix)]
            return (1, _parse_library_version(version), filename)

    return None


def _parse_library_version(version: str) -> Tuple[int, ...]:
    parts = re.findall(r"\d+", version)
    return tuple(int(part) for part in parts) if parts else (0,)
