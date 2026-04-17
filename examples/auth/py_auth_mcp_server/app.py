"""MCP Server using FastMCP with Streamable HTTP transport.

Mirrors the JS auth example pattern using the official Python MCP SDK.
OAuth discovery endpoints registered via mcp.custom_route().
"""

from __future__ import annotations

import json
import signal
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from gopher_mcp_python.auth import GopherAuth
from gopher_mcp_python.ffi.auth.loader import (
    gopher_auth_build_protected_resource_metadata,
    gopher_auth_build_oauth_server_metadata,
    gopher_auth_build_oidc_discovery_metadata,
    gopher_auth_url_encode,
)


def create_server(config_path: str | None = None) -> tuple[FastMCP, GopherAuth]:
    """Create MCP server and GopherAuth instance."""
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

    mcp = FastMCP(
        "py-auth-mcp-server",
        host=host,
        port=port,
        json_response=True,
    )

    # ── Weather Tools ──────────────────────────────────────────────

    @mcp.tool()
    def get_weather(city: str) -> str:
        """Get current weather for a city. No auth required."""
        h = sum(ord(c) for c in city)
        conds = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Windy"]
        return f"Weather in {city}: {10 + h % 26}C, {conds[h % len(conds)]}, Humidity: {40 + h % 40}%"

    @mcp.tool()
    def get_forecast(city: str) -> str:
        """Get 5-day forecast. Requires mcp:read scope."""
        h = sum(ord(c) for c in city)
        conds = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy", "Windy"]
        lines = [f"{d}: {10+((h+i*7)%26)+5}C/{10+((h+i*7)%26)-5}C {conds[(h+i)%len(conds)]}"
                 for i, d in enumerate(["Today", "Tomorrow", "Day 3", "Day 4", "Day 5"])]
        return f"5-Day Forecast for {city}:\n" + "\n".join(lines)

    @mcp.tool()
    def get_weather_alerts(region: str) -> str:
        """Get weather alerts. Requires mcp:admin scope."""
        h = sum(ord(c) for c in region)
        if h % 3 == 0:
            return f"Alert for {region}: Heat Warning"
        elif h % 3 == 1:
            return f"Alerts for {region}: Storm Watch, Wind Advisory"
        return f"No active alerts for {region}"

    # ── OAuth Discovery Endpoints ──────────────────────────────────

    def _cors_headers() -> dict:
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Mcp-Session-Id",
            "Access-Control-Expose-Headers": "WWW-Authenticate, Mcp-Session-Id",
            "Access-Control-Max-Age": "86400",
        }

    @mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    @mcp.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET", "OPTIONS"])
    async def protected_resource(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers())
        meta = gopher_auth_build_protected_resource_metadata(
            f"{server_url}/mcp", server_url, scopes or None)
        return JSONResponse(meta, headers=_cors_headers())

    @mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])
    async def auth_server_metadata(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers())
        meta = gopher_auth_build_oauth_server_metadata(
            issuer, oauth_authorize_url or f"{server_url}/oauth/authorize",
            oauth_token_url or f"{server_url}/oauth/token",
            f"{server_url}/oauth/register", jwks_uri or None, scopes or None)
        if auth_server_url:
            meta["end_session_endpoint"] = f"{auth_server_url}/protocol/openid-connect/logout"
        return JSONResponse(meta, headers=_cors_headers())

    @mcp.custom_route("/.well-known/openid-configuration", methods=["GET", "OPTIONS"])
    async def oidc_discovery(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers())
        userinfo = f"{auth_server_url}/protocol/openid-connect/userinfo" if auth_server_url else None
        end_session = f"{auth_server_url}/protocol/openid-connect/logout" if auth_server_url else None
        meta = gopher_auth_build_oidc_discovery_metadata(
            issuer, oauth_authorize_url or f"{server_url}/oauth/authorize",
            oauth_token_url or f"{server_url}/oauth/token",
            jwks_uri or None, f"{server_url}/oauth/register",
            scopes or None, userinfo, end_session)
        return JSONResponse(meta, headers=_cors_headers())

    @mcp.custom_route("/oauth/authorize", methods=["GET", "OPTIONS"])
    async def oauth_authorize(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers())
        q = request.query_params
        target = oauth_authorize_url or f"{auth_server_url}/protocol/openid-connect/auth"
        url = f"{target}?client_id={gopher_auth_url_encode(q.get('client_id', ''))}"
        for k in ["redirect_uri", "scope", "response_type", "state", "code_challenge"]:
            if q.get(k):
                url += f"&{k}={gopher_auth_url_encode(q[k])}"
        if q.get("code_challenge_method"):
            url += f"&code_challenge_method={q['code_challenge_method']}"
        return RedirectResponse(url, status_code=302)

    @mcp.custom_route("/oauth/register", methods=["POST", "OPTIONS"])
    async def oauth_register(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_cors_headers())
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        resp = {
            "client_id": client_id,
            **({"client_secret": client_secret} if client_secret else {}),
            "client_id_issued_at": int(time.time()),
            "client_secret_expires_at": 0,
            "redirect_uris": body.get("redirect_uris", []),
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post" if client_secret else "none",
        }
        return JSONResponse(resp, status_code=201, headers=_cors_headers())

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> Response:
        return JSONResponse({"status": "healthy", "service": "py-auth-mcp-server",
                            "timestamp": int(time.time())})

    return mcp, auth


def main() -> None:
    """Run the MCP server with Streamable HTTP transport."""
    config_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).parent.parent / "server.config"
    )

    print("========================================")
    print("   Python Auth MCP Server")
    print("========================================")

    mcp, auth = create_server(config_path)

    print(f"Server: http://{mcp.settings.host}:{mcp.settings.port}")
    print(f"MCP: http://{mcp.settings.host}:{mcp.settings.port}/mcp")
    print(f"Config: {config_path}")
    print(f"Auth: {'DISABLED' if auth.is_disabled else 'ENABLED'}")
    print()

    def shutdown_handler(sig, frame):
        print("\nShutting down...")
        auth.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
