"""Local integration test for OAuth-aware create_with_url."""

import json
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import gopher_mcp_python.agent as agent_module
import gopher_mcp_python.oauth_resolver as oauth_resolver
from gopher_mcp_python import GopherAgent


PROVIDER = "AnthropicProvider"
MODEL = "test-model"


class FakeLibrary:
    def __init__(self) -> None:
        self.calls = []

    def agent_create_by_url(self, provider, model, url, runtime_options=None):
        self.calls.append(("url", provider, model, url, runtime_options))
        return 3001

    def agent_release(self, handle):
        self.calls.append(("release", handle))

    def get_last_error_message(self):
        return None

    def clear_error(self):
        return None


def test_local_oauth_flow_obtains_token_before_url_agent_creation(monkeypatch) -> None:
    server = _FakeOAuthServer.start()
    fake = FakeLibrary()
    opened_authorization_urls = []

    def open_authorization_url(url, open_browser=None):
        opened_authorization_urls.append(url)
        urllib.request.urlopen(url).read()
        return {"opened": True, "url": url}

    monkeypatch.setattr(agent_module, "_initialized", True)
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary,
        "get_instance",
        staticmethod(lambda: fake),
    )
    monkeypatch.setattr(oauth_resolver, "open_authorization_url", open_authorization_url)

    try:
        agent = GopherAgent.create_with_url(PROVIDER, MODEL, server.mcp_url)
    finally:
        oauth_resolver.set_oauth_resolver_hooks_for_test()
        oauth_resolver.set_oauth_url_runtime_options_resolver_for_test()
        server.close()

    assert len(opened_authorization_urls) == 1
    authorization_url = urllib.parse.urlparse(opened_authorization_urls[0])
    params = urllib.parse.parse_qs(authorization_url.query)
    assert authorization_url.path == "/authorize"
    assert params["resource"] == [server.mcp_url]
    assert params["scope"] == ["openid email"]

    call = fake.calls[0]
    assert call[:4] == ("url", PROVIDER, MODEL, server.mcp_url)
    assert call[4].access_token == "local-access-token"
    agent.dispose()


class _FakeOAuthServer:
    def __init__(self, server: ThreadingHTTPServer) -> None:
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        self.base_url = f"http://127.0.0.1:{server.server_address[1]}"
        self.mcp_url = f"{self.base_url}/mcp"

    @classmethod
    def start(cls) -> "_FakeOAuthServer":
        owner = {"base_url": ""}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                _handle_fake_oauth_request(self, owner["base_url"])

            def do_POST(self):
                _handle_fake_oauth_request(self, owner["base_url"])

        server = cls(ThreadingHTTPServer(("127.0.0.1", 0), Handler))
        owner["base_url"] = server.base_url
        return server

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1)


def _handle_fake_oauth_request(handler: BaseHTTPRequestHandler, base_url: str) -> None:
    parsed = urllib.parse.urlparse(handler.path)

    if handler.command == "POST" and parsed.path == "/mcp":
        handler.send_response(401)
        handler.send_header(
            "WWW-Authenticate",
            f'Bearer realm="mcp", resource_metadata="'
            f'{base_url}/.well-known/oauth-protected-resource/mcp"',
        )
        handler.end_headers()
        return

    if (
        handler.command == "GET"
        and parsed.path == "/.well-known/oauth-protected-resource/mcp"
    ):
        _json(
            handler,
            {
                "resource": f"{base_url}/mcp",
                "authorization_servers": [base_url],
                "scopes_supported": ["openid", "email"],
            },
        )
        return

    if (
        handler.command == "GET"
        and parsed.path == "/.well-known/oauth-authorization-server"
    ):
        _json(
            handler,
            {
                "issuer": base_url,
                "authorization_endpoint": f"{base_url}/authorize",
                "token_endpoint": f"{base_url}/token",
                "registration_endpoint": f"{base_url}/register",
                "scopes_supported": ["openid", "email"],
            },
        )
        return

    if handler.command == "POST" and parsed.path == "/register":
        _json(handler, {"client_id": "local-client"})
        return

    if handler.command == "GET" and parsed.path == "/authorize":
        params = urllib.parse.parse_qs(parsed.query)
        redirect_uri = params.get("redirect_uri", [None])[0]
        state = params.get("state", [None])[0]
        if redirect_uri is None or state is None:
            _text(handler, 400, "missing redirect_uri or state")
            return

        callback = urllib.parse.urlparse(redirect_uri)
        callback_query = urllib.parse.urlencode(
            {"code": "local-auth-code", "state": state}
        )
        location = urllib.parse.urlunparse(callback._replace(query=callback_query))
        handler.send_response(302)
        handler.send_header("Location", location)
        handler.end_headers()
        return

    if handler.command == "POST" and parsed.path == "/token":
        body = _read_body(handler)
        form = urllib.parse.parse_qs(body)
        if form.get("code") != ["local-auth-code"]:
            _text(handler, 400, "bad code")
            return
        _json(
            handler,
            {
                "access_token": "local-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )
        return

    _text(handler, 404, "not found")


def _json(handler: BaseHTTPRequestHandler, body) -> None:
    data = json.dumps(body).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _text(handler: BaseHTTPRequestHandler, status: int, body: str) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _read_body(handler: BaseHTTPRequestHandler) -> str:
    length = int(handler.headers.get("Content-Length", "0"))
    return handler.rfile.read(length).decode("utf-8")
