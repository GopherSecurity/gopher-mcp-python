"""Helpers for merging OAuth tokens into agent runtime options."""

from typing import Optional

from gopher_mcp_python.runtime_options import (
    GopherAgentRuntimeOptions,
    GopherAgentTokenRecord,
    normalize_runtime_options,
)


def merge_oauth_token_into_runtime_options(
    base: Optional[GopherAgentRuntimeOptions],
    token: GopherAgentTokenRecord,
) -> GopherAgentRuntimeOptions:
    """Add an OAuth bearer token unless caller already supplied credentials."""
    normalized = normalize_runtime_options(base)
    if normalized is not None:
        if normalized.access_token is not None:
            return normalized
        for name in normalized.headers:
            if name.lower() == "authorization":
                return normalized

    headers = normalized.headers if normalized is not None else {}
    return GopherAgentRuntimeOptions(
        access_token=token.access_token,
        headers=headers,
        elicitation=normalized.elicitation if normalized is not None else None,
    )
