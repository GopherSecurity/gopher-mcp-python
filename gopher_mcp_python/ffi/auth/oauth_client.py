"""
GopherOAuthClient - FFI wrapper for OAuth HTTP client operations.

Provides token exchange, refresh, RFC 8693 token exchange, and
RFC 7591 dynamic client registration via the native C API.
"""

from ctypes import POINTER, byref, c_char_p, c_int64, c_void_p
from dataclasses import dataclass
from typing import List, Optional

from gopher_mcp_python.ffi.auth.loader import get_auth_functions, is_auth_available, load_library
from gopher_mcp_python.ffi.auth.types import GopherAuthError


@dataclass
class TokenResponse:
    """Token endpoint response."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int = 0
    token_type: str = "Bearer"
    error: Optional[str] = None
    success: bool = False


@dataclass
class RegistrationResponse:
    """Dynamic client registration response."""
    client_id: str
    client_secret: Optional[str] = None
    success: bool = False
    error: Optional[str] = None


class GopherOAuthClient:
    """OAuth HTTP client for token operations via native C API."""

    def __init__(
        self,
        token_endpoint: str,
        client_id: str,
        client_secret: Optional[str] = None,
        request_timeout: int = 30,
    ) -> None:
        if not is_auth_available():
            load_library()

        funcs = get_auth_functions()
        create = funcs.get("oauth_client_create")
        if not create:
            raise RuntimeError("OAuth client functions not available")

        self._handle = c_void_p()
        result = create(
            byref(self._handle),
            token_endpoint.encode("utf-8"),
            client_id.encode("utf-8"),
            client_secret.encode("utf-8") if client_secret else None,
            request_timeout,
        )
        if result != GopherAuthError.SUCCESS:
            raise RuntimeError(f"Failed to create OAuth client: error {result}")
        self._destroyed = False

    def _read_token_response(self, resp_handle: c_void_p) -> TokenResponse:
        funcs = get_auth_functions()
        success = funcs.get("token_response_is_success")
        is_ok = success(resp_handle) if success else False

        at_out = c_char_p()
        funcs.get("token_response_get_access_token", lambda *a: None)(resp_handle, byref(at_out))
        rt_out = c_char_p()
        funcs.get("token_response_get_refresh_token", lambda *a: None)(resp_handle, byref(rt_out))
        exp_out = c_int64(0)
        funcs.get("token_response_get_expires_in", lambda *a: None)(resp_handle, byref(exp_out))
        err_out = c_char_p()
        funcs.get("token_response_get_error", lambda *a: None)(resp_handle, byref(err_out))

        funcs.get("token_response_destroy", lambda *a: None)(resp_handle)

        return TokenResponse(
            access_token=at_out.value.decode("utf-8") if at_out.value else "",
            refresh_token=rt_out.value.decode("utf-8") if rt_out.value else None,
            expires_in=exp_out.value,
            error=err_out.value.decode("utf-8") if err_out.value and not is_ok else None,
            success=is_ok,
        )

    def exchange_code(self, code: str, redirect_uri: str, code_verifier: Optional[str] = None) -> TokenResponse:
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        fn = funcs.get("oauth_exchange_code")
        if not fn:
            return TokenResponse(access_token="", error="ffi_error", success=False)
        resp = c_void_p()
        err = fn(self._handle, code.encode("utf-8"), redirect_uri.encode("utf-8"),
                 code_verifier.encode("utf-8") if code_verifier else None, byref(resp))
        if err != GopherAuthError.SUCCESS or not resp:
            return TokenResponse(access_token="", error="ffi_error", success=False)
        return self._read_token_response(resp)

    def refresh_token(self, refresh_token: str) -> TokenResponse:
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        fn = funcs.get("oauth_refresh_token")
        if not fn:
            return TokenResponse(access_token="", error="ffi_error", success=False)
        resp = c_void_p()
        err = fn(self._handle, refresh_token.encode("utf-8"), byref(resp))
        if err != GopherAuthError.SUCCESS or not resp:
            return TokenResponse(access_token="", error="ffi_error", success=False)
        return self._read_token_response(resp)

    def token_exchange(self, subject_token: str, requested_issuer: str,
                       audience: Optional[str] = None, scope: Optional[str] = None) -> TokenResponse:
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        fn = funcs.get("oauth_token_exchange")
        if not fn:
            return TokenResponse(access_token="", error="ffi_error", success=False)
        resp = c_void_p()
        err = fn(self._handle, subject_token.encode("utf-8"), requested_issuer.encode("utf-8"),
                 audience.encode("utf-8") if audience else None,
                 scope.encode("utf-8") if scope else None, byref(resp))
        if err != GopherAuthError.SUCCESS or not resp:
            return TokenResponse(access_token="", error="ffi_error", success=False)
        return self._read_token_response(resp)

    def register_client(self, registration_endpoint: str, client_name: str,
                        redirect_uris: List[str], scopes: Optional[str] = None) -> RegistrationResponse:
        self._ensure_not_destroyed()
        funcs = get_auth_functions()
        fn = funcs.get("oauth_register_client")
        if not fn:
            return RegistrationResponse(client_id="", error="ffi_error", success=False)
        count = len(redirect_uris)
        uris_arr = (c_char_p * count)(*(u.encode("utf-8") for u in redirect_uris))
        resp = c_void_p()
        err = fn(self._handle, registration_endpoint.encode("utf-8"),
                 client_name.encode("utf-8"), uris_arr, count,
                 scopes.encode("utf-8") if scopes else b"openid", byref(resp))
        if err != GopherAuthError.SUCCESS or not resp:
            return RegistrationResponse(client_id="", error="ffi_error", success=False)

        is_ok = funcs.get("registration_response_is_success", lambda *a: False)(resp)
        cid_out = c_char_p()
        funcs.get("registration_response_get_client_id", lambda *a: None)(resp, byref(cid_out))
        cs_out = c_char_p()
        funcs.get("registration_response_get_client_secret", lambda *a: None)(resp, byref(cs_out))
        funcs.get("registration_response_destroy", lambda *a: None)(resp)

        return RegistrationResponse(
            client_id=cid_out.value.decode("utf-8") if cid_out.value else "",
            client_secret=cs_out.value.decode("utf-8") if cs_out.value else None,
            success=is_ok,
        )

    def get_handle(self) -> c_void_p:
        self._ensure_not_destroyed()
        return self._handle

    def destroy(self) -> None:
        if self._destroyed:
            return
        funcs = get_auth_functions()
        d = funcs.get("oauth_client_destroy")
        if d and self._handle:
            d(self._handle)
        self._handle = None
        self._destroyed = True

    def is_destroyed(self) -> bool:
        return self._destroyed

    def __enter__(self) -> "GopherOAuthClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.destroy()

    def _ensure_not_destroyed(self) -> None:
        if self._destroyed:
            raise RuntimeError("GopherOAuthClient has been destroyed")
