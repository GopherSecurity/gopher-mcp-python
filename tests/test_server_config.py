"""Inventory method negotiation preserves selectors and one bounded request budget."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

import gopher_mcp_python.server_config as module
from gopher_mcp_python.errors import AgentError, ApiKeyError
from gopher_mcp_python.server_config import ServerConfig, ServerConfigRoute


class FakeResponse:
    def __init__(self, body=None):
        self.body = (
            body if body is not None else b'{"succeeded":true,"data":{"servers":[]}}'
        )
        self.closed = False
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def read(self):
        self.reads += 1
        return self.body

    def close(self):
        self.closed = True


def gateway_response(value):
    return FakeResponse(
        json.dumps(
            {
                "succeeded": True,
                "data": {
                    "servers": [
                        {
                            "id": value,
                            "name": value,
                            "transport": "http",
                            "config": {
                                "url": "https://mcp.example/v1/mcp/gateways/g1/mcp"
                            },
                        }
                    ]
                },
            }
        ).encode()
    )


def http_error(status, response=None):
    return HTTPError(
        "https://secret.invalid/echo-key",
        status,
        "secret-body",
        {"Location": "https://untrusted.invalid"},
        response if response is not None else FakeResponse(b"echoed-secret"),
    )


def test_empty_selection_uses_one_get_without_body_or_content_type(monkeypatch):
    monkeypatch.delenv("GOPHER_SDK_TEST", raising=False)
    calls = []

    def request(req, timeout):
        calls.append((req, timeout))
        return FakeResponse()

    monkeypatch.setattr(module, "urlopen", request)
    ServerConfig.fetch("secret")
    assert len(calls) == 1
    req, timeout = calls[0]
    assert req.method == "GET"
    assert req.full_url == "https://api.gopher.security/v1/mcp-servers"
    assert req.data is None
    assert req.get_header("Content-type") is None
    assert req.get_header("Authorization") == "Bearer secret"
    assert req.get_header("Accept") == "application/json"
    assert 0 < timeout <= 30


@pytest.mark.parametrize(
    "field", ["serverId", "serverName", "gatewayId", "gatewayName"]
)
def test_one_deduplicated_selector_uses_exact_percent_encoded_get_query(
    monkeypatch, field
):
    value = " Team & Ops/+?#=%ü "
    requests = []

    def request(req, timeout):
        requests.append(req)
        return gateway_response(value)

    monkeypatch.setenv("GOPHER_SDK_TEST", "true")
    monkeypatch.setattr(module, "urlopen", request)
    ServerConfig.fetch(
        "secret", ServerConfigRoute(field, value), {field: [value, value]}
    )
    assert len(requests) == 1
    req = requests[0]
    assert req.method == "GET"
    assert req.full_url.startswith("https://api-test.gopher.security/v1/mcp-servers?")
    assert parse_qs(urlsplit(req.full_url).query) == {field: [value]}
    assert "%20" in req.full_url and "%2F" in req.full_url and "%2B" in req.full_url
    assert req.data is None


def test_post_merges_multiple_selectors_once(monkeypatch):
    requests = []

    def request(req, timeout):
        requests.append((req, timeout))
        return FakeResponse()

    monkeypatch.setenv("GOPHER_SDK_TEST", "true")
    monkeypatch.setattr(module, "urlopen", request)
    ServerConfig.fetch(
        "secret", ServerConfigRoute("serverName", "Draft Mail"), {"serverId": ["s1"]}
    )
    assert len(requests) == 1
    req, timeout = requests[0]
    assert 0 < timeout <= 30
    assert req.full_url == "https://api-test.gopher.security/v1/mcp-servers"
    assert req.method == "POST"
    assert req.headers["Authorization"] == "Bearer secret"
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data) == {
        "serverId": ["s1"],
        "serverName": ["Draft Mail"],
        "gatewayId": [],
        "gatewayName": [],
    }


@pytest.mark.parametrize(
    "selection", [{}, {"serverName": [" Draft Mail ", " Draft Mail "]}]
)
def test_get_405_retries_once_as_same_host_post_with_exact_selection(
    monkeypatch, selection
):
    monkeypatch.delenv("GOPHER_SDK_TEST", raising=False)
    calls = []
    refused = FakeResponse(b"echoed-private-body")

    def request(req, timeout):
        calls.append(req)
        if len(calls) == 1:
            raise http_error(405, refused)
        return FakeResponse()

    monkeypatch.setattr(module, "urlopen", request)
    ServerConfig.fetch("secret", selection=selection)
    assert [req.method for req in calls] == ["GET", "POST"]
    assert calls[1].full_url == "https://api.gopher.security/v1/mcp-servers"
    assert (
        calls[1].get_header("Authorization")
        == calls[0].get_header("Authorization")
        == "Bearer secret"
    )
    assert json.loads(calls[1].data) == {
        "serverId": [],
        "serverName": [" Draft Mail "] if selection else [],
        "gatewayId": [],
        "gatewayName": [],
    }
    assert refused.closed and refused.reads == 0


@pytest.mark.parametrize(
    "status", [301, 302, 303, 307, 308, 400, 401, 403, 404, 429, 500, 503]
)
def test_other_get_statuses_never_switch_methods_and_close_error_response(
    monkeypatch, status
):
    calls = []
    refused = FakeResponse(b"echoed-secret")

    def request(req, timeout):
        calls.append(req)
        raise http_error(status, refused)

    monkeypatch.setattr(module, "urlopen", request)
    with pytest.raises(AgentError, match=str(status)) as error:
        ServerConfig.fetch("secret")
    assert [req.method for req in calls] == ["GET"]
    assert refused.closed and refused.reads == 0
    assert "secret" not in str(error.value)
    assert "untrusted" not in str(error.value)


@pytest.mark.parametrize("status", [405, 401, 500])
def test_second_request_failure_does_not_start_another_retry(monkeypatch, status):
    calls = []

    def request(req, timeout):
        calls.append(req)
        raise http_error(405 if len(calls) == 1 else status)

    monkeypatch.setattr(module, "urlopen", request)
    with pytest.raises(AgentError, match=str(status)):
        ServerConfig.fetch("secret")
    assert [req.method for req in calls] == ["GET", "POST"]


@pytest.mark.parametrize(
    "selection",
    [{"serverId": ["one", "two"]}, {"serverId": ["same"], "gatewayId": ["same"]}],
)
def test_multi_selector_405_fails_clearly_without_get_or_fanout(monkeypatch, selection):
    calls = []

    def request(req, timeout):
        calls.append(req)
        raise http_error(405)

    monkeypatch.setattr(module, "urlopen", request)
    with pytest.raises(
        AgentError, match="multiple selectors require backend POST"
    ) as error:
        ServerConfig.fetch("secret", selection=selection)
    assert [req.method for req in calls] == ["POST"]
    assert "secret" not in str(error.value)


def test_retry_uses_remaining_budget_instead_of_resetting_timeout(monkeypatch):
    clock = [100.0]
    timeouts = []
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def request(req, timeout):
        timeouts.append(timeout)
        if len(timeouts) == 1:
            clock[0] += 7
            raise http_error(405)
        return FakeResponse()

    monkeypatch.setattr(module, "urlopen", request)
    ServerConfig.fetch("key")
    assert timeouts == [30.0, 23.0]


def test_exhausted_budget_prevents_retry(monkeypatch):
    clock = [100.0]
    calls = []
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def request(req, timeout):
        calls.append(req)
        clock[0] += 31
        raise http_error(405)

    monkeypatch.setattr(module, "urlopen", request)
    with pytest.raises(AgentError, match="timed out"):
        ServerConfig.fetch("key")
    assert len(calls) == 1


def test_streamed_body_cannot_extend_overall_deadline(monkeypatch):
    clock = [100.0]
    calls = []

    class StreamResponse(FakeResponse):
        def read1(self, count):
            self.reads += 1
            clock[0] += 16
            return b"partial-body"

    response = StreamResponse()
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def request(req, timeout):
        calls.append(req)
        return response

    monkeypatch.setattr(module, "urlopen", request)
    with pytest.raises(AgentError, match="timed out"):
        ServerConfig.fetch("key")
    assert response.closed
    assert response.reads == 2
    assert len(calls) == 1


@pytest.mark.parametrize("key", [None, "", "  "])
def test_missing_key(key):
    with pytest.raises(ApiKeyError):
        ServerConfig.fetch(key)


@pytest.mark.parametrize(
    "error", [URLError("secret-body"), TimeoutError("secret-body")]
)
def test_transport_errors_do_not_echo_credentials_or_retry(monkeypatch, error):
    calls = []

    def fail(req, **kwargs):
        calls.append(req)
        raise error

    monkeypatch.setattr(module, "urlopen", fail)
    with pytest.raises(AgentError) as caught:
        ServerConfig.fetch("secret")
    assert "secret" not in str(caught.value)
    assert len(calls) == 1


def test_unknown_selector_rejected_before_request(monkeypatch):
    monkeypatch.setattr(module, "urlopen", lambda *a, **k: pytest.fail("request sent"))
    with pytest.raises(AgentError):
        ServerConfig.fetch("key", ServerConfigRoute("bad", "s"))


@pytest.fixture
def inventory_http(monkeypatch):
    """Exercise urllib status handling and redirect rejection over real HTTP."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    state = {"mode": "get-only", "calls": [], "servers": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_inventory(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            state["calls"].append((self.command, self.path, dict(self.headers), raw))
            if state["mode"] == "redirect":
                status, body = 307, b"private redirect body"
            elif state["mode"] == "post-only" and self.command == "GET":
                status, body = 405, b"private refused-method body"
            else:
                status, body = (
                    200,
                    json.dumps(
                        {"succeeded": True, "data": {"servers": state["servers"]}}
                    ).encode(),
                )
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if status == 307:
                self.send_header("Location", "/redirect-target")
            self.end_headers()
            self.wfile.write(body)

        do_GET = handle_inventory
        do_POST = handle_inventory

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        module, "_gopher_api_root", lambda: f"http://127.0.0.1:{server.server_port}"
    )
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize(
    "mode, expected", [("get-only", ["GET"]), ("post-only", ["GET", "POST"])]
)
def test_real_http_supports_legacy_and_post_only_deployments(
    inventory_http, mode, expected
):
    inventory_http["mode"] = mode
    value = " Team & Ops/+?#=%ü "
    result = ServerConfig.fetch("fixture-key", ServerConfigRoute("serverName", value))
    assert json.loads(result)["data"]["servers"] == []
    calls = inventory_http["calls"]
    assert [call[0] for call in calls] == expected
    assert parse_qs(urlsplit(calls[0][1]).query) == {"serverName": [value]}
    assert calls[0][3] == b""
    assert all(call[2]["Authorization"] == "Bearer fixture-key" for call in calls)
    if mode == "post-only":
        assert calls[1][1] == "/v1/mcp-servers"
        assert json.loads(calls[1][3]) == {
            "serverId": [],
            "serverName": [value],
            "gatewayId": [],
            "gatewayName": [],
        }


@pytest.mark.parametrize("selection", [{}, {"serverId": ["one", "two"]}])
def test_real_http_redirect_is_not_followed_or_retried(inventory_http, selection):
    inventory_http["mode"] = "redirect"
    with pytest.raises(AgentError, match="307"):
        ServerConfig.fetch("fixture-key", selection=selection)
    assert len(inventory_http["calls"]) == 1
    assert "/redirect-target" not in inventory_http["calls"][0][1]


def test_get_405_retry_keeps_gateway_route_validation(inventory_http):
    inventory_http["mode"] = "post-only"
    inventory_http["servers"] = [
        {
            "id": "g1",
            "name": "Production",
            "transport": "http",
            "config": {"url": "https://mcp.example/v1/mcp/servers/g1/mcp"},
        }
    ]
    with pytest.raises(AgentError, match="gateway"):
        ServerConfig.fetch("fixture-key", ServerConfigRoute("gatewayId", "g1"))
    assert [call[0] for call in inventory_http["calls"]] == ["GET", "POST"]
