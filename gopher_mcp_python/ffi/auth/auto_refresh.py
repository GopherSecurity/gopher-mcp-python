"""
Auto-Refresh - Combines session lookup, token refresh, and re-validation.
"""

from ._lifecycle import native_operation
from ._memory import owned_string

from ctypes import POINTER, byref, c_char_p
from dataclasses import dataclass
from typing import Optional

from gopher_mcp_python.ffi.auth.loader import (
    GopherAuthValidationResult,
    get_auth_functions,
)
from gopher_mcp_python.ffi.auth.auth_client import GopherAuthClient
from gopher_mcp_python.ffi.auth.oauth_client import GopherOAuthClient
from gopher_mcp_python.ffi.auth.session_manager import GopherSessionManager
from gopher_mcp_python.ffi.auth.types import GopherAuthError


@dataclass
class AutoRefreshResult:
    """Result of auto-refresh operation."""

    valid: bool
    new_access_token: Optional[str] = None
    error_code: int = 0
    error_message: Optional[str] = None


@native_operation
def gopher_auth_auto_refresh(
    auth_client: GopherAuthClient,
    oauth_client: GopherOAuthClient,
    session_manager: GopherSessionManager,
    session_id: str,
) -> AutoRefreshResult:
    """
    Auto-refresh: validate token, refresh if expired, re-validate.

    If the token is still valid, new_access_token is None.
    If refreshed, new_access_token contains the new token.
    """
    funcs = get_auth_functions()
    fn = funcs.get("auto_refresh")
    if not fn:
        return AutoRefreshResult(
            valid=False,
            error_code=GopherAuthError.NOT_INITIALIZED,
            error_message="Auto-refresh function not available",
        )
    with owned_string(funcs) as token_out:
        result_out = GopherAuthValidationResult()
        err = fn(
            auth_client.get_handle(),
            oauth_client.get_handle(),
            session_manager.get_handle(),
            session_id.encode("utf-8"),
            byref(token_out),
            byref(result_out),
        )
        message = (
            result_out.error_message.decode("utf-8")
            if result_out.error_message
            else None
        )
        if err != GopherAuthError.SUCCESS:
            return AutoRefreshResult(
                valid=False,
                error_code=err,
                error_message=message or f"Error code {err}",
            )
        return AutoRefreshResult(
            valid=result_out.valid,
            new_access_token=(
                token_out.value.decode("utf-8") if token_out.value else None
            ),
            error_code=result_out.error_code,
            error_message=message,
        )
