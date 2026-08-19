"""Protected MCP endpoint harness for OAuth auto tests."""

from __future__ import annotations

import json
import threading
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Dict, List, Optional, Type


@dataclass(frozen=True)
class CustomProtectedMcpEndpointsOptions:
    authorization_server: str
    access_token: str
    scopes_supported: Optional[List[str]] = None
    protected_resource_metadata: Optional[Dict[str, object]] = None


@dataclass(frozen=True)
class CustomProtectedMcpEndpoint:
    kind: str
    base_url: str
    mcp_url: str
    resource_metadata_url: str


@dataclass
class _EndpointState:
    kind: str
    base_url: str
    authorization_server: str
    access_token: str
    scopes_supported: List[str]
    protected_resource_metadata: Optional[Dict[str, object]]


class _RunningEndpoint:
    def __init__(
        self,
        endpoint: CustomProtectedMcpEndpoint,
        server: ThreadingHTTPServer,
        thread: threading.Thread,
    ) -> None:
        self.endpoint = endpoint
        self._server = server
        self._thread = thread

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)


class CustomProtectedMcpEndpoints:
    def __init__(
        self,
        server: _RunningEndpoint,
        gateway: _RunningEndpoint,
    ) -> None:
        self._server_endpoint = server
        self._gateway_endpoint = gateway
        self.server = server.endpoint
        self.gateway = gateway.endpoint

    def close(self) -> None:
        self._server_endpoint.close()
        self._gateway_endpoint.close()

    def __enter__(self) -> "CustomProtectedMcpEndpoints":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()


def start_custom_protected_mcp_endpoints(
    options: CustomProtectedMcpEndpointsOptions,
) -> CustomProtectedMcpEndpoints:
    server = _start_custom_protected_mcp_endpoint("server", options)
    try:
        gateway = _start_custom_protected_mcp_endpoint("gateway", options)
    except Exception:
        server.close()
        raise
    return CustomProtectedMcpEndpoints(server, gateway)


def _start_custom_protected_mcp_endpoint(
    kind: str,
    options: CustomProtectedMcpEndpointsOptions,
) -> _RunningEndpoint:
    state = _EndpointState(
        kind=kind,
        base_url="",
        authorization_server=options.authorization_server,
        access_token=options.access_token,
        scopes_supported=options.scopes_supported or ["openid", "profile", "email"],
        protected_resource_metadata=options.protected_resource_metadata,
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            _handle_endpoint_request(self, state)

        def do_POST(self) -> None:
            _handle_endpoint_request(self, state)

    http_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.base_url = f"http://127.0.0.1:{http_server.server_address[1]}"
    thread = threading.Thread(target=http_server.serve_forever, daemon=True)
    thread.start()
    endpoint = CustomProtectedMcpEndpoint(
        kind=kind,
        base_url=state.base_url,
        mcp_url=f"{state.base_url}/mcp",
        resource_metadata_url=(
            f"{state.base_url}/.well-known/oauth-protected-resource/mcp"
        ),
    )
    return _RunningEndpoint(endpoint, http_server, thread)


def _handle_endpoint_request(
    handler: BaseHTTPRequestHandler,
    state: _EndpointState,
) -> None:
    parsed = urllib.parse.urlparse(handler.path)

    if (
        handler.command == "GET"
        and parsed.path == "/.well-known/oauth-protected-resource/mcp"
    ):
        _json(handler, 200, _protected_resource_metadata(state))
        return

    if handler.command == "POST" and parsed.path == "/mcp":
        if not _has_expected_bearer_token(handler, state.access_token):
            handler.send_response(401)
            handler.send_header(
                "WWW-Authenticate",
                'Bearer realm="mcp", resource_metadata="'
                f'{state.base_url}/.well-known/oauth-protected-resource/mcp"',
            )
            handler.end_headers()
            return

        _json(
            handler,
            200,
            {
                "jsonrpc": "2.0",
                "id": "custom-protected-mcp-response",
                "result": {
                    "endpoint": state.kind,
                    "authenticated": True,
                },
            },
        )
        return

    handler.send_response(404)
    handler.end_headers()


def _protected_resource_metadata(state: _EndpointState) -> Dict[str, object]:
    if state.protected_resource_metadata is not None:
        return state.protected_resource_metadata
    return {
        "resource": f"{state.base_url}/mcp",
        "authorization_servers": [state.authorization_server],
        "scopes_supported": state.scopes_supported,
    }


def _has_expected_bearer_token(
    handler: BaseHTTPRequestHandler,
    access_token: str,
) -> bool:
    return handler.headers.get("Authorization") == f"Bearer {access_token}"


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
