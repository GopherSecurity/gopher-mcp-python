"""Scope validation helpers for per-request usage."""

from typing import List, Optional

from gopher_mcp_python.ffi.auth.types import GopherAuthContext
from gopher_mcp_python.ffi.auth.loader import (
    gopher_auth_validate_all_scopes,
    gopher_auth_validate_any_scopes,
)


def has_scope(context: Optional[GopherAuthContext], scope: str) -> bool:
    """Check if context has a specific scope."""
    if not context or not context.scopes:
        return False
    return gopher_auth_validate_all_scopes(context.scopes, scope)


def has_all_scopes(context: Optional[GopherAuthContext], scopes: List[str]) -> bool:
    """Check if context has ALL required scopes (AND logic)."""
    if not context or not context.scopes:
        return len(scopes) == 0
    if not scopes:
        return True
    return gopher_auth_validate_all_scopes(context.scopes, " ".join(scopes))


def has_any_scope(context: Optional[GopherAuthContext], scopes: List[str]) -> bool:
    """Check if context has ANY of the required scopes (OR logic)."""
    if not context or not context.scopes:
        return len(scopes) == 0
    if not scopes:
        return True
    return gopher_auth_validate_any_scopes(context.scopes, " ".join(scopes))
