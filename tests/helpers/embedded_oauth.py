"""Local HTTP OAuth/MCP fixture for the actual embedded native interface."""

import base64
import hashlib
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def fetch(url, data=None, headers=None):
    request = Request(
        url,
        data=urlencode(data).encode() if data is not None else None,
        headers=headers or {},
    )
    try:
        response = build_opener(NoRedirect()).open(request, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read().decode()


def authorize(url, flow="assemble"):
    status, headers, html = fetch(url)
    assert status == 200
    assert headers.get("Referrer-Policy") == "same-origin"
    transaction = re.search(r'name="transaction" value="([^"]+)"', html)[1]
    parts = urlsplit(url)
    headers = {
        "Origin": f"{parts.scheme}://{parts.netloc}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    for source in ("a", "b"):
        status, response, _ = fetch(
            url + "/connect", {"transaction": transaction, "backend": source}, headers
        )
        assert status == 303
        status, response, _ = fetch(response["Location"])
        assert status == 302
        status, _, _ = fetch(response["Location"])
        assert status == 303
    assert fetch(url + "/continue", {"transaction": transaction}, headers)[0] == 200


class OAuthFixture:
    def __init__(self, shared=False, provider_required=False):
        self.shared = shared
        self.provider_required = provider_required
        self.provider_ready = False
        self.codes = {}
        self.tokens = {}
        self.valid_tokens = {"a": set(), "b": set()}
        self.refreshes = []
        self.initialized = []
        self.sequence = 0
        self.inventory_sources = ("a", "b")
        self.received_credentials = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                fixture.handle(self)

            def do_POST(self):
                fixture.handle(self)

            def do_DELETE(self):
                fixture.handle(self)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def issuer(self, source):
        return self.base + "/issuer/" + ("shared" if self.shared else source)

    def inventory(self):
        return json.dumps(
            {
                "succeeded": True,
                "message": "success",
                "data": {
                    "servers": [
                        {
                            "id": source,
                            "name": source,
                            "transport": "streamable_http",
                            "config": {"url": self.base + "/" + source + "/mcp"},
                        }
                        for source in self.inventory_sources
                    ]
                },
            }
        )

    def handle(self, request):
        path = urlsplit(request.path)
        raw = request.rfile.read(int(request.headers.get("Content-Length", "0")))
        source = path.path.strip("/").split("/")[0]

        def send(status, body, headers=None):
            content = (
                body.encode() if isinstance(body, str) else json.dumps(body).encode()
            )
            request.send_response(status)
            request.send_header(
                "Content-Type", (headers or {}).get("Content-Type", "application/json")
            )
            request.send_header("Content-Length", str(len(content)))
            for key, value in (headers or {}).items():
                if key != "Content-Type":
                    request.send_header(key, value)
            request.end_headers()
            request.wfile.write(content)

        if path.path.endswith("/metadata"):
            return send(
                200,
                {
                    "resource": self.base + "/" + source + "/mcp",
                    "authorization_servers": [self.issuer(source)],
                    "scopes_supported": ["openid", "resource:" + source],
                },
            )
        if path.path.startswith("/.well-known/oauth-authorization-server/"):
            issuer = self.base + path.path.replace(
                "/.well-known/oauth-authorization-server", ""
            )
            return send(
                200,
                {
                    "issuer": issuer,
                    "authorization_endpoint": issuer + "/authorize",
                    "token_endpoint": issuer + "/token",
                    "registration_endpoint": issuer + "/register",
                    "code_challenge_methods_supported": ["S256"],
                },
            )
        if path.path.endswith("/register"):
            return send(
                201,
                {"client_id": "fixture-client", "token_endpoint_auth_method": "none"},
            )
        if path.path.endswith("/authorize"):
            params = {key: value[0] for key, value in parse_qs(path.query).items()}
            assert params["code_challenge_method"] == "S256"
            self.sequence += 1
            code = "code-" + str(self.sequence)
            self.codes[code] = params
            source = "a" if "/a/mcp" in params["resource"] else "b"
            callback = (
                params["redirect_uri"]
                + "?"
                + urlencode(
                    {"state": params["state"], "code": code, "iss": self.issuer(source)}
                )
            )
            return send(302, "", {"Location": callback})
        if path.path.endswith("/token"):
            params = {key: value[0] for key, value in parse_qs(raw.decode()).items()}
            source = "a" if "/a/mcp" in params.get("resource", "") else "b"
            if params.get("grant_type") == "refresh_token":
                assert params["refresh_token"] == "refresh-" + source
                self.refreshes.append(source)
            else:
                code = self.codes.pop(params["code"])
                assert all(
                    code[key] == params[key]
                    for key in ("resource", "redirect_uri", "client_id")
                )
                challenge = (
                    base64.urlsafe_b64encode(
                        hashlib.sha256(params["code_verifier"].encode()).digest()
                    )
                    .decode()
                    .rstrip("=")
                )
                assert code["code_challenge"] == challenge
            self.sequence += 1
            token = "opaque-" + source + "-" + str(self.sequence)
            self.tokens[source] = token
            self.valid_tokens[source].add(token)
            return send(
                200,
                {
                    "access_token": token,
                    "refresh_token": "refresh-" + source,
                    "token_type": "Bearer",
                    "expires_in": 600,
                },
            )
        if path.path.endswith("/mcp"):
            authorization = request.headers.get("Authorization", "")
            token = (
                authorization[7:]
                if authorization.startswith("Bearer ")
                else authorization
            )
            self.received_credentials.append((source, token))
            valid = (
                not token
                if source == "public"
                else token in self.valid_tokens.get(source, set())
            )
            if not valid:
                return send(
                    401,
                    {},
                    {
                        "WWW-Authenticate": f'Bearer resource_metadata="{self.base}/{source}/metadata"'
                    },
                )
            if request.command == "GET":
                if self.provider_required and not self.provider_ready:
                    event = {
                        "jsonrpc": "2.0",
                        "id": "provider",
                        "method": "elicitation/create",
                        "params": {
                            "elicitationId": "provider",
                            "mode": "url",
                            "url": "https://provider.example/consent",
                            "message": "Connect provider",
                        },
                    }
                    return send(
                        200,
                        "event: message\ndata: " + json.dumps(event) + "\n\n",
                        {"Content-Type": "text/event-stream"},
                    )
                return send(405, {})
            if request.command == "DELETE":
                return send(200, {})
            rpc = json.loads(raw)
            if rpc["method"] == "initialize":
                self.initialized.append(source)
                return send(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": rpc["id"],
                        "result": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": source, "version": "1"},
                        },
                    },
                )
            if rpc["method"] == "tools/list":
                return send(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": rpc["id"],
                        "result": {
                            "tools": [
                                {
                                    "name": "tool_" + source,
                                    "description": "Fixture tool",
                                    "inputSchema": {"type": "object", "properties": {}},
                                }
                            ]
                        },
                    },
                )
            return send(202, "")
        return send(404, {})
