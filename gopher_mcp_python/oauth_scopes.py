"""Scope selection shared by SDK and application-managed OAuth flows."""

from typing import List, Optional


def select_oauth_scopes(
    *,
    challenge_scopes: Optional[List[str]] = None,
    resource_scopes: Optional[List[str]] = None,
    scopes: Optional[List[str]] = None,
) -> List[str]:
    """Select request scopes without using realm-wide authorization-server scopes.

    A challenge is authoritative, including an explicitly empty challenge.
    Otherwise honor caller-selected scopes, then the resource's advertised
    scopes. An empty result means the request should omit its scope parameter.
    """
    for selected in (challenge_scopes, scopes, resource_scopes):
        if selected is not None:
            return list(selected)
    return []
