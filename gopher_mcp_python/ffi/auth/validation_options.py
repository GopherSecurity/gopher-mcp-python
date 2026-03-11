"""
ValidationOptions - Configuration for token validation.

Provides a fluent API for configuring JWT token validation options
such as required scopes, audience, and clock skew tolerance.
"""

from ctypes import byref, c_void_p
from typing import List, Optional, TYPE_CHECKING

from gopher_mcp_python.ffi.auth.loader import (
    load_library,
    get_auth_functions,
    is_auth_available,
    GopherAuthOptionsPtr,
)
from gopher_mcp_python.ffi.auth.types import GopherAuthError


class GopherValidationOptions:
    """
    Configuration options for JWT token validation.

    Provides a fluent API for setting validation parameters like
    required scopes, audience, and clock skew tolerance.

    Usage:
        # Using context manager (recommended)
        with GopherValidationOptions() as options:
            options.set_scopes(["read", "write"]).set_audience("my-api")
            result = client.validate_token(token, options)

        # Manual lifecycle management
        options = GopherValidationOptions()
        try:
            options.set_scopes(["read"])
            result = client.validate_token(token, options)
        finally:
            options.destroy()

        # Using factory function with defaults
        options = gopher_create_validation_options(clock_skew=60)
    """

    def __init__(self) -> None:
        """
        Create a new ValidationOptions instance.

        Raises:
            RuntimeError: If the library is not loaded or auth is not available.
        """
        self._handle: Optional[c_void_p] = None
        self._destroyed: bool = False

        if not load_library():
            raise RuntimeError("Failed to load gopher-orch library")

        if not is_auth_available():
            raise RuntimeError("Auth functions not available in library")

        funcs = get_auth_functions()
        options_create = funcs.get("options_create")
        if options_create is None:
            raise RuntimeError("options_create function not available")

        handle = c_void_p()
        result = options_create(byref(handle))

        if result != GopherAuthError.SUCCESS:
            raise RuntimeError(f"Failed to create validation options: error {result}")

        self._handle = handle

    def set_scopes(self, scopes: List[str]) -> "GopherValidationOptions":
        """
        Set the required scopes for token validation.

        Args:
            scopes: List of scope strings that the token must have.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If the options have been destroyed or function unavailable.
        """
        self._ensure_not_destroyed()

        funcs = get_auth_functions()
        options_set_scopes = funcs.get("options_set_scopes")
        if options_set_scopes is None:
            raise RuntimeError("options_set_scopes function not available")

        # Join scopes with space separator
        scopes_str = " ".join(scopes)
        options_set_scopes(self._handle, scopes_str.encode("utf-8"))

        return self

    def set_audience(self, audience: str) -> "GopherValidationOptions":
        """
        Set the required audience for token validation.

        Args:
            audience: The expected audience value in the token.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If the options have been destroyed or function unavailable.
        """
        self._ensure_not_destroyed()

        funcs = get_auth_functions()
        options_set_audience = funcs.get("options_set_audience")
        if options_set_audience is None:
            raise RuntimeError("options_set_audience function not available")

        options_set_audience(self._handle, audience.encode("utf-8"))

        return self

    def set_clock_skew(self, seconds: int) -> "GopherValidationOptions":
        """
        Set the clock skew tolerance for token expiration checks.

        Args:
            seconds: Number of seconds of clock skew to allow.

        Returns:
            Self for method chaining.

        Raises:
            RuntimeError: If the options have been destroyed or function unavailable.
        """
        self._ensure_not_destroyed()

        funcs = get_auth_functions()
        options_set_clock_skew = funcs.get("options_set_clock_skew")
        if options_set_clock_skew is None:
            raise RuntimeError("options_set_clock_skew function not available")

        options_set_clock_skew(self._handle, seconds)

        return self

    def get_handle(self) -> c_void_p:
        """
        Get the native handle for this options instance.

        Returns:
            The ctypes void pointer handle.

        Raises:
            RuntimeError: If the options have been destroyed.
        """
        self._ensure_not_destroyed()
        return self._handle

    def destroy(self) -> None:
        """
        Destroy the native options handle and release resources.

        This method is idempotent - calling it multiple times is safe.
        """
        if self._destroyed or self._handle is None:
            return

        funcs = get_auth_functions()
        options_destroy = funcs.get("options_destroy")
        if options_destroy is not None:
            options_destroy(self._handle)

        self._handle = None
        self._destroyed = True

    def is_destroyed(self) -> bool:
        """
        Check if this options instance has been destroyed.

        Returns:
            True if destroyed, False otherwise.
        """
        return self._destroyed

    def _ensure_not_destroyed(self) -> None:
        """
        Ensure the options have not been destroyed.

        Raises:
            RuntimeError: If the options have been destroyed.
        """
        if self._destroyed:
            raise RuntimeError("GopherValidationOptions has been destroyed")

    def __enter__(self) -> "GopherValidationOptions":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and destroy resources."""
        self.destroy()

    def __del__(self) -> None:
        """Destructor - ensure resources are released."""
        self.destroy()


def gopher_create_validation_options(
    scopes: Optional[List[str]] = None,
    audience: Optional[str] = None,
    clock_skew: int = 30,
) -> GopherValidationOptions:
    """
    Factory function to create GopherValidationOptions with common defaults.

    Args:
        scopes: Optional list of required scopes.
        audience: Optional required audience.
        clock_skew: Clock skew tolerance in seconds (default: 30).

    Returns:
        A configured GopherValidationOptions instance.

    Raises:
        RuntimeError: If the library is not loaded or auth is not available.
    """
    options = GopherValidationOptions()

    if scopes is not None:
        options.set_scopes(scopes)

    if audience is not None:
        options.set_audience(audience)

    options.set_clock_skew(clock_skew)

    return options
