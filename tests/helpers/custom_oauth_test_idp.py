"""Deterministic OAuth/OIDC IdP harness for tests."""

from __future__ import annotations

import json
import threading
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Dict, List, Optional, Type


OAUTH_TEST_CLIENT_ID = "test-client"
OAUTH_TEST_CLIENT_SECRET = "test-secret"
OAUTH_TEST_REFRESH_TOKEN = "test-refresh-token"
OAUTH_TEST_ACCESS_TOKEN = "test-access-token"


@dataclass(frozen=True)
class CustomOAuthTestIdpOptions:
    client_id: str = OAUTH_TEST_CLIENT_ID
    client_secret: str = OAUTH_TEST_CLIENT_SECRET
    refresh_token: str = OAUTH_TEST_REFRESH_TOKEN
    access_token: str = OAUTH_TEST_ACCESS_TOKEN
    scope: str = "openid profile email"
    expires_in: int = 3600


@dataclass
class _CustomOAuthTestIdpState:
    issuer: str
    client_id: str
    client_secret: str
    refresh_token: str
    access_token: str
    scope: str
    expires_in: int


class CustomOAuthTestIdp:
    def __init__(
        self,
        server: ThreadingHTTPServer,
        thread: threading.Thread,
        state: _CustomOAuthTestIdpState,
    ) -> None:
        self._server = server
        self._thread = thread
        self._state = state
        self.issuer = state.issuer
        self.open_id_configuration_url = (
            f"{self.issuer}/.well-known/openid-configuration"
        )
        self.authorization_server_metadata_url = (
            f"{self.issuer}/.well-known/oauth-authorization-server"
        )
        self.authorization_endpoint = f"{self.issuer}/authorize"
        self.token_endpoint = f"{self.issuer}/token"
        self.jwks_url = f"{self.issuer}/jwks"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)

    def __enter__(self) -> "CustomOAuthTestIdp":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()


def start_custom_oauth_test_idp(
    options: Optional[CustomOAuthTestIdpOptions] = None,
) -> CustomOAuthTestIdp:
    resolved = options or CustomOAuthTestIdpOptions()
    state = _CustomOAuthTestIdpState(
        issuer="",
        client_id=resolved.client_id,
        client_secret=resolved.client_secret,
        refresh_token=resolved.refresh_token,
        access_token=resolved.access_token,
        scope=resolved.scope,
        expires_in=resolved.expires_in,
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            _handle_get(self, state)

        def do_POST(self) -> None:
            _handle_post(self, state)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.issuer = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return CustomOAuthTestIdp(server, thread, state)


def _handle_get(
    handler: BaseHTTPRequestHandler,
    state: _CustomOAuthTestIdpState,
) -> None:
    parsed = urllib.parse.urlparse(handler.path)
    if parsed.path in (
        "/.well-known/openid-configuration",
        "/.well-known/oauth-authorization-server",
    ):
        _json(handler, 200, _authorization_server_metadata(state))
        return

    if parsed.path == "/jwks":
        _json(handler, 200, {"keys": []})
        return

    if parsed.path == "/authorize":
        _json(
            handler,
            200,
            {
                "issuer": state.issuer,
                "message": "custom OAuth test IdP authorization endpoint",
            },
        )
        return

    handler.send_response(404)
    handler.end_headers()


def _handle_post(
    handler: BaseHTTPRequestHandler,
    state: _CustomOAuthTestIdpState,
) -> None:
    parsed = urllib.parse.urlparse(handler.path)
    if parsed.path != "/token":
        handler.send_response(404)
        handler.end_headers()
        return

    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length).decode("utf-8")
    params = urllib.parse.parse_qs(body)

    grant_type = _single(params, "grant_type")
    client_id = _single(params, "client_id")
    client_secret = _single(params, "client_secret")
    refresh_token = _single(params, "refresh_token")

    if grant_type is None:
        _oauth_error(handler, 400, "invalid_request")
        return
    if grant_type != "refresh_token":
        _oauth_error(handler, 400, "unsupported_grant_type")
        return
    if client_id is None or client_secret is None or refresh_token is None:
        _oauth_error(handler, 400, "invalid_request")
        return
    if client_id != state.client_id or client_secret != state.client_secret:
        _oauth_error(handler, 401, "invalid_client")
        return
    if refresh_token != state.refresh_token:
        _oauth_error(handler, 400, "invalid_grant")
        return

    _json(
        handler,
        200,
        {
            "access_token": state.access_token,
            "token_type": "Bearer",
            "expires_in": state.expires_in,
            "scope": state.scope,
        },
    )


def _authorization_server_metadata(
    state: _CustomOAuthTestIdpState,
) -> Dict[str, object]:
    return {
        "issuer": state.issuer,
        "authorization_endpoint": f"{state.issuer}/authorize",
        "token_endpoint": f"{state.issuer}/token",
        "jwks_uri": f"{state.issuer}/jwks",
        "registration_endpoint": f"{state.issuer}/register",
        "scopes_supported": ["openid", "profile", "email"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["refresh_token"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
    }


def _single(params: Dict[str, List[str]], name: str) -> Optional[str]:
    values = params.get(name)
    return values[0] if values else None


def _oauth_error(
    handler: BaseHTTPRequestHandler,
    status: int,
    error: str,
) -> None:
    _json(handler, status, {"error": error})


def _json(
    handler: BaseHTTPRequestHandler,
    status: int,
    body: object,
) -> None:
    data = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
