"""
AuthClient - JWT token validation client.

Provides high-level API for validating JWT tokens and extracting
payload information using the gopher-auth native library.
"""

from ctypes import byref, c_char_p, c_int64, c_void_p
from typing import List, Optional, Tuple

from gopher_mcp_python.ffi.auth.loader import (
    load_library,
    get_auth_functions,
    is_auth_available,
    GopherAuthValidationResult,
)
from gopher_mcp_python.ffi.auth.types import (
    GopherAuthError,
    ValidationResult,
    TokenPayload,
    get_error_description,
)
from gopher_mcp_python.ffi.auth.validation_options import GopherValidationOptions


# ============================================================================
# Library Lifecycle Functions
# ============================================================================

_auth_initialized: bool = False


def gopher_init_auth_library() -> bool:
    """
    Initialize the auth library.

    This must be called before using any auth functions.

    Returns:
        True if initialization successful, False otherwise.
    """
    global _auth_initialized

    if _auth_initialized:
        return True

    if not load_library():
        return False

    if not is_auth_available():
        return False

    funcs = get_auth_functions()
    auth_init = funcs.get("auth_init")
    if auth_init is None:
        return False

    result = auth_init()
    if result == GopherAuthError.SUCCESS:
        _auth_initialized = True
        return True

    return False


def gopher_shutdown_auth_library() -> bool:
    """
    Shutdown the auth library and release resources.

    Returns:
        True if shutdown successful, False otherwise.
    """
    global _auth_initialized

    if not _auth_initialized:
        return True

    funcs = get_auth_functions()
    auth_shutdown = funcs.get("auth_shutdown")
    if auth_shutdown is None:
        return False

    result = auth_shutdown()
    if result == GopherAuthError.SUCCESS:
        _auth_initialized = False
        return True

    return False


def gopher_get_auth_library_version() -> Optional[str]:
    """
    Get the auth library version string.

    Returns:
        Version string, or None if unavailable.
    """
    if not load_library():
        return None

    funcs = get_auth_functions()
    auth_version = funcs.get("auth_version")
    if auth_version is None:
        return None

    result = auth_version()
    if result:
        return result.decode("utf-8")
    return None


def gopher_is_auth_library_initialized() -> bool:
    """
    Check if the auth library has been initialized.

    Returns:
        True if initialized, False otherwise.
    """
    return _auth_initialized


# ============================================================================
# WWW-Authenticate Header Generation
# ============================================================================


def gopher_generate_www_authenticate_header(
    realm: str,
    error: str = "",
    description: str = "",
) -> Optional[str]:
    """
    Generate a WWW-Authenticate header for 401 responses.

    Args:
        realm: The authentication realm.
        error: Optional error code (e.g., "invalid_token").
        description: Optional error description.

    Returns:
        The WWW-Authenticate header value, or None on error.
    """
    if not load_library():
        return None

    funcs = get_auth_functions()
    generate_func = funcs.get("generate_www_authenticate")
    if generate_func is None:
        return None

    header_out = c_char_p()
    result = generate_func(
        realm.encode("utf-8"),
        error.encode("utf-8"),
        description.encode("utf-8"),
        byref(header_out),
    )

    if result != GopherAuthError.SUCCESS:
        return None

    if header_out.value:
        header = header_out.value.decode("utf-8")
        # Free the allocated string
        free_string = funcs.get("free_string")
        if free_string:
            free_string(header_out)
        return header

    return None


def gopher_generate_www_authenticate_header_v2(
    realm: str,
    resource_metadata_url: str,
    scopes: List[str],
    error: str = "",
    error_description: str = "",
) -> Optional[str]:
    """
    Generate a WWW-Authenticate header with RFC 9728 support.

    Args:
        realm: The authentication realm.
        resource_metadata_url: URL to the OAuth protected resource metadata.
        scopes: List of required scopes.
        error: Optional error code.
        error_description: Optional error description.

    Returns:
        The WWW-Authenticate header value, or None on error.
    """
    if not load_library():
        return None

    funcs = get_auth_functions()
    generate_func = funcs.get("generate_www_authenticate_v2")
    if generate_func is None:
        return None

    scopes_str = " ".join(scopes)
    header_out = c_char_p()
    result = generate_func(
        realm.encode("utf-8"),
        resource_metadata_url.encode("utf-8"),
        scopes_str.encode("utf-8"),
        error.encode("utf-8"),
        error_description.encode("utf-8"),
        byref(header_out),
    )

    if result != GopherAuthError.SUCCESS:
        return None

    if header_out.value:
        header = header_out.value.decode("utf-8")
        # Free the allocated string
        free_string = funcs.get("free_string")
        if free_string:
            free_string(header_out)
        return header

    return None


