"""Runtime helpers for MCP elicitation callbacks."""

import inspect
import os
import selectors
import sys
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from gopher_mcp_python.elicitation import (
    GopherAgentElicitationAction,
    GopherAgentElicitationHandler,
    GopherAgentElicitationOptions,
    GopherAgentElicitationRequest,
    GopherAgentElicitationResponse,
    normalize_elicitation_action,
)
from gopher_mcp_python.oauth_browser import open_authorization_url

ELICITATION_ACTION_ACCEPT = 1
ELICITATION_ACTION_DECLINE = 2
ELICITATION_ACTION_CANCEL = 3

_read_input: Callable[[Optional[int]], Optional[str]]


def to_elicitation_request(
    request: Mapping[str, Optional[str]]
) -> GopherAgentElicitationRequest:
    """Convert native request fields into the public Python request object."""
    return GopherAgentElicitationRequest(
        mode=request.get("mode") or "",
        elicitation_id=request.get("elicitation_id"),
        message=request.get("message"),
        url=request.get("url"),
        request_id_json=request.get("request_id_json"),
        raw_json=request.get("raw_json"),
        raw_params_json=request.get("raw_params_json"),
    )


def resolve_elicitation_action_sync(
    options: GopherAgentElicitationOptions,
    request: GopherAgentElicitationRequest,
) -> GopherAgentElicitationAction:
    """Resolve an elicitation request using a synchronous handler."""
    handler = options.handler or default_url_elicitation_handler(options)
    _log_elicitation_debug("request", _summarize_elicitation_request(request))
    response = handler(request)
    if inspect.isawaitable(response):
        if inspect.iscoroutine(response):
            response.close()
        raise RuntimeError(
            "Async MCP elicitation handlers are not supported by the native "
            "FFI bridge yet"
        )
    action = normalize_elicitation_action(response)
    _log_elicitation_debug(
        "response",
        {
            "elicitation_id": request.elicitation_id,
            "mode": request.mode,
            "action": action,
        },
    )
    return action


def default_url_elicitation_handler(
    options: Optional[GopherAgentElicitationOptions] = None,
) -> GopherAgentElicitationHandler:
    """Return the SDK's default URL-mode provider OAuth handler."""
    resolved_options = options or GopherAgentElicitationOptions()

    def handle(
        request: GopherAgentElicitationRequest,
    ) -> GopherAgentElicitationResponse:
        if request.mode != "url" or not request.url:
            return GopherAgentElicitationResponse("decline")
        result = open_authorization_url(
            request.url,
            open_browser=resolved_options.open_browser,
        )
        if not result.get("opened"):
            print(
                "Open this OAuth authorization URL to continue:\n"
                f"{request.url}",
                file=sys.stderr,
            )
        return GopherAgentElicitationResponse(
            wait_for_oauth_completion_sync(resolved_options.timeout_ms)
        )

    return handle


def wait_for_oauth_completion_sync(
    timeout_ms: Optional[int] = None,
) -> GopherAgentElicitationAction:
    """Wait synchronously for the user to finish browser OAuth."""
    print(
        'Complete the OAuth flow in the browser, then press Enter to continue. '
        'Type "cancel" and press Enter to cancel.',
        file=sys.stderr,
    )
    value = _read_input(timeout_ms)
    if value is None:
        print(
            "Cannot access an interactive terminal; canceling provider "
            "authorization.",
            file=sys.stderr,
        )
        return "cancel"
    return "cancel" if value.strip().lower() == "cancel" else "accept"


def native_action_from_elicitation_action(
    action: GopherAgentElicitationAction,
) -> int:
    """Map public action strings to native integer constants."""
    if action == "accept":
        return ELICITATION_ACTION_ACCEPT
    if action == "decline":
        return ELICITATION_ACTION_DECLINE
    if action == "cancel":
        return ELICITATION_ACTION_CANCEL
    raise ValueError(f"unsupported MCP elicitation action: {action}")


def set_elicitation_input_for_test(
    read_input: Optional[Callable[[Optional[int]], Optional[str]]],
) -> None:
    """Override terminal input for tests."""
    global _read_input
    _read_input = read_input or _read_terminal_input


def redact_elicitation_url(url: str) -> str:
    """Redact sensitive OAuth query fields for diagnostic logging."""
    try:
        parsed = urlsplit(url)
        query = urlencode(
            [
                (
                    name,
                    "<redacted>" if _is_sensitive_query_name(name) else "<present>",
                )
                for name, _value in parse_qsl(parsed.query, keep_blank_values=True)
            ]
        )
        fragment = "<redacted>" if parsed.fragment else ""
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, query, fragment)
        )
    except Exception:
        return "<invalid-url>"


def _read_terminal_input(timeout_ms: Optional[int]) -> Optional[str]:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    if timeout_ms is not None and timeout_ms > 0:
        return _read_terminal_input_with_timeout(timeout_ms)
    if not sys.stdin or not sys.stdin.isatty():
        return None
    return sys.stdin.readline()


def _read_terminal_input_with_timeout(timeout_ms: int) -> Optional[str]:
    if not sys.stdin or not sys.stdin.isatty():
        return None
    selector = None
    try:
        selector = selectors.DefaultSelector()
        selector.register(sys.stdin, selectors.EVENT_READ)
        events = selector.select(timeout_ms / 1000.0)
    except Exception:
        return None
    finally:
        if selector is not None:
            try:
                selector.close()
            except Exception:
                pass
    if not events:
        print(
            "Timed out waiting for OAuth completion; canceling provider "
            "authorization.",
            file=sys.stderr,
        )
        return None
    return sys.stdin.readline()


def _summarize_elicitation_request(
    request: GopherAgentElicitationRequest,
) -> Dict[str, Optional[str]]:
    host = None
    if request.url:
        try:
            host = urlsplit(request.url).netloc
        except Exception:
            host = None
    return {
        "elicitation_id": request.elicitation_id,
        "mode": request.mode,
        "host": host,
        "url": redact_elicitation_url(request.url) if request.url else None,
    }


def _log_elicitation_debug(label: str, values: Any) -> None:
    if os.environ.get("GOPHER_MCP_OAUTH_DEBUG") != "1" and os.environ.get("DEBUG") != "1":
        return
    print(f"[gopher-mcp-python elicitation] {label}: {values}", file=sys.stderr)


def _is_sensitive_query_name(name: str) -> bool:
    normalized = name.lower()
    return (
        normalized == "state"
        or normalized == "code"
        or normalized == "client_secret"
        or "token" in normalized
        or "secret" in normalized
    )


_read_input = _read_terminal_input
