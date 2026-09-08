"""MCP URL elicitation preflight for direct create_with_url flows."""

from dataclasses import dataclass
import json
import os
import socket
import time
from typing import Callable, Dict, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from gopher_mcp_python.elicitation_runtime import (
    resolve_elicitation_action_sync,
    to_elicitation_request,
)
from gopher_mcp_python.runtime_options import (
    GopherAgentCreateOptions,
    GopherAgentRuntimeOptions,
)

MCP_PROTOCOL_VERSION = "2025-11-25"
DEFAULT_PREFLIGHT_TIMEOUT_MS = 5000

UrlOpen = Callable[..., object]


@dataclass(frozen=True)
class GatewayElicitationPreflightResult:
    runtime_options: Optional[GopherAgentRuntimeOptions]
    handled: bool
    session: Optional[str] = None


def preflight_gateway_elicitation(
    url: str,
    runtime_options: Optional[GopherAgentRuntimeOptions],
    create_options: Optional[GopherAgentCreateOptions],
    opener: UrlOpen = urlopen,
) -> Optional[GopherAgentRuntimeOptions]:
    """Handle URL elicitation before native tool calls."""
    return preflight_gateway_elicitation_with_status(
        url, runtime_options, create_options, opener
    ).runtime_options


def preflight_gateway_elicitation_with_status(
    url: str,
    runtime_options: Optional[GopherAgentRuntimeOptions],
    create_options: Optional[GopherAgentCreateOptions],
    opener: UrlOpen = urlopen,
) -> GatewayElicitationPreflightResult:
    """Handle URL elicitation and report whether preflight accepted it."""
    if not _is_http_mcp_url(url):
        return GatewayElicitationPreflightResult(runtime_options, False)
    if create_options is None or create_options.elicitation is None:
        return GatewayElicitationPreflightResult(runtime_options, False)

    authorization = _authorization_header_value(runtime_options)
    if authorization is None:
        return GatewayElicitationPreflightResult(runtime_options, False)

    timeout_ms = (
        create_options.elicitation.timeout_ms
        if create_options.elicitation.timeout_ms is not None
        else DEFAULT_PREFLIGHT_TIMEOUT_MS
    )
    timeout_ms = max(0, int(timeout_ms))
    if timeout_ms == 0:
        return GatewayElicitationPreflightResult(runtime_options, False)

    try:
        session = _initialize_gateway_session(url, authorization, opener)
        if session is None:
            return GatewayElicitationPreflightResult(runtime_options, False)

        _notify_initialized(url, authorization, session, opener)
        _list_tools(url, authorization, session, opener)
        handled = _handle_gateway_event_stream(
            url, authorization, session, create_options, timeout_ms, opener
        )
        return GatewayElicitationPreflightResult(
            runtime_options,
            handled,
            session if handled else None,
        )
    except Exception as exc:
        _log_debug("elicitation preflight skipped", {"error": str(exc)})
        return GatewayElicitationPreflightResult(runtime_options, False)


def _is_http_mcp_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and parsed.netloc != ""


def _authorization_header_value(
    options: Optional[GopherAgentRuntimeOptions],
) -> Optional[str]:
    if options is None:
        return None
    for name, value in options.headers.items():
        if name.lower() == "authorization":
            return value
    if options.access_token:
        return f"Bearer {options.access_token}"
    return None


def _initialize_gateway_session(
    url: str,
    authorization: str,
    opener: UrlOpen,
) -> Optional[str]:
    response = _post_json(
        url,
        authorization,
        None,
        {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "elicitation": {"form": {}, "url": {}},
                    "sampling": {},
                },
                "clientInfo": {
                    "name": "gopher-mcp-python",
                    "version": "0.1.34",
                },
            },
        },
        opener,
    )
    session = _response_header(response, "mcp-session-id")
    _log_debug(
        "elicitation preflight initialized",
        {"session_present": session is not None},
    )
    return session


