"""OAuth Authentication Middleware.

Flask middleware for JWT token validation using gopher-auth FFI.
Mirrors OAuthAuthFilter from the C++ example.
"""

from functools import wraps
from typing import Any, Callable

from flask import Response, g, jsonify, request

from gopher_mcp_python.ffi.auth import (
    AuthClient,
    AuthContext,
    ValidationOptions,
    create_empty_auth_context,
    generate_www_authenticate_header_v2,
)

from ..config import AuthServerConfig


class OAuthAuthMiddleware:
    """OAuth authentication middleware.

    Validates JWT tokens on protected endpoints and attaches
    the auth context to Flask's g object.
    """

    def __init__(
        self, auth_client: AuthClient | None, config: AuthServerConfig
    ) -> None:
        """Create new OAuth middleware.

        Args:
            auth_client: AuthClient instance for token validation
                (None if auth disabled).
            config: Server configuration.
        """
        self.auth_client = auth_client
        self.config = config
        self._current_auth_context: AuthContext = create_empty_auth_context()

    def before_request(self) -> Response | None:
        """Flask before_request handler.

        Returns:
            Response if auth fails, None to continue processing.
        """
        # Handle CORS preflight
        if request.method == "OPTIONS":
            return self._send_cors_preflight_response()

        path = request.path

        # Check if path requires authentication
        if not self.requires_auth(path):
            return None

        # Extract bearer token
        token = self.extract_token()
        if not token:
            return self._send_unauthorized("invalid_request", "Missing bearer token")

        # Validate token
        valid, error_message = self._validate_token(token)
        if not valid:
            return self._send_unauthorized(
                "invalid_token", error_message or "Token validation failed"
            )

        # Attach auth context to Flask g object
        g.auth_context = self._current_auth_context
        return None

    def extract_token(self) -> str | None:
        """Extract bearer token from request.

        Checks Authorization header first, then query parameter.

        Returns:
            Token string or None if not found.
        """
        # Try Authorization header first
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Try query parameter
        query_token = request.args.get("access_token", "")
        if query_token:
            return query_token

        return None

    def requires_auth(self, path: str) -> bool:
        """Check if path requires authentication.

        Args:
            path: Request path.

        Returns:
            True if authentication is required.
        """
        # Auth is globally disabled
        if self.config.auth_disabled:
            return False

        # No auth client available
        if self.auth_client is None:
            return False

        # Public paths (no auth required)
        if path.startswith("/.well-known/"):
            return False
        if path.startswith("/oauth/"):
            return False
        if path == "/authorize":
            return False
        if path == "/health":
            return False
        if path == "/favicon.ico":
            return False

        # Protected paths (auth required)
        if path == "/mcp" or path.startswith("/mcp/"):
            return True
        if path == "/rpc" or path.startswith("/rpc/"):
            return True
        if path == "/events" or path.startswith("/events/"):
            return True
        if path == "/sse" or path.startswith("/sse/"):
            return True

        # Default: require auth for unknown paths
        return True

    def _validate_token(self, token: str) -> tuple[bool, str | None]:
        """Validate JWT token using gopher-auth.

        Args:
            token: JWT token string.

        Returns:
            Tuple of (valid, error_message).
        """
        if self.auth_client is None:
            return False, "Auth client not initialized"

        with ValidationOptions() as options:
            options.set_clock_skew(30)

            result = self.auth_client.validate_token(token, options)

            if not result.valid:
                return False, result.error_message

            # Extract payload to populate auth context
            try:
                payload = self.auth_client.extract_payload(token)

                self._current_auth_context = AuthContext(
                    user_id=payload.subject,
                    scopes=payload.scopes,
                    audience=payload.audience or "",
                    token_expiry=payload.expiration or 0,
                    authenticated=True,
                )
            except Exception:
                # Payload extraction failed, but token is valid
                self._current_auth_context = AuthContext(
                    user_id="",
                    scopes="",
                    audience="",
                    token_expiry=0,
                    authenticated=True,
                )

            return True, None

    def _send_unauthorized(self, error: str, description: str) -> Response:
        """Send 401 Unauthorized response with WWW-Authenticate header.

        Args:
            error: OAuth error code.
            description: Human-readable error description.

        Returns:
            Flask Response object.
        """
        try:
            www_authenticate = generate_www_authenticate_header_v2(
                realm=self.config.server_url,
                resource_metadata_url=(
                    f"{self.config.server_url}/.well-known/oauth-protected-resource"
                ),
                scopes=self.config.allowed_scopes.split(),
                error=error,
                error_description=description,
            )
        except Exception:
            # Fallback to basic Bearer header
            www_authenticate = (
                f'Bearer realm="{self.config.server_url}", '
                f'error="{error}", '
                f'error_description="{description}"'
            )

        response = jsonify({"error": error, "error_description": description})
        response.status_code = 401
        response.headers["WWW-Authenticate"] = www_authenticate
        response.headers["Content-Type"] = "application/json"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "WWW-Authenticate"
        return response

    def _send_cors_preflight_response(self) -> Response:
        """Send CORS preflight response.

        Returns:
            Flask Response object.
        """
        response = Response("", status=204)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Accept, Accept-Language, Content-Language, Content-Type, Authorization, "
            "X-Requested-With, Origin, Cache-Control, Pragma, Mcp-Session-Id, "
            "Mcp-Protocol-Version"
        )
        response.headers["Access-Control-Max-Age"] = "86400"
        response.headers["Access-Control-Expose-Headers"] = (
            "WWW-Authenticate, Content-Length, Content-Type"
        )
        return response

    def get_auth_context(self) -> AuthContext:
        """Get the current authentication context."""
        return self._current_auth_context

    def is_auth_disabled(self) -> bool:
        """Check if authentication is disabled."""
        return self.config.auth_disabled

    def has_scope(self, scope: str) -> bool:
        """Check if a scope is present in the current auth context.

        Args:
            scope: Scope to check.

        Returns:
            True if scope is present.
        """
        if not self._current_auth_context.authenticated:
            return False
        return scope in self._current_auth_context.scopes.split()


def require_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    """Flask decorator to require authentication on a route.

    Usage:
        @app.route('/protected')
        @require_auth
        def protected():
            auth_context = g.auth_context
            return f"Hello, {auth_context.user_id}"

    Args:
        f: The route function to wrap.

    Returns:
        Wrapped function that checks for auth context.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        auth_context = getattr(g, "auth_context", None)
        if auth_context is None or not auth_context.authenticated:
            response = jsonify(
                {
                    "error": "unauthorized",
                    "error_description": "Authentication required",
                }
            )
            response.status_code = 401
            return response
        return f(*args, **kwargs)

    return decorated_function