# ============================================================================
# AuthClient Class
# ============================================================================


class GopherAuthClient:
    """
    JWT token validation client.

    Provides methods for validating JWT tokens and extracting payload
    information using JWKS-based signature verification.

    Usage:
        # Using context manager (recommended)
        with GopherAuthClient("https://auth.example.com/.well-known/jwks.json",
                              "https://auth.example.com") as client:
            result = client.validate_token(token)
            if result.valid:
                payload = client.extract_payload(token)

        # Manual lifecycle management
        client = GopherAuthClient(jwks_uri, issuer)
        try:
            result, payload = client.validate_and_extract(token)
        finally:
            client.destroy()
    """

    def __init__(self, jwks_uri: str, issuer: str) -> None:
        """
        Create a new AuthClient instance.

        Args:
            jwks_uri: URL to the JWKS endpoint.
            issuer: Expected token issuer.

        Raises:
            RuntimeError: If the library is not loaded or client creation fails.
        """
        self._handle: Optional[c_void_p] = None
        self._destroyed: bool = False

        if not load_library():
            raise RuntimeError("Failed to load gopher-orch library")

        if not is_auth_available():
            raise RuntimeError("Auth functions not available in library")

        # Initialize library if needed
        if not gopher_is_auth_library_initialized():
            if not gopher_init_auth_library():
                raise RuntimeError("Failed to initialize auth library")

        funcs = get_auth_functions()
        client_create = funcs.get("client_create")
        if client_create is None:
            raise RuntimeError("client_create function not available")

        handle = c_void_p()
        result = client_create(
            byref(handle),
            jwks_uri.encode("utf-8"),
            issuer.encode("utf-8"),
        )

        if result != GopherAuthError.SUCCESS:
            raise RuntimeError(
                f"Failed to create auth client: {get_error_description(result)}"
            )

        self._handle = handle

    def set_option(self, key: str, value: str) -> bool:
        """
        Set a client option.

        Args:
            key: Option name (e.g., "cache_duration", "auto_refresh", "request_timeout").
            value: Option value as string.

        Returns:
            True if option was set successfully, False otherwise.

        Raises:
            RuntimeError: If the client has been destroyed.
        """
        self._ensure_not_destroyed()

        funcs = get_auth_functions()
        client_set_option = funcs.get("client_set_option")
        if client_set_option is None:
            return False

        result = client_set_option(
            self._handle,
            key.encode("utf-8"),
            value.encode("utf-8"),
        )

        return result == GopherAuthError.SUCCESS

    def validate_token(
        self,
        token: str,
        options: Optional[GopherValidationOptions] = None,
    ) -> ValidationResult:
        """
        Validate a JWT token.

        Args:
            token: The JWT token string to validate.
            options: Optional validation options (scopes, audience, etc.).

        Returns:
            ValidationResult with valid flag, error code, and message.

        Raises:
            RuntimeError: If the client has been destroyed or function unavailable.
        """
        self._ensure_not_destroyed()

        funcs = get_auth_functions()
        validate_token = funcs.get("validate_token")
        if validate_token is None:
            return ValidationResult(
                valid=False,
                error_code=GopherAuthError.NOT_INITIALIZED,
                error_message="validate_token function not available",
            )

        result_struct = GopherAuthValidationResult()
        options_handle = options.get_handle() if options else None

        err = validate_token(
            self._handle,
            token.encode("utf-8"),
            options_handle,
            byref(result_struct),
        )

        if err != GopherAuthError.SUCCESS:
            return ValidationResult(
                valid=False,
                error_code=err,
                error_message=get_error_description(err),
            )

        error_message = None
        if result_struct.error_message:
            error_message = result_struct.error_message.decode("utf-8")

        return ValidationResult(
            valid=result_struct.valid,
            error_code=result_struct.error_code,
            error_message=error_message,
        )

    def extract_payload(self, token: str) -> Optional[TokenPayload]:
        """
        Extract payload from a JWT token without validation.

        Args:
            token: The JWT token string.

        Returns:
            TokenPayload with extracted claims, or None on error.

        Raises:
            RuntimeError: If the client has been destroyed.
        """
        self._ensure_not_destroyed()

        funcs = get_auth_functions()
        extract_payload = funcs.get("extract_payload")
        if extract_payload is None:
            return None

        payload_handle = c_void_p()
        result = extract_payload(
            token.encode("utf-8"),
            byref(payload_handle),
        )

        if result != GopherAuthError.SUCCESS:
            return None

        try:
            subject = self._get_payload_string(payload_handle, "payload_get_subject")
            scopes = self._get_payload_string(payload_handle, "payload_get_scopes")
            audience = self._get_payload_string(payload_handle, "payload_get_audience")
            issuer = self._get_payload_string(payload_handle, "payload_get_issuer")

            # Get expiration
            expiration = None
            get_exp = funcs.get("payload_get_expiration")
            if get_exp:
                exp_value = c_int64()
                if get_exp(payload_handle, byref(exp_value)) == GopherAuthError.SUCCESS:
                    expiration = exp_value.value

            # Extract extended claims via payload_get_claim
            email = self._get_payload_claim(payload_handle, "email")
            name_val = self._get_payload_claim(payload_handle, "name")
            organization_id = self._get_payload_claim(payload_handle, "organization_id")
            server_id = self._get_payload_claim(payload_handle, "server_id")

            return TokenPayload(
                subject=subject or "",
                scopes=scopes or "",
                audience=audience,
                expiration=expiration,
                issuer=issuer,
                email=email,
                name=name_val,
                organization_id=organization_id,
                server_id=server_id,
            )
        finally:
            # Clean up payload handle
            payload_destroy = funcs.get("payload_destroy")
            if payload_destroy:
                payload_destroy(payload_handle)

    def _get_payload_string(
        self,
        payload_handle: c_void_p,
        func_name: str,
    ) -> Optional[str]:
        """
        Helper to get a string field from payload.

        Args:
            payload_handle: The payload handle.
            func_name: Name of the getter function.

        Returns:
            The string value, or None if unavailable.
        """
        funcs = get_auth_functions()
        getter = funcs.get(func_name)
        if getter is None:
            return None

        value_out = c_char_p()
        result = getter(payload_handle, byref(value_out))

        if result != GopherAuthError.SUCCESS:
            return None

        if value_out.value:
            value = value_out.value.decode("utf-8")
            # Free the allocated string
            free_string = funcs.get("free_string")
            if free_string:
                free_string(value_out)
            return value

        return None

    def _get_payload_claim(
        self,
        payload_handle: c_void_p,
        claim_name: str,
    ) -> Optional[str]:
        """
        Get a custom claim from payload by name.

        Args:
            payload_handle: The payload handle.
            claim_name: The claim name to extract.

        Returns:
            The claim value, or None if not present.
        """
        funcs = get_auth_functions()
        get_claim = funcs.get("payload_get_claim")
        if get_claim is None:
            return None

        value_out = c_char_p()
        result = get_claim(
            payload_handle,
            claim_name.encode("utf-8"),
            byref(value_out),
        )

        if result != GopherAuthError.SUCCESS:
            return None

        if value_out.value:
            value = value_out.value.decode("utf-8")
            free_string = funcs.get("free_string")
            if free_string:
                free_string(value_out)
            return value

        return None

    def validate_and_extract(
        self,
        token: str,
        options: Optional[GopherValidationOptions] = None,
    ) -> Tuple[ValidationResult, Optional[TokenPayload]]:
        """
        Validate a token and extract its payload in one call.

        Args:
            token: The JWT token string.
            options: Optional validation options.

        Returns:
            Tuple of (ValidationResult, TokenPayload or None).

        Raises:
            RuntimeError: If the client has been destroyed.
        """
        result = self.validate_token(token, options)

        if not result.valid:
            return result, None

        payload = self.extract_payload(token)
        return result, payload

    def destroy(self) -> None:
        """
        Destroy the client and release resources.

        This method is idempotent - calling it multiple times is safe.
        """
        if self._destroyed or self._handle is None:
            return

        funcs = get_auth_functions()
        client_destroy = funcs.get("client_destroy")
        if client_destroy is not None:
            client_destroy(self._handle)

        self._handle = None
        self._destroyed = True

    def get_handle(self) -> c_void_p:
        """Get the native handle (for internal use by auto-refresh)."""
        self._ensure_not_destroyed()
        return self._handle

    def is_destroyed(self) -> bool:
        """
        Check if this client has been destroyed.

        Returns:
            True if destroyed, False otherwise.
        """
        return self._destroyed

    def _ensure_not_destroyed(self) -> None:
        """
        Ensure the client has not been destroyed.

        Raises:
            RuntimeError: If the client has been destroyed.
        """
        if self._destroyed:
            raise RuntimeError("GopherAuthClient has been destroyed")

    def __enter__(self) -> "GopherAuthClient":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and destroy resources."""
        self.destroy()

    def __del__(self) -> None:
        """Destructor - ensure resources are released."""
        self.destroy()
