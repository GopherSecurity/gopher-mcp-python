"""
Shared runtime option types for agent creation.

This module intentionally has no dependency on the public config or FFI layers,
so both can consume the same normalization contract without introducing an
import cycle.
"""

from typing import Any, Dict, List, Mapping, Optional, Protocol, Union

RuntimeOptionsInput = Optional[
    Union["GopherAgentRuntimeOptions", "GopherAgentCreateOptions", Mapping[str, Any]]
]
CreateOptionsInput = Optional[Union["GopherAgentCreateOptions", Mapping[str, Any]]]


class GopherAgentTokenRecord:
    """OAuth token record stored by SDK-side token stores."""

    def __init__(
        self,
        access_token: str,
        token_type: str = "Bearer",
        refresh_token: Optional[str] = None,
        expires_at: Optional[float] = None,
        scope: Optional[str] = None,
    ) -> None:
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("token access_token must be a non-empty string")
        if not isinstance(token_type, str) or not token_type:
            raise ValueError("token token_type must be a non-empty string")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise ValueError("token refresh_token must be a string")
        if expires_at is not None and not isinstance(expires_at, (int, float)):
            raise ValueError("token expires_at must be a number")
        if scope is not None and not isinstance(scope, str):
            raise ValueError("token scope must be a string")
        self.access_token = access_token
        self.token_type = token_type
        self.refresh_token = refresh_token
        self.expires_at = float(expires_at) if expires_at is not None else None
        self.scope = scope


class GopherAgentTokenStore(Protocol):
    """Async token store protocol used by SDK OAuth auto-flow."""

    async def get(self, key: str) -> Optional[GopherAgentTokenRecord]:
        """Return a cached token record for key, if any."""

    async def set(self, key: str, token: GopherAgentTokenRecord) -> None:
        """Store a token record for key."""

    async def delete(self, key: str) -> None:
        """Delete a cached token record for key, if supported."""


class GopherAgentOAuthOptions:
    """OAuth options for SDK-side agent creation."""

    def __init__(
        self,
        mode: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        client_name: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        open_browser: Optional[bool] = None,
        token_store: Optional[GopherAgentTokenStore] = None,
    ) -> None:
        if mode is not None and mode not in ("auto", "disabled"):
            raise ValueError('oauth mode must be "auto" or "disabled"')
        if scopes is not None:
            if not isinstance(scopes, list) or not all(
                isinstance(scope, str) for scope in scopes
            ):
                raise ValueError("oauth scopes must be a list of strings")
        if client_name is not None and not isinstance(client_name, str):
            raise ValueError("oauth client_name must be a string")
        if redirect_uri is not None and not isinstance(redirect_uri, str):
            raise ValueError("oauth redirect_uri must be a string")
        if open_browser is not None and not isinstance(open_browser, bool):
            raise ValueError("oauth open_browser must be a boolean")

        self.mode = mode
        self.scopes = list(scopes) if scopes is not None else None
        self.client_name = client_name
        self.redirect_uri = redirect_uri
        self.open_browser = open_browser
        self.token_store = token_store


class GopherAgentCreateOptions:
    """Agent creation options: native runtime options plus SDK OAuth options."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
        oauth: Optional[Union[GopherAgentOAuthOptions, Mapping[str, Any]]] = None,
    ) -> None:
        runtime = GopherAgentRuntimeOptions(access_token=access_token, headers=headers)
        self._access_token = runtime.access_token
        self._headers = runtime.headers
        self._oauth = normalize_oauth_options(oauth)

    @property
    def access_token(self) -> Optional[str]:
        """Get the MCP runtime bearer token."""
        return self._access_token

    @property
    def headers(self) -> Dict[str, str]:
        """Get dynamic MCP runtime headers."""
        return dict(self._headers)

    @property
    def oauth(self) -> Optional[GopherAgentOAuthOptions]:
        """Get SDK-side OAuth options."""
        return self._oauth


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

    if isinstance(options, (GopherAgentRuntimeOptions, GopherAgentCreateOptions)):
        if options.access_token is None and len(options.headers) == 0:
            return None
        return GopherAgentRuntimeOptions(
            access_token=options.access_token,
            headers=options.headers,
        )

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


def normalize_create_options(
    options: Union[RuntimeOptionsInput, CreateOptionsInput] = None,
) -> Optional[GopherAgentCreateOptions]:
    """Normalize agent creation options, preserving optional OAuth options."""
    if options is None:
        return None

    if isinstance(options, GopherAgentCreateOptions):
        if (
            options.access_token is None
            and len(options.headers) == 0
            and options.oauth is None
        ):
            return None
        return options

    if isinstance(options, GopherAgentRuntimeOptions):
        if options.access_token is None and len(options.headers) == 0:
            return None
        return GopherAgentCreateOptions(
            access_token=options.access_token,
            headers=options.headers,
        )

    if isinstance(options, Mapping):
        access_token = options.get("access_token")
        headers = options.get("headers")
        oauth = options.get("oauth")
        if access_token == "":
            access_token = None
        if access_token is None and (headers is None or len(headers) == 0):
            runtime_empty = True
        else:
            runtime_empty = False
        if runtime_empty and oauth is None:
            return None
        return GopherAgentCreateOptions(
            access_token=access_token,
            headers=headers,
            oauth=oauth,
        )

    raise ValueError(
        "create options must be a GopherAgentCreateOptions instance or mapping"
    )


def normalize_oauth_options(
    options: Optional[Union[GopherAgentOAuthOptions, Mapping[str, Any]]] = None,
) -> Optional[GopherAgentOAuthOptions]:
    """Normalize OAuth options into a GopherAgentOAuthOptions instance."""
    if options is None:
        return None

    if isinstance(options, GopherAgentOAuthOptions):
        return options

    if isinstance(options, Mapping):
        return GopherAgentOAuthOptions(
            mode=options.get("mode"),
            scopes=options.get("scopes"),
            client_name=options.get("client_name")
            if "client_name" in options
            else options.get("clientName"),
            redirect_uri=options.get("redirect_uri")
            if "redirect_uri" in options
            else options.get("redirectUri"),
            open_browser=options.get("open_browser")
            if "open_browser" in options
            else options.get("openBrowser"),
            token_store=options.get("token_store")
            if "token_store" in options
            else options.get("tokenStore"),
        )

    raise ValueError("oauth options must be a GopherAgentOAuthOptions instance or mapping")


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
