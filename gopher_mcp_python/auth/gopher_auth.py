"""
GopherAuth - Reusable auth module for Python.

Provides OAuth 2.0 / JWT authentication via native FFI bindings.
Matches the JS SDK's GopherAuth class API surface.
"""

from typing import Any, Dict, List, Optional

from gopher_mcp_python.ffi.auth.auth_client import (
    GopherAuthClient,
    gopher_init_auth_library,
    gopher_shutdown_auth_library,
    gopher_generate_www_authenticate_header_v2,
)
from gopher_mcp_python.ffi.auth.config_loader import GopherAuthConfig
from gopher_mcp_python.ffi.auth.oauth_client import GopherOAuthClient, TokenResponse
from gopher_mcp_python.ffi.auth.session_manager import GopherSessionManager
from gopher_mcp_python.ffi.auth.loader import (
    gopher_auth_build_protected_resource_metadata,
)
from gopher_mcp_python.ffi.auth.types import TokenPayload, GopherAuthContext

from gopher_mcp_python.auth.errors import (
    ConfigurationError,
    TokenValidationError,
    InsufficientScopesError,
    TokenExchangeError,
)
from gopher_mcp_python.auth.scope_helpers import (
    has_scope,
    has_all_scopes,
    has_any_scope,
)


class GopherAuth:
    """Reusable auth module wrapping native FFI bindings."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        auth_disabled: bool = False,
    ) -> None:
        self._config_path = config_path
        self._config_dict = config
        self._auth_disabled = auth_disabled
        self._config: Optional[GopherAuthConfig] = None
        self._auth_client: Optional[GopherAuthClient] = None
        self._oauth_client: Optional[GopherOAuthClient] = None
        self._session_manager: Optional[GopherSessionManager] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the auth module. Must be called before any other method."""
        if self._initialized:
            return

        if self._auth_disabled:
            self._initialized = True
            return

        gopher_init_auth_library()

        if self._config_path:
            self._config = GopherAuthConfig.load_file(self._config_path)
        elif self._config_dict:
            pairs: Dict[str, str] = {}
            mapping = {
                "auth_server_url": "auth_server_url",
                "client_id": "client_id",
                "client_secret": "client_secret",
                "audience": "audience",
                "issuer": "issuer",
                "jwks_uri": "jwks_uri",
                "oauth_authorize_url": "oauth_authorize_url",
                "oauth_token_url": "oauth_token_url",
                "server_url": "server_url",
                "allowed_scopes": "allowed_scopes",
                "exchange_idps": "exchange_idps",
                "host": "host",
                "port": "port",
            }
            for py_key, cfg_key in mapping.items():
                val = self._config_dict.get(py_key)
                if val is not None:
                    pairs[cfg_key] = str(val)
            self._config = GopherAuthConfig.load_from_pairs(pairs)
        else:
            raise ConfigurationError("Either config_path or config must be provided")

        # Create auth client
        jwks_uri = self._config.get_string("jwks_uri")
        issuer = self._config.get_string("issuer")
        if jwks_uri and issuer:
            self._auth_client = GopherAuthClient(jwks_uri, issuer)
            cache_dur = self._config.get_string("jwks_cache_duration")
            if cache_dur:
                self._auth_client.set_option("cache_duration", cache_dur)

        # Create OAuth client
        token_endpoint = self._config.get_string("token_endpoint")
        client_id = self._config.get_string("client_id")
        client_secret = self._config.get_string("client_secret")
        if token_endpoint and client_id:
            self._oauth_client = GopherOAuthClient(
                token_endpoint, client_id, client_secret or None, 30
            )

        self._session_manager = GopherSessionManager(300)
        self._initialized = True

    def shutdown(self) -> None:
        """Shutdown and release all native resources."""
        if self._session_manager:
            self._session_manager.destroy()
        if self._oauth_client:
            self._oauth_client.destroy()
        if self._auth_client:
            self._auth_client.destroy()
        if self._config:
            self._config.destroy()
        self._session_manager = None
        self._oauth_client = None
        self._auth_client = None
        self._config = None
        if self._initialized and not self._auth_disabled:
            gopher_shutdown_auth_library()
        self._initialized = False

    def validate_token(
        self,
        token: str,
        required_scopes: Optional[List[str]] = None,
    ) -> TokenPayload:
        """Validate a JWT token. Raises on failure."""
        self._ensure_initialized()
        if not self._auth_client:
            raise TokenValidationError("Auth client not initialized")

        result = self._auth_client.validate_token(token)
        if not result or not result.valid:
            raise TokenValidationError(
                result.error_message if result else "Token validation failed",
                result.error_code if result else 0,
            )

        payload = self._auth_client.extract_payload(token)
        if not payload:
            raise TokenValidationError("Failed to extract payload")

        if required_scopes:
            token_scopes = [s for s in payload.scopes.split(" ") if s]
            missing = [s for s in required_scopes if s not in token_scopes]
            if missing:
                raise InsufficientScopesError(required_scopes, token_scopes)

        return payload

    def has_scope(self, payload: TokenPayload, scope: str) -> bool:
        ctx = GopherAuthContext(
            user_id=payload.subject,
            scopes=payload.scopes,
            audience=payload.audience or "",
            token_expiry=payload.expiration or 0,
            authenticated=True,
        )
        return has_scope(ctx, scope)

    def has_all_scopes(self, payload: TokenPayload, scopes: List[str]) -> bool:
        ctx = GopherAuthContext(
            user_id=payload.subject,
            scopes=payload.scopes,
            audience=payload.audience or "",
            token_expiry=payload.expiration or 0,
            authenticated=True,
        )
        return has_all_scopes(ctx, scopes)

    def has_any_scope(self, payload: TokenPayload, scopes: List[str]) -> bool:
        ctx = GopherAuthContext(
            user_id=payload.subject,
            scopes=payload.scopes,
            audience=payload.audience or "",
            token_expiry=payload.expiration or 0,
            authenticated=True,
        )
        return has_any_scope(ctx, scopes)

    def exchange_token(
        self,
        subject_token: str,
        requested_issuer: str,
        audience: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> TokenResponse:
        """Exchange a token (RFC 8693). Raises on failure."""
        self._ensure_initialized()
        if not self._oauth_client:
            raise TokenExchangeError("OAuth client not initialized")
        result = self._oauth_client.token_exchange(
            subject_token, requested_issuer, audience, scope
        )
        if not result.success:
            raise TokenExchangeError(
                result.error or "Token exchange failed",
                result.error or "",
            )
        return result

    def get_protected_resource_metadata(self) -> dict:
        server_url = self._config.get_string("server_url") if self._config else ""
        scopes = self._config.get_string("allowed_scopes") if self._config else ""
        return gopher_auth_build_protected_resource_metadata(
            f"{server_url}/mcp", server_url, scopes or None
        )

    def get_www_authenticate_header(
        self,
        error: str = "",
        error_description: str = "",
    ) -> str:
        server_url = self._config.get_string("server_url") if self._config else ""
        resource_metadata = f"{server_url}/.well-known/oauth-protected-resource"
        return (
            gopher_generate_www_authenticate_header_v2(
                server_url, resource_metadata, "", error, error_description
            )
            or "Bearer"
        )

    def get_token_endpoint(self) -> str:
        return self._config.get_string("token_endpoint") if self._config else ""

    @property
    def native_config(self) -> Optional[GopherAuthConfig]:
        return self._config

    @property
    def is_disabled(self) -> bool:
        return self._auth_disabled

    def __enter__(self) -> "GopherAuth":
        self.initialize()
        return self

    def __exit__(self, *args: object) -> None:
        self.shutdown()

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise ConfigurationError(
                "GopherAuth not initialized. Call initialize() first."
            )
