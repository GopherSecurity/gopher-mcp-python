"""
GopherAuthConfig - High-level wrapper for auth configuration loading.

Provides a Pythonic API for loading auth server configuration from files,
environment variables, or inline key-value pairs. Uses the C++ core
ConfigLoader which handles INI parsing, Keycloak endpoint derivation,
and validation.
"""

from ._lifecycle import NativeHandleOwner, native_constructor, native_operation
from ._memory import read_owned_string

from ctypes import POINTER, byref, c_bool, c_char_p, c_int, c_void_p
from typing import Dict, List, Optional

from gopher_mcp_python.ffi.auth.loader import (
    get_auth_functions,
    is_auth_available,
    load_library,
)
from gopher_mcp_python.ffi.auth.types import GopherAuthError


class GopherAuthConfig(NativeHandleOwner):
    """Auth server configuration loaded via native ConfigLoader."""

    _destroy_function = "config_destroy"

    @native_constructor
    def __init__(self, handle: c_void_p) -> None:
        self._handle = handle
        self._destroyed = False

    @staticmethod
    @native_operation
    def load_file(filepath: str) -> "GopherAuthConfig":
        """
        Load configuration from an INI-style config file.

        After loading, Keycloak endpoints are auto-derived from
        auth_server_url if not explicitly set.

        Args:
            filepath: Path to config file.

        Returns:
            GopherAuthConfig instance.

        Raises:
            RuntimeError: If file not found or validation fails.
        """
        return _load_config(
            "config_load_file",
            (filepath.encode("utf-8"),),
            f"Failed to load config file: {filepath}",
        )

    @staticmethod
    @native_operation
    def load_env() -> "GopherAuthConfig":
        """
        Load configuration from environment variables.

        Returns:
            GopherAuthConfig instance.
        """
        # Environment loading historically permits incomplete configuration.
        return _load_config(
            "config_load_env",
            (),
            "Failed to load config from environment",
            require_valid=False,
        )

    @staticmethod
    @native_operation
    def load_from_pairs(pairs: Dict[str, str]) -> "GopherAuthConfig":
        """
        Load configuration from inline key-value pairs.

        Args:
            pairs: Dictionary of config keys to values.

        Returns:
            GopherAuthConfig instance.
        """
        count = len(pairs)
        keys = (c_char_p * count)(*(key.encode("utf-8") for key in pairs))
        values = (c_char_p * count)(
            *(value.encode("utf-8") for value in pairs.values())
        )
        return _load_config(
            "config_load_from_pairs",
            (keys, values, count),
            "Failed to load config from pairs",
        )

    @native_operation
    def get_string(self, key: str) -> str:
        """Get a string configuration value."""
        return read_owned_string(
            get_auth_functions(),
            "config_get_string",
            self._handle,
            key.encode("utf-8"),
            default="",
        )

    @native_operation
    def get_int(self, key: str) -> int:
        """Get an integer configuration value."""
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        getter = funcs.get("config_get_int")
        if not getter:
            return 0

        value_out = c_int(0)
        getter(self._handle, key.encode("utf-8"), byref(value_out))
        return value_out.value

    @native_operation
    def get_bool(self, key: str) -> bool:
        """Get a boolean configuration value."""
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        getter = funcs.get("config_get_bool")
        if not getter:
            return False

        value_out = c_bool(False)
        getter(self._handle, key.encode("utf-8"), byref(value_out))
        return value_out.value

    @native_operation
    def get_exchange_idps(self) -> List[str]:
        """Get exchange IDPs as a list (splits CSV from C API)."""
        csv = read_owned_string(
            get_auth_functions(), "config_get_exchange_idps", self._handle, default=""
        )
        return [value.strip() for value in csv.split(",") if value.strip()]

    @native_operation
    def get_handle(self) -> c_void_p:
        """Get the native config handle (for internal use)."""
        self._ensure_not_destroyed()
        return self._handle

    def destroy(self) -> None:
        """Wait for active calls and release the handle exactly once."""
        self._destroy_handle()

    def is_destroyed(self) -> bool:
        return self._is_handle_destroyed()

    def __enter__(self) -> "GopherAuthConfig":
        return self

    def __exit__(self, *args: object) -> None:
        self.destroy()

    def _ensure_not_destroyed(self) -> None:
        if self._destroyed:
            raise RuntimeError("GopherAuthConfig has been destroyed")


def _load_config(name, args, message, require_valid=True):
    if not is_auth_available():
        load_library()
    funcs = get_auth_functions()
    create = funcs.get("config_create")
    load = funcs.get(name)
    validate = funcs.get("config_validate")
    if not create or not load or not validate:
        raise RuntimeError("Config functions not available")
    handle = c_void_p()
    transferred = False
    try:
        if create(byref(handle)) != GopherAuthError.SUCCESS:
            raise RuntimeError("Failed to create config handle")
        if load(handle, *args) != GopherAuthError.SUCCESS:
            raise RuntimeError(message)
        if validate(handle) != GopherAuthError.SUCCESS and require_valid:
            disabled = c_bool(False)
            get_bool = funcs.get("config_get_bool")
            if get_bool:
                get_bool(handle, b"auth_disabled", byref(disabled))
            if not disabled.value:
                raise RuntimeError("Configuration validation failed")
        config = GopherAuthConfig(handle)
        transferred = True
        return config
    finally:
        destroy = funcs.get("config_destroy")
        if handle and not transferred and destroy:
            destroy(handle)
