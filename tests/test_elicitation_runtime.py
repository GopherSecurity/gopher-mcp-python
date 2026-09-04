"""Tests for MCP elicitation runtime helpers."""

import pytest

import gopher_mcp_python.elicitation_runtime as runtime
from gopher_mcp_python.elicitation import (
    GopherAgentElicitationOptions,
    GopherAgentElicitationRequest,
    GopherAgentElicitationResponse,
    normalize_elicitation_options,
)


def teardown_function() -> None:
    runtime.set_elicitation_input_for_test(None)


def test_normalize_elicitation_options_defaults_to_enabled() -> None:
    options = normalize_elicitation_options()

    assert options.handler is None
    assert options.timeout_ms is None
    assert options.open_browser is None


def test_normalize_elicitation_options_accepts_camel_case() -> None:
    def handler(request):
        return "accept"

    options = normalize_elicitation_options(
        {"handler": handler, "timeoutMs": 10.8, "openBrowser": False}
    )

    assert options.handler is handler
    assert options.timeout_ms == 10
    assert options.open_browser is False


@pytest.mark.parametrize(
    "options, match",
    [
        ({"handler": object()}, "handler must be callable"),
        ({"timeout_ms": "soon"}, "timeout_ms must be a finite number"),
        ({"open_browser": "yes"}, "open_browser must be a boolean"),
    ],
)
def test_normalize_elicitation_options_rejects_invalid_input(options, match) -> None:
    with pytest.raises(ValueError, match=match):
        normalize_elicitation_options(options)


def test_to_elicitation_request_maps_native_names() -> None:
    request = runtime.to_elicitation_request(
        {
            "mode": "url",
            "elicitation_id": "elicit-1",
            "message": "Connect",
            "url": "https://auth.example.com",
            "request_id_json": '"1"',
            "raw_json": '{"jsonrpc":"2.0"}',
            "raw_params_json": '{"url":"https://auth.example.com"}',
        }
    )

    assert request.mode == "url"
    assert request.elicitation_id == "elicit-1"
    assert request.message == "Connect"
    assert request.url == "https://auth.example.com"
    assert request.request_id_json == '"1"'
    assert request.raw_json == '{"jsonrpc":"2.0"}'
    assert request.raw_params_json == '{"url":"https://auth.example.com"}'


def test_default_url_handler_opens_browser_and_accepts(monkeypatch) -> None:
    opened = []

    def open_url(url, open_browser=None):
        opened.append((url, open_browser))
        return {"opened": True, "url": url}

    monkeypatch.setattr(runtime, "open_authorization_url", open_url)
    runtime.set_elicitation_input_for_test(lambda timeout_ms: "\n")

    response = runtime.default_url_elicitation_handler(
        GopherAgentElicitationOptions(open_browser=True)
    )(GopherAgentElicitationRequest(mode="url", url="https://auth.example.com"))

    assert response.action == "accept"
    assert opened == [("https://auth.example.com", True)]


def test_default_url_handler_manual_fallback_prints_url(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        runtime,
        "open_authorization_url",
        lambda url, open_browser=None: {"opened": False, "url": url},
    )
    runtime.set_elicitation_input_for_test(lambda timeout_ms: "cancel\n")

    response = runtime.default_url_elicitation_handler()(
        GopherAgentElicitationRequest(mode="url", url="https://auth.example.com")
    )

    assert response.action == "cancel"
    assert "Open this OAuth authorization URL to continue" in capsys.readouterr().err


def test_default_url_handler_declines_unsupported_mode() -> None:
    response = runtime.default_url_elicitation_handler()(
        GopherAgentElicitationRequest(mode="form")
    )

    assert response.action == "decline"


def test_resolve_elicitation_action_rejects_async_handler() -> None:
    async def handler(request):
        return "accept"

    with pytest.raises(RuntimeError, match="Async MCP elicitation handlers"):
        runtime.resolve_elicitation_action_sync(
            GopherAgentElicitationOptions(handler=handler),
            GopherAgentElicitationRequest(mode="url"),
        )


@pytest.mark.parametrize(
    "response",
    ["accept", GopherAgentElicitationResponse("accept")],
)
def test_resolve_elicitation_action_normalizes_response(response) -> None:
    action = runtime.resolve_elicitation_action_sync(
        GopherAgentElicitationOptions(handler=lambda request: response),
        GopherAgentElicitationRequest(mode="url"),
    )

    assert action == "accept"


def test_native_action_mapping() -> None:
    assert runtime.native_action_from_elicitation_action("accept") == 1
    assert runtime.native_action_from_elicitation_action("decline") == 2
    assert runtime.native_action_from_elicitation_action("cancel") == 3


def test_redact_elicitation_url_hides_sensitive_fields() -> None:
    redacted = runtime.redact_elicitation_url(
        "https://auth.example.com/oauth?"
        "code=abc&state=xyz&access_token=secret&scope=mail#frag"
    )

    assert "abc" not in redacted
    assert "xyz" not in redacted
    assert "secret" not in redacted
    assert "frag" not in redacted
    assert "scope=%3Cpresent%3E" in redacted
    assert "code=%3Credacted%3E" in redacted
