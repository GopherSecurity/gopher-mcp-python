"""
GopherAuthConfig - High-level wrapper for auth configuration loading.

Provides a Pythonic API for loading auth server configuration from files,
environment variables, or inline key-value pairs. Uses the C++ core
ConfigLoader which handles INI parsing, Keycloak endpoint derivation,
and validation.
"""

from ctypes import POINTER, byref, c_bool, c_char_p, c_int, c_void_p
from typing import Dict, List, Optional

from gopher_mcp_python.ffi.auth.loader import (
    get_auth_functions,
    is_auth_available,
    load_library,
)
from gopher_mcp_python.ffi.auth.types import GopherAuthError


class GopherAuthConfig:
    """Auth server configuration loaded via native ConfigLoader."""

    def __init__(self, handle: c_void_p) -> None:
        self._handle = handle
        self._destroyed = False

    @staticmethod
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
        if not is_auth_available():
            load_library()

        funcs = get_auth_functions()
        create = funcs.get("config_create")
        load = funcs.get("config_load_file")
        validate = funcs.get("config_validate")

        if not create or not load or not validate:
            raise RuntimeError("Config functions not available")

        handle = c_void_p()
        result = create(byref(handle))
        if result != GopherAuthError.SUCCESS:
            raise RuntimeError("Failed to create config handle")

        result = load(handle, filepath.encode("utf-8"))
        if result != GopherAuthError.SUCCESS:
            funcs["config_destroy"](handle)
            raise RuntimeError(f"Failed to load config file: {filepath}")

        result = validate(handle)
        if result != GopherAuthError.SUCCESS:
            # Check if auth is disabled (validation is skipped)
            get_bool = funcs.get("config_get_bool")
            if get_bool:
                disabled = c_bool(False)
                get_bool(handle, b"auth_disabled", byref(disabled))
                if not disabled.value:
                    funcs["config_destroy"](handle)
                    raise RuntimeError("Configuration validation failed")

        return GopherAuthConfig(handle)

    @staticmethod
    def load_env() -> "GopherAuthConfig":
        """
        Load configuration from environment variables.

        Returns:
            GopherAuthConfig instance.
        """
        if not is_auth_available():
            load_library()

        funcs = get_auth_functions()
        create = funcs.get("config_create")
        load_env = funcs.get("config_load_env")
        validate = funcs.get("config_validate")

        if not create or not load_env or not validate:
            raise RuntimeError("Config functions not available")

        handle = c_void_p()
        result = create(byref(handle))
        if result != GopherAuthError.SUCCESS:
            raise RuntimeError("Failed to create config handle")

        load_env(handle)
        validate(handle)

        return GopherAuthConfig(handle)

    @staticmethod
    def load_from_pairs(pairs: Dict[str, str]) -> "GopherAuthConfig":
        """
        Load configuration from inline key-value pairs.

        Args:
            pairs: Dictionary of config keys to values.

        Returns:
            GopherAuthConfig instance.
        """
        if not is_auth_available():
            load_library()

        funcs = get_auth_functions()
        create = funcs.get("config_create")
        load_pairs = funcs.get("config_load_from_pairs")
        validate = funcs.get("config_validate")

        if not create or not load_pairs or not validate:
            raise RuntimeError("Config functions not available")

        handle = c_void_p()
        result = create(byref(handle))
        if result != GopherAuthError.SUCCESS:
            raise RuntimeError("Failed to create config handle")

        keys = list(pairs.keys())
        values = [pairs[k] for k in keys]
        count = len(keys)

        # Build ctypes arrays
        keys_arr = (c_char_p * count)(*(k.encode("utf-8") for k in keys))
        values_arr = (c_char_p * count)(*(v.encode("utf-8") for v in values))

        result = load_pairs(handle, keys_arr, values_arr, count)
        if result != GopherAuthError.SUCCESS:
            funcs["config_destroy"](handle)
            raise RuntimeError("Failed to load config from pairs")

        result = validate(handle)
        if result != GopherAuthError.SUCCESS:
            get_bool = funcs.get("config_get_bool")
            if get_bool:
                disabled = c_bool(False)
                get_bool(handle, b"auth_disabled", byref(disabled))
                if not disabled.value:
                    funcs["config_destroy"](handle)
                    raise RuntimeError("Configuration validation failed")

        return GopherAuthConfig(handle)

    def get_string(self, key: str) -> str:
        """Get a string configuration value."""
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        getter = funcs.get("config_get_string")
        if not getter:
            return ""

        value_out = c_char_p()
        result = getter(self._handle, key.encode("utf-8"), byref(value_out))
        if result != GopherAuthError.SUCCESS:
            return ""

        if value_out.value:
            val = value_out.value.decode("utf-8")
            free_string = funcs.get("free_string")
            if free_string:
                free_string(value_out)
            return val
        return ""

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

    def get_exchange_idps(self) -> List[str]:
        """Get exchange IDPs as a list (splits CSV from C API)."""
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        getter = funcs.get("config_get_exchange_idps")
        if not getter:
            return []

        value_out = c_char_p()
        result = getter(self._handle, byref(value_out))
        if result != GopherAuthError.SUCCESS or not value_out.value:
            return []

        csv = value_out.value.decode("utf-8")
        free_string = funcs.get("free_string")
        if free_string:
            free_string(value_out)

        if not csv.strip():
            return []
        return [s.strip() for s in csv.split(",") if s.strip()]

    def get_handle(self) -> c_void_p:
        """Get the native config handle (for internal use)."""
        self._ensure_not_destroyed()
        return self._handle

    def destroy(self) -> None:
        """Destroy the config and release resources. Idempotent."""
        if self._destroyed or not self._handle:
            return
        funcs = get_auth_functions()
        destroy = funcs.get("config_destroy")
        if destroy:
            destroy(self._handle)
        self._handle = None
        self._destroyed = True

    def is_destroyed(self) -> bool:
        """Check if the config has been destroyed."""
        return self._destroyed

    def __enter__(self) -> "GopherAuthConfig":
        return self

    def __exit__(self, *args: object) -> None:
        self.destroy()

    def _ensure_not_destroyed(self) -> None:
        if self._destroyed:
            raise RuntimeError("GopherAuthConfig has been destroyed")
