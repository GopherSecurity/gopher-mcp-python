"""OAuth Discovery Endpoints.

Implements OAuth 2.0 discovery endpoints:
- /.well-known/oauth-protected-resource (RFC 9728)
- /.well-known/oauth-authorization-server (RFC 8414)
- /.well-known/openid-configuration
- /oauth/authorize (redirect to IdP)
- /oauth/register (RFC 7591 dynamic registration)
"""

from __future__ import annotations

import math
import time
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

from flask import Blueprint, Flask, Response, jsonify, redirect, request

from ..config import AuthServerConfig


def _set_cors_headers(response: Response) -> Response:
    """Set common CORS headers on response.

    Args:
        response: Flask response object.

    Returns:
        Response with CORS headers set.
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Authorization, Content-Type, Accept, Origin, X-Requested-With"
    )
    response.headers["Access-Control-Expose-Headers"] = (
        "WWW-Authenticate, Content-Length"
    )
    response.headers["Access-Control-Max-Age"] = "86400"
    return response


def _cors_preflight() -> Response:
    """Create CORS preflight response."""
    response = Response("", status=204)
    response.headers["Content-Length"] = "0"
    return _set_cors_headers(response)


def _build_protected_resource_metadata(config: AuthServerConfig) -> dict[str, Any]:
    """Build protected resource metadata (RFC 9728).

    Args:
        config: Server configuration.

    Returns:
        Protected resource metadata dictionary.
    """
    scopes = [s for s in config.allowed_scopes.split() if s]
    return {
        "resource": f"{config.server_url}/mcp",
        "authorization_servers": [config.server_url],
        "scopes_supported": scopes,
        "bearer_methods_supported": ["header", "query"],
        "resource_documentation": f"{config.server_url}/docs",
    }


def create_oauth_blueprint(config: AuthServerConfig) -> Blueprint:
    """Create OAuth discovery blueprint.

    Args:
        config: Server configuration.

    Returns:
        Flask Blueprint with OAuth endpoints.
    """
    bp = Blueprint("oauth", __name__)

    # OPTIONS handlers for CORS preflight
    @bp.route("/.well-known/oauth-protected-resource", methods=["OPTIONS"])
    def cors_protected_resource() -> Response:
        return _cors_preflight()

    @bp.route("/.well-known/oauth-protected-resource/mcp", methods=["OPTIONS"])
    def cors_protected_resource_mcp() -> Response:
        return _cors_preflight()

    @bp.route("/.well-known/oauth-authorization-server", methods=["OPTIONS"])
    def cors_authorization_server() -> Response:
        return _cors_preflight()

    @bp.route("/.well-known/openid-configuration", methods=["OPTIONS"])
    def cors_openid_configuration() -> Response:
        return _cors_preflight()

    @bp.route("/oauth/authorize", methods=["OPTIONS"])
    def cors_authorize() -> Response:
        return _cors_preflight()

    @bp.route("/oauth/register", methods=["OPTIONS"])
    def cors_register() -> Response:
        return _cors_preflight()

    # RFC 9728 - Protected Resource Metadata (root)
    @bp.route("/.well-known/oauth-protected-resource", methods=["GET"])
    def protected_resource() -> tuple[Response, int]:
        metadata = _build_protected_resource_metadata(config)
        response = jsonify(metadata)
        return _set_cors_headers(response), 200

    # RFC 9728: Resource-specific discovery URL for /mcp endpoint
    @bp.route("/.well-known/oauth-protected-resource/mcp", methods=["GET"])
    def protected_resource_mcp() -> tuple[Response, int]:
        metadata = _build_protected_resource_metadata(config)
        response = jsonify(metadata)
        return _set_cors_headers(response), 200

    # RFC 8414 - OAuth Authorization Server Metadata
    @bp.route("/.well-known/oauth-authorization-server", methods=["GET"])
    def authorization_server() -> tuple[Response, int]:
        auth_endpoint = (
            config.oauth_authorize_url
            or f"{config.auth_server_url}/protocol/openid-connect/auth"
        )
        token_endpoint = (
            config.oauth_token_url
            or f"{config.auth_server_url}/protocol/openid-connect/token"
        )

        scopes = [s for s in config.allowed_scopes.split() if s]

        metadata: dict[str, Any] = {
            "issuer": config.issuer or config.server_url,
            "authorization_endpoint": auth_endpoint,
            "token_endpoint": token_endpoint,
            "registration_endpoint": f"{config.server_url}/oauth/register",
            "scopes_supported": scopes,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
                "none",
            ],
            "code_challenge_methods_supported": ["S256"],
        }

        if config.jwks_uri:
            metadata["jwks_uri"] = config.jwks_uri

        response = jsonify(metadata)
        return _set_cors_headers(response), 200

    # OpenID Connect Discovery
    @bp.route("/.well-known/openid-configuration", methods=["GET"])
    def openid_configuration() -> tuple[Response, int]:
        auth_endpoint = (
            config.oauth_authorize_url
            or f"{config.auth_server_url}/protocol/openid-connect/auth"
        )
        token_endpoint = (
            config.oauth_token_url
            or f"{config.auth_server_url}/protocol/openid-connect/token"
        )

        base_scopes = ["openid", "profile", "email"]
        custom_scopes = [s for s in config.allowed_scopes.split() if s]
        all_scopes = list(dict.fromkeys(base_scopes + custom_scopes))

        metadata: dict[str, Any] = {
            "issuer": config.issuer or config.server_url,
            "authorization_endpoint": auth_endpoint,
            "token_endpoint": token_endpoint,
            "scopes_supported": all_scopes,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
            ],
            "code_challenge_methods_supported": ["S256"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }

        if config.jwks_uri:
            metadata["jwks_uri"] = config.jwks_uri

        if config.auth_server_url:
            metadata["userinfo_endpoint"] = (
                f"{config.auth_server_url}/protocol/openid-connect/userinfo"
            )

        response = jsonify(metadata)
        return _set_cors_headers(response), 200

    # OAuth Authorization redirect
    @bp.route("/oauth/authorize", methods=["GET"])
    def authorize() -> Response | tuple[Response, int]:
        auth_endpoint = (
            config.oauth_authorize_url
            or f"{config.auth_server_url}/protocol/openid-connect/auth"
        )

        try:
            # Parse the base authorization endpoint
            parsed = urlparse(auth_endpoint)

            # Build query parameters from request
            params: dict[str, str] = {}
            for key, value in request.args.items():
                if isinstance(value, str):
                    params[key] = value

            # Construct new URL with parameters
            new_query = urlencode(params)
            auth_url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                )
            )

            response = redirect(auth_url, code=302)
            return _set_cors_headers(response)
        except Exception:
            response = jsonify(
                {
                    "error": "server_error",
                    "error_description": "Failed to construct authorization URL",
                }
            )
            return _set_cors_headers(response), 500

    # POST /oauth/register - Dynamic Client Registration (RFC 7591)
    @bp.route("/oauth/register", methods=["POST"])
    def register() -> tuple[Response, int]:
        body = request.get_json(silent=True) or {}

        # Extract redirect_uris from request
        redirect_uris: list[str] = []
        if isinstance(body.get("redirect_uris"), list):
            redirect_uris = [
                uri for uri in body["redirect_uris"] if isinstance(uri, str)
            ]

        # Return pre-configured credentials (stateless mode)
        registration: dict[str, Any] = {
            "client_id": config.client_id,
            "client_id_issued_at": math.floor(time.time()),
            "client_secret_expires_at": 0,  # Never expires
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": (
                "client_secret_post" if config.client_secret else "none"
            ),
        }

        if config.client_secret:
            registration["client_secret"] = config.client_secret

        response = jsonify(registration)
        return _set_cors_headers(response), 201

    return bp


def register_oauth_routes(app: Flask, config: AuthServerConfig) -> None:
    """Register OAuth discovery endpoints.

    Args:
        app: Flask application instance.
        config: Server configuration.
    """
    bp = create_oauth_blueprint(config)
    app.register_blueprint(bp)
