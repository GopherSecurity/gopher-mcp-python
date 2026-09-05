"""Tests for gateway URL elicitation preflight."""

import json

from gopher_mcp_python import elicitation_runtime
from gopher_mcp_python.gateway_elicitation_preflight import (
    preflight_gateway_elicitation,
)
from gopher_mcp_python.runtime_options import (
    GopherAgentCreateOptions,
    GopherAgentRuntimeOptions,
)

GATEWAY_URL = "https://mcp-test.gopher.security/v1/mcp/gateways/gw-1/mcp"


def teardown_function():
    elicitation_runtime.set_elicitation_input_for_test(None)


def test_answers_gateway_url_elicitation_before_native_tool_calls() -> None:
    elicitation_runtime.set_elicitation_input_for_test(lambda timeout_ms: "\n")
    opener = FakeOpener(
        [
            FakeResponse(headers={"mcp-session-id": "session-1"}),
            FakeResponse(),
            FakeResponse(body=b'{"tools":[]}'),
            FakeResponse(
                lines=[
                    b"event: message\n",
                    (
                        b'data: {"jsonrpc":"2.0","id":"gw_elicitation_1",'
                        b'"method":"elicitation/create","params":'
                        b'{"elicitationId":"provider-auth","message":"Connect",'
                        b'"mode":"url","url":"https://accounts.google.com/o/oauth2'
                        b'/v2/auth?state=s"}}\n'
                    ),
                    b"\n",
                ]
            ),
            FakeResponse(),
        ]
    )

    result = preflight_gateway_elicitation(
        GATEWAY_URL,
        GopherAgentRuntimeOptions(access_token="gateway-token"),
        GopherAgentCreateOptions(elicitation={"open_browser": False}),
        opener=opener,
    )

    assert result is not None
    assert result.access_token == "gateway-token"
    assert result.headers["Authorization"] == "Bearer gateway-token"
    assert result.headers["Mcp-Session-Id"] == "session-1"
    assert len(opener.requests) == 5
    assert json.loads(opener.requests[0].data.decode("utf-8"))["method"] == (
        "initialize"
    )
    assert json.loads(opener.requests[1].data.decode("utf-8"))["method"] == (
        "notifications/initialized"
    )
    assert json.loads(opener.requests[2].data.decode("utf-8"))["method"] == (
        "tools/list"
    )
    assert opener.requests[3].get_method() == "GET"
    assert opener.requests[3].headers["Mcp-session-id"] == "session-1"
    assert json.loads(opener.requests[4].data.decode("utf-8")) == {
        "jsonrpc": "2.0",
        "id": "gw_elicitation_1",
        "result": {"action": "accept"},
    }


def test_does_nothing_for_non_gateway_urls() -> None:
    opener = FakeOpener([])
    runtime_options = GopherAgentRuntimeOptions(access_token="token")

    result = preflight_gateway_elicitation(
        "https://mcp.example.com/mcp",
        runtime_options,
        GopherAgentCreateOptions(),
        opener=opener,
    )

    assert result is runtime_options
    assert opener.requests == []


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected request")
        return self.responses.pop(0)


class FakeResponse:
    def __init__(self, body=b"", headers=None, lines=None):
        self.body = body
        self.headers = headers or {}
        self.lines = list(lines or [])

    def getheader(self, name):
        return self.headers.get(name.lower())

    def read(self):
        return self.body

    def readline(self):
        if self.lines:
            return self.lines.pop(0)
        return b""
