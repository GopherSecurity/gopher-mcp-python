"""
GopherOAuthClient - FFI wrapper for OAuth HTTP client operations.

Provides token exchange, refresh, RFC 8693 token exchange, and
RFC 7591 dynamic client registration via the native C API.
"""

from ._lifecycle import NativeHandleOwner, native_constructor, native_operation
from ._memory import read_owned_string

from ctypes import POINTER, byref, c_char_p, c_int64, c_void_p
from dataclasses import dataclass
from typing import List, Optional

from gopher_mcp_python.ffi.auth.loader import (
    get_auth_functions,
    is_auth_available,
    load_library,
)
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


class GopherOAuthClient(NativeHandleOwner):
    """OAuth HTTP client for token operations via native C API."""

    _destroy_function = "oauth_client_destroy"

    @native_constructor
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

    def _token_request(self, name, *args):
        funcs = get_auth_functions()
        function = funcs.get(name)
        if not function:
            return TokenResponse(access_token="", error="ffi_error", success=False)
        response = c_void_p()
        try:
            status = function(self._handle, *args, byref(response))
            if status != GopherAuthError.SUCCESS or not response:
                return TokenResponse(access_token="", error="ffi_error", success=False)
            owned = response
            response = c_void_p()
            return self._read_token_response(owned)
        finally:
            destroy = funcs.get("token_response_destroy")
            if response and destroy:
                destroy(response)

    def _read_token_response(self, resp_handle: c_void_p) -> TokenResponse:
        funcs = get_auth_functions()
        try:
            success = funcs.get("token_response_is_success")
            is_ok = success(resp_handle) if success else False
            expires = c_int64(0)
            getter = funcs.get("token_response_get_expires_in")
            if getter:
                getter(resp_handle, byref(expires))
            return TokenResponse(
                access_token=read_owned_string(
                    funcs, "token_response_get_access_token", resp_handle, default=""
                ),
                refresh_token=read_owned_string(
                    funcs, "token_response_get_refresh_token", resp_handle
                ),
                token_type=read_owned_string(
                    funcs,
                    "token_response_get_token_type",
                    resp_handle,
                    default="Bearer",
                ),
                expires_in=expires.value,
                error=(
                    read_owned_string(funcs, "token_response_get_error", resp_handle)
                    if not is_ok
                    else None
                ),
                success=is_ok,
            )
        finally:
            destroy = funcs.get("token_response_destroy")
            if destroy:
                destroy(resp_handle)

    @native_operation
    def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: Optional[str] = None
    ) -> TokenResponse:
        return self._token_request(
            "oauth_exchange_code",
            code.encode("utf-8"),
            redirect_uri.encode("utf-8"),
            code_verifier.encode("utf-8") if code_verifier else None,
        )

    @native_operation
    def refresh_token(self, refresh_token: str) -> TokenResponse:
        return self._token_request("oauth_refresh_token", refresh_token.encode("utf-8"))

    @native_operation
    def token_exchange(
        self,
        subject_token: str,
        requested_issuer: str,
        audience: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> TokenResponse:
        return self._token_request(
            "oauth_token_exchange",
            subject_token.encode("utf-8"),
            requested_issuer.encode("utf-8"),
            audience.encode("utf-8") if audience else None,
            scope.encode("utf-8") if scope else None,
        )

    @native_operation
    def register_client(
        self,
        registration_endpoint: str,
        client_name: str,
        redirect_uris: List[str],
        scopes: Optional[str] = None,
    ) -> RegistrationResponse:
        funcs = get_auth_functions()
        fn = funcs.get("oauth_register_client")
        if not fn:
            return RegistrationResponse(client_id="", error="ffi_error", success=False)
        count = len(redirect_uris)
        uris_arr = (c_char_p * count)(*(u.encode("utf-8") for u in redirect_uris))
        resp = c_void_p()
        try:
            err = fn(
                self._handle,
                registration_endpoint.encode("utf-8"),
                client_name.encode("utf-8"),
                uris_arr,
                count,
                scopes.encode("utf-8") if scopes else b"openid",
                byref(resp),
            )
            if err != GopherAuthError.SUCCESS or not resp:
                return RegistrationResponse(
                    client_id="", error="ffi_error", success=False
                )
            is_ok = funcs.get("registration_response_is_success", lambda *a: False)(
                resp
            )
            return RegistrationResponse(
                client_id=read_owned_string(
                    funcs, "registration_response_get_client_id", resp, default=""
                ),
                client_secret=read_owned_string(
                    funcs, "registration_response_get_client_secret", resp
                ),
                error=(
                    read_owned_string(funcs, "registration_response_get_error", resp)
                    if not is_ok
                    else None
                ),
                success=is_ok,
            )
        finally:
            destroy = funcs.get("registration_response_destroy")
            if resp and destroy:
                destroy(resp)

    @native_operation
    def get_handle(self) -> c_void_p:
        """Return a borrowed pointer; use borrow_handle() for external calls."""
        self._ensure_not_destroyed()
        return self._handle

    def destroy(self) -> None:
        """Wait for active calls and release the handle exactly once."""
        self._destroy_handle()

    def is_destroyed(self) -> bool:
        return self._is_handle_destroyed()

    def __enter__(self) -> "GopherOAuthClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.destroy()

    def _ensure_not_destroyed(self) -> None:
        if self._destroyed:
            raise RuntimeError("GopherOAuthClient has been destroyed")
