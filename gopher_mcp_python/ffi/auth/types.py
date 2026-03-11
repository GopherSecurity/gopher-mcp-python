"""
Auth Types - Type definitions for gopher-auth FFI bindings.

These types mirror the C API from gopher-orch/include/gopher/orch/auth/auth_c_api.h
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional


class GopherAuthError(IntEnum):
    """Error codes from gopher_auth_error_t enum."""

    SUCCESS = 0
    INVALID_TOKEN = -1000
    EXPIRED_TOKEN = -1001
    INVALID_SIGNATURE = -1002
    INVALID_ISSUER = -1003
    INVALID_AUDIENCE = -1004
    INSUFFICIENT_SCOPE = -1005
    JWKS_FETCH_FAILED = -1006
    INVALID_KEY = -1007
    NETWORK_ERROR = -1008
    INVALID_CONFIG = -1009
    OUT_OF_MEMORY = -1010
    INVALID_PARAMETER = -1011
    NOT_INITIALIZED = -1012
    INTERNAL_ERROR = -1013
    TOKEN_EXCHANGE_FAILED = -1014
    IDP_NOT_LINKED = -1015
    INVALID_IDP_ALIAS = -1016


# Human-readable descriptions for each error code
ERROR_DESCRIPTIONS = {
    GopherAuthError.SUCCESS: "Success",
    GopherAuthError.INVALID_TOKEN: "Invalid token format or structure",
    GopherAuthError.EXPIRED_TOKEN: "Token has expired",
    GopherAuthError.INVALID_SIGNATURE: "Token signature verification failed",
    GopherAuthError.INVALID_ISSUER: "Token issuer does not match expected value",
    GopherAuthError.INVALID_AUDIENCE: "Token audience does not match expected value",
    GopherAuthError.INSUFFICIENT_SCOPE: "Token does not have required scopes",
    GopherAuthError.JWKS_FETCH_FAILED: "Failed to fetch JWKS from server",
    GopherAuthError.INVALID_KEY: "Invalid or unsupported key in JWKS",
    GopherAuthError.NETWORK_ERROR: "Network error during authentication",
    GopherAuthError.INVALID_CONFIG: "Invalid configuration",
    GopherAuthError.OUT_OF_MEMORY: "Out of memory",
    GopherAuthError.INVALID_PARAMETER: "Invalid parameter provided",
    GopherAuthError.NOT_INITIALIZED: "Auth library not initialized",
    GopherAuthError.INTERNAL_ERROR: "Internal error",
    GopherAuthError.TOKEN_EXCHANGE_FAILED: "Token exchange failed",
    GopherAuthError.IDP_NOT_LINKED: "Identity provider not linked",
    GopherAuthError.INVALID_IDP_ALIAS: "Invalid identity provider alias",
}


def is_gopher_auth_error(code: int) -> bool:
    """
    Check if a value is a valid GopherAuthError code.

    Args:
        code: The error code to check.

    Returns:
        True if the code is a valid GopherAuthError, False otherwise.
    """
    if code == GopherAuthError.SUCCESS:
        return True
    # Error codes range from -1000 to -1016
    return GopherAuthError.INVALID_TOKEN >= code >= GopherAuthError.INVALID_IDP_ALIAS


def get_error_description(code: int) -> str:
    """
    Get human-readable description for an error code.

    Args:
        code: The error code to get description for.

    Returns:
        Human-readable error description.
    """
    try:
        error = GopherAuthError(code)
        return ERROR_DESCRIPTIONS.get(error, f"Unknown error code: {code}")
    except ValueError:
        return f"Unknown error code: {code}"


@dataclass
class ValidationResult:
    """Token validation result."""

    valid: bool
    error_code: int
    error_message: Optional[str] = None


@dataclass
class TokenPayload:
    """Decoded JWT token payload."""

    subject: str
    scopes: str
    audience: Optional[str] = None
    expiration: Optional[int] = None
    issuer: Optional[str] = None


@dataclass
class GopherAuthContext:
    """Authentication context for the current request."""

    user_id: str
    scopes: str
    audience: str
    token_expiry: int
    authenticated: bool


def gopher_create_empty_auth_context() -> GopherAuthContext:
    """
    Create an empty auth context (unauthenticated).

    Returns:
        A GopherAuthContext with default empty values and authenticated=False.
    """
    return GopherAuthContext(
        user_id="",
        scopes="",
        audience="",
        token_expiry=0,
        authenticated=False,
    )