def _notify_initialized(
    url: str,
    authorization: str,
    session: str,
    opener: UrlOpen,
) -> None:
    _post_json(
        url,
        authorization,
        session,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        opener,
    )


def _list_tools(
    url: str,
    authorization: str,
    session: str,
    opener: UrlOpen,
) -> None:
    _post_json(
        url,
        authorization,
        session,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        opener,
    )


def _handle_gateway_event_stream(
    url: str,
    authorization: str,
    session: str,
    create_options: GopherAgentCreateOptions,
    timeout_ms: int,
    opener: UrlOpen,
) -> bool:
    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "text/event-stream",
            "Authorization": authorization,
            "Mcp-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Mcp-Session-Id": session,
        },
    )
    try:
        response = opener(request, timeout=timeout_ms / 1000.0)
        event = _read_first_sse_event(response, timeout_ms)
    except (OSError, TimeoutError, socket.timeout) as exc:
        _log_debug("elicitation preflight skipped", {"error": str(exc)})
        return False

    parsed = _parse_elicitation_event(event)
    if parsed is None:
        return False

    action = resolve_elicitation_action_sync(
        create_options.elicitation,
        to_elicitation_request(parsed["request"]),
    )
    _post_json(
        url,
        authorization,
        session,
        {
            "jsonrpc": "2.0",
            "id": parsed["id"],
            "result": {"action": action},
        },
        opener,
    )
    _log_debug(
        "elicitation preflight answered",
        {"action": action, "session": session},
    )
    return action == "accept"


def _post_json(
    url: str,
    authorization: str,
    session: Optional[str],
    body: Dict[str, object],
    opener: UrlOpen,
) -> object:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Authorization": authorization,
        "Content-Type": "application/json",
    }
    if session is not None:
        headers["Mcp-Protocol-Version"] = MCP_PROTOCOL_VERSION
        headers["Mcp-Session-Id"] = session
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    response = opener(request, timeout=30)
    try:
        response.read()
    except Exception:
        pass
    return response


def _read_first_sse_event(response: object, timeout_ms: int) -> str:
    deadline = time.monotonic() + timeout_ms / 1000.0
    lines = []
    while time.monotonic() < deadline:
        line = response.readline()
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        if line == "":
            break
        stripped = line.rstrip("\r\n")
        if stripped == "":
            break
        lines.append(stripped)
    return "\n".join(lines)


def _parse_elicitation_event(event: str) -> Optional[Dict[str, object]]:
    data = None
    for line in event.splitlines():
        if line.startswith("data:"):
            data = line[len("data:") :].strip()
            break
    if not data:
        return None
    try:
        payload = json.loads(data)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("method") != "elicitation/create":
        return None
    params = payload.get("params")
    if not isinstance(params, dict):
        return None
    request = {
        "request_id_json": json.dumps(payload.get("id")),
        "elicitation_id": _string_field(params, "elicitationId"),
        "mode": _string_field(params, "mode"),
        "message": _string_field(params, "message"),
        "url": _string_field(params, "url"),
        "raw_json": json.dumps(payload),
        "raw_params_json": json.dumps(params),
    }
    return {"id": payload.get("id"), "request": request}


def _response_header(response: object, name: str) -> Optional[str]:
    if hasattr(response, "getheader"):
        value = response.getheader(name)
        return value if isinstance(value, str) and value else None
    headers = getattr(response, "headers", None)
    if headers is not None:
        value = headers.get(name)
        return value if isinstance(value, str) and value else None
    return None


def _string_field(value: Dict[str, object], field: str) -> Optional[str]:
    field_value = value.get(field)
    return field_value if isinstance(field_value, str) else None


def _log_debug(label: str, values: Dict[str, object]) -> None:
    if (
        os.environ.get("GOPHER_MCP_OAUTH_DEBUG") != "1"
        and os.environ.get("DEBUG") != "1"
    ):
        return
    print(f"[gopher-mcp-python oauth] {label}: {values}")
