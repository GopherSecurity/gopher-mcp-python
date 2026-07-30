"""
Shared runtime option types for agent creation.

This module intentionally has no dependency on the public config or FFI layers,
so both can consume the same normalization contract without introducing an
import cycle.
"""

from typing import Any, Dict, Mapping, Optional, Union

RuntimeOptionsInput = Optional[
    Union["GopherAgentRuntimeOptions", Mapping[str, Any]]
]


class GopherAgentRuntimeOptions:
    """
    Runtime options applied when the native agent connects to MCP servers.

    access_token is a convenience for Authorization: Bearer <token>. If an
    explicit Authorization header is supplied in headers, that header wins.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        normalized_access_token = _normalize_access_token(access_token)
        self._access_token = normalized_access_token
        self._headers = _normalize_headers(normalized_access_token, headers)

    @property
    def access_token(self) -> Optional[str]:
        """Get the MCP runtime bearer token."""
        return self._access_token

    @property
    def headers(self) -> Dict[str, str]:
        """Get dynamic MCP runtime headers."""
        return dict(self._headers)


def normalize_runtime_options(
    options: RuntimeOptionsInput = None,
) -> Optional[GopherAgentRuntimeOptions]:
    """
    Normalize runtime options into a GopherAgentRuntimeOptions instance.

    Accepts None, GopherAgentRuntimeOptions, or a dict-like object with
    access_token and/or headers keys. Empty options normalize to None.
    """
    if options is None:
        return None

    if isinstance(options, GopherAgentRuntimeOptions):
        if options.access_token is None and len(options.headers) == 0:
            return None
        return options

    if isinstance(options, Mapping):
        access_token = options.get("access_token")
        headers = options.get("headers")
        if access_token == "":
            access_token = None
        if access_token is None and (headers is None or len(headers) == 0):
            return None
        return GopherAgentRuntimeOptions(access_token=access_token, headers=headers)

    raise ValueError(
        "runtime_options must be a GopherAgentRuntimeOptions instance or mapping"
    )


def _normalize_headers(
    access_token: Optional[str],
    headers: Optional[Mapping[str, str]],
) -> Dict[str, str]:
    normalized: Dict[str, str] = {}

    if headers is not None:
        if not isinstance(headers, Mapping):
            raise ValueError("runtime option headers must be a string mapping")
        for name, value in headers.items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise ValueError("runtime option headers must be a string mapping")
            normalized[name] = value

    if access_token:
        if "Authorization" not in normalized:
            normalized["Authorization"] = f"Bearer {access_token}"

    return normalized


def _normalize_access_token(access_token: Optional[str]) -> Optional[str]:
    if access_token is not None and not isinstance(access_token, str):
        raise ValueError("runtime option access_token must be a string")
    return access_token or None
