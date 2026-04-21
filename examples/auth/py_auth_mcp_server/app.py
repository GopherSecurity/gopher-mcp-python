"""MCP Server using Server + StreamableHTTP transport.

Follows the official Python MCP SDK pattern (simple-streamablehttp example)
with GopherAuth for OAuth discovery endpoints.
"""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope as ASGIScope, Send

from gopher_mcp_python.auth import GopherAuth
from gopher_mcp_python.ffi.auth.loader import (
    gopher_auth_build_protected_resource_metadata,
    gopher_auth_build_oauth_server_metadata,
    gopher_auth_build_oidc_discovery_metadata,
    gopher_auth_url_encode,
)


def create_app(
    config_path: str | None = None,
) -> tuple[Starlette, GopherAuth, int, str]:
    """Create the Starlette ASGI app with MCP + OAuth routes."""

    # Initialize GopherAuth
    auth = GopherAuth(config_path=config_path)
    auth.initialize()

    cfg = auth.native_config
    port = cfg.get_int("port") if cfg else 3001
    host = cfg.get_string("host") if cfg else "0.0.0.0"
    server_url = cfg.get_string("server_url") if cfg else f"http://localhost:{port}"
    scopes = cfg.get_string("allowed_scopes") if cfg else ""
    issuer = cfg.get_string("issuer") if cfg else server_url
    jwks_uri = cfg.get_string("jwks_uri") if cfg else ""
    auth_server_url = cfg.get_string("auth_server_url") if cfg else ""
    oauth_authorize_url = cfg.get_string("oauth_authorize_url") if cfg else ""
    oauth_token_url = cfg.get_string("oauth_token_url") if cfg else ""
    client_id = cfg.get_string("client_id") if cfg else ""
    client_secret = cfg.get_string("client_secret") if cfg else ""

    # ── MCP Server ─────────────────────────────────────────────────

    mcp_server = FastMCP(
        "py-auth-mcp-server",
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )

    @mcp_server.tool()
    def get_weather(city: str) -> str:
        """Get current weather for a city. No auth required."""
        h = sum(ord(c) for c in city)
        conds = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Windy"]
        return f"Weather in {city}: {10+h%26}C, {conds[h%len(conds)]}, Humidity: {40+h%40}%"

    @mcp_server.tool()
    def get_forecast(city: str) -> str:
        """Get 5-day forecast. Requires mcp:read scope."""
        h = sum(ord(c) for c in city)
        conds = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Windy"]
        lines = [
            f"{d}: {10+((h+i*7)%26)+5}C/{10+((h+i*7)%26)-5}C {conds[(h+i)%len(conds)]}"
            for i, d in enumerate(["Today", "Tomorrow", "Day 3", "Day 4", "Day 5"])
        ]
        return f"5-Day Forecast for {city}:\n" + "\n".join(lines)

    @mcp_server.tool()
    def get_weather_alerts(region: str) -> str:
        """Get weather alerts. Requires mcp:admin scope."""
        h = sum(ord(c) for c in region)
        if h % 3 == 0:
            return f"Alert for {region}: Heat Warning"
        elif h % 3 == 1:
            return f"Alerts for {region}: Storm Watch, Wind Advisory"
        return f"No active alerts for {region}"

    # Get the StreamableHTTP Starlette app from FastMCP
    mcp_app = mcp_server.streamable_http_app()

    # ── OAuth Discovery Routes ─────────────────────────────────────

    def _cors() -> dict:
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Mcp-Session-Id",
            "Access-Control-Expose-Headers": "WWW-Authenticate, Mcp-Session-Id",
        }

    async def protected_resource(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors())
        meta = gopher_auth_build_protected_resource_metadata(
            f"{server_url}/mcp", server_url, scopes or None
        )
        return JSONResponse(meta, headers=_cors())

    async def auth_server_meta(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors())
        meta = gopher_auth_build_oauth_server_metadata(
            issuer,
            oauth_authorize_url or f"{server_url}/oauth/authorize",
            oauth_token_url or f"{server_url}/oauth/token",
            f"{server_url}/oauth/register",
            jwks_uri or None,
            scopes or None,
        )
        if auth_server_url:
            meta["end_session_endpoint"] = (
                f"{auth_server_url}/protocol/openid-connect/logout"
            )
        return JSONResponse(meta, headers=_cors())

    async def oidc_discovery(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors())
        userinfo = (
            f"{auth_server_url}/protocol/openid-connect/userinfo"
            if auth_server_url
            else None
        )
        end_session = (
            f"{auth_server_url}/protocol/openid-connect/logout"
            if auth_server_url
            else None
        )
        meta = gopher_auth_build_oidc_discovery_metadata(
            issuer,
            oauth_authorize_url or f"{server_url}/oauth/authorize",
            oauth_token_url or f"{server_url}/oauth/token",
            jwks_uri or None,
            f"{server_url}/oauth/register",
            scopes or None,
            userinfo,
            end_session,
        )
        return JSONResponse(meta, headers=_cors())

    async def oauth_authorize(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors())
        q = request.query_params
        target = (
            oauth_authorize_url or f"{auth_server_url}/protocol/openid-connect/auth"
        )
        url = f"{target}?client_id={gopher_auth_url_encode(q.get('client_id', ''))}"
        for k in ["redirect_uri", "scope", "response_type", "state", "code_challenge"]:
            if q.get(k):
                url += f"&{k}={gopher_auth_url_encode(q[k])}"
        if q.get("code_challenge_method"):
            url += f"&code_challenge_method={q['code_challenge_method']}"
        return RedirectResponse(url, status_code=302)

    async def oauth_token(request: Request) -> Response:
        """Proxy token requests to IdP token endpoint.

        Required for MCP clients (claude.ai) that use the discovered
        token_endpoint URL and need client credentials injected.
        """
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors())
        token_url = (
            oauth_token_url or f"{auth_server_url}/protocol/openid-connect/token"
        )
        try:
            body = await request.body()
            from urllib.parse import parse_qs, urlencode

            params = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            flat: dict[str, str] = {k: v[0] for k, v in params.items()}
            # Inject client credentials if not provided
            if "client_id" not in flat and client_id:
                flat["client_id"] = client_id
            if "client_secret" not in flat and client_secret:
                flat["client_secret"] = client_secret

            print(f"🔑 Token proxy → {token_url}")
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    token_url,
                    content=urlencode(flat),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30,
                )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers={
                    **_cors(),
                    "Content-Type": resp.headers.get(
                        "content-type", "application/json"
                    ),
                },
            )
        except Exception as e:
            print(f"❌ Token proxy error: {e}")
            return JSONResponse(
                {"error": "token_proxy_error", "error_description": str(e)},
                status_code=502,
                headers=_cors(),
            )

    async def oauth_register(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors())
        body = (
            await request.json()
            if "json" in (request.headers.get("content-type") or "")
            else {}
        )
        return JSONResponse(
            {
                "client_id": client_id,
                **({"client_secret": client_secret} if client_secret else {}),
                "client_id_issued_at": int(time.time()),
                "client_secret_expires_at": 0,
                "redirect_uris": body.get("redirect_uris", []),
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": (
                    "client_secret_post" if client_secret else "none"
                ),
            },
            status_code=201,
            headers=_cors(),
        )

    async def health(request: Request) -> Response:
        return JSONResponse({"status": "healthy", "timestamp": int(time.time())})

    # ── Auth Middleware for /mcp ────────────────────────────────────

    class RequestLoggingMiddleware:
        """Log all incoming requests for debugging."""

        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(
            self, scope: ASGIScope, receive: Receive, send: Send
        ) -> None:
            if scope["type"] == "http":
                path = scope.get("path", "")
                method = scope.get("method", "")
                headers = dict(scope.get("headers", []))
                session = headers.get(b"mcp-session-id", b"none").decode(
                    "utf-8", errors="ignore"
                )
                has_auth = b"authorization" in headers
                print(
                    f"🌐 {method} {path} "
                    f"[session: {session}] [auth: {'yes' if has_auth else 'no'}]"
                )
            await self.app(scope, receive, send)

    class McpAuthMiddleware:
        """Validates Bearer token on /mcp. Returns 401 to trigger OAuth flow."""

        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(
            self, scope: ASGIScope, receive: Receive, send: Send
        ) -> None:
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            path = scope.get("path", "")
            method = scope.get("method", "")

            # Only protect /mcp path
            if not path.startswith("/mcp"):
                await self.app(scope, receive, send)
                return

            # Let OPTIONS through (CORS preflight)
            if method == "OPTIONS":
                await self.app(scope, receive, send)
                return

            # Skip auth if disabled
            if auth.is_disabled:
                await self.app(scope, receive, send)
                return

            # Check for Bearer token
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode(
                "utf-8", errors="ignore"
            )

            if not auth_header.startswith("Bearer "):
                www_auth = auth.get_www_authenticate_header(
                    error="invalid_request",
                    error_description="Missing bearer token",
                )
                response = JSONResponse(
                    {
                        "error": "invalid_request",
                        "error_description": "Missing bearer token",
                    },
                    status_code=401,
                    headers={"WWW-Authenticate": www_auth, **_cors()},
                )
                await response(scope, receive, send)
                return

            # Validate token
            token = auth_header[7:].strip()
            try:
                auth.validate_token(token)
            except Exception as e:
                www_auth = auth.get_www_authenticate_header(
                    error="invalid_token",
                    error_description=str(e),
                )
                response = JSONResponse(
                    {"error": "invalid_token", "error_description": str(e)},
                    status_code=401,
                    headers={"WWW-Authenticate": www_auth, **_cors()},
                )
                await response(scope, receive, send)
                return

            await self.app(scope, receive, send)

    # ── Starlette App (OAuth routes + MCP mount) ───────────────────

    routes = [
        Route(
            "/.well-known/oauth-protected-resource",
            protected_resource,
            methods=["GET", "OPTIONS"],
        ),
        Route(
            "/.well-known/oauth-protected-resource/mcp",
            protected_resource,
            methods=["GET", "OPTIONS"],
        ),
        Route(
            "/.well-known/oauth-authorization-server",
            auth_server_meta,
            methods=["GET", "OPTIONS"],
        ),
        Route(
            "/.well-known/openid-configuration",
            oidc_discovery,
            methods=["GET", "OPTIONS"],
        ),
        Route("/oauth/authorize", oauth_authorize, methods=["GET", "OPTIONS"]),
        Route("/oauth/token", oauth_token, methods=["POST", "OPTIONS"]),
        Route("/oauth/register", oauth_register, methods=["POST", "OPTIONS"]),
        Route("/health", health, methods=["GET"]),
        Mount("/", app=mcp_app),
    ]

    app = Starlette(
        routes=routes,
        lifespan=mcp_app.router.lifespan_context,
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                allow_headers=["*"],
                expose_headers=["Mcp-Session-Id"],
            ),
            Middleware(RequestLoggingMiddleware),
            Middleware(McpAuthMiddleware),
        ],
    )

    return app, auth, port, host


def main() -> None:
    """Run the MCP server."""
    config_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(Path(__file__).parent.parent / "server.config")
    )

    print("========================================")
    print("   Python Auth MCP Server")
    print("========================================")

    app, auth, port, host = create_app(config_path)

    print(f"Server: http://{host}:{port}")
    print(f"MCP: http://{host}:{port}/mcp")
    print(f"Config: {config_path}")
    print(f"Auth: {'DISABLED' if auth.is_disabled else 'ENABLED'}")
    print()

    def shutdown_handler(sig, frame):
        print("\nShutting down...")
        auth.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
