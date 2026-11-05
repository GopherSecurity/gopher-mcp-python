"""
GopherSessionManager - FFI wrapper for per-client session management.

Thread-safe session manager with OAuth token storage, expiry tracking,
and secure session ID generation.
"""

from ._lifecycle import NativeHandleOwner, native_constructor, native_operation
from ._memory import read_owned_string

from ctypes import POINTER, byref, c_bool, c_char_p, c_void_p
from typing import Optional

from gopher_mcp_python.ffi.auth.loader import (
    get_auth_functions,
    is_auth_available,
    load_library,
)
from gopher_mcp_python.ffi.auth.types import GopherAuthError


class GopherSessionManager(NativeHandleOwner):
    """Per-client session manager via native C API."""

    _destroy_function = "session_manager_destroy"

    @native_constructor
    def __init__(self, timeout_seconds: int = 300) -> None:
        if not is_auth_available():
            load_library()
        funcs = get_auth_functions()
        create = funcs.get("session_manager_create")
        if not create:
            raise RuntimeError("Session manager functions not available")
        self._handle = c_void_p()
        result = create(byref(self._handle), timeout_seconds)
        if result != GopherAuthError.SUCCESS:
            raise RuntimeError(f"Failed to create session manager: error {result}")
        self._destroyed = False

    @native_operation
    def store_token(
        self, session_id: str, access_token: str, refresh_token: str, expires_in: int
    ) -> None:
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        fn = funcs.get("session_store_token")
        if fn:
            fn(
                self._handle,
                session_id.encode("utf-8"),
                access_token.encode("utf-8"),
                refresh_token.encode("utf-8"),
                expires_in,
            )

    @native_operation
    def get_access_token(self, session_id: str) -> Optional[str]:
        return read_owned_string(
            get_auth_functions(),
            "session_get_access_token",
            self._handle,
            session_id.encode("utf-8"),
        )

    @native_operation
    def get_refresh_token(self, session_id: str) -> Optional[str]:
        return read_owned_string(
            get_auth_functions(),
            "session_get_refresh_token",
            self._handle,
            session_id.encode("utf-8"),
        )

    @native_operation
    def has_valid_token(self, session_id: str) -> bool:
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        fn = funcs.get("session_has_valid_token")
        if not fn:
            return False
        out = c_bool(False)
        fn(self._handle, session_id.encode("utf-8"), byref(out))
        return out.value

    @native_operation
    def cleanup(self) -> None:
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        fn = funcs.get("session_cleanup")
        if fn:
            fn(self._handle)

    @staticmethod
    @native_operation
    def generate_session_id() -> str:
        if not is_auth_available():
            load_library()
        value = read_owned_string(get_auth_functions(), "session_generate_id")
        if not value:
            raise RuntimeError("Failed to generate session ID")
        return value

    @native_operation
    def get_handle(self) -> c_void_p:
        self._ensure_not_destroyed()
        return self._handle

    def destroy(self) -> None:
        """Wait for active calls and release the handle exactly once."""
        self._destroy_handle()

    def is_destroyed(self) -> bool:
        return self._is_handle_destroyed()

    def __enter__(self) -> "GopherSessionManager":
        return self

    def __exit__(self, *args: object) -> None:
        self.destroy()

    def _ensure_not_destroyed(self) -> None:
        if self._destroyed:
            raise RuntimeError("GopherSessionManager has been destroyed")
