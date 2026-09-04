"""MCP server-to-client elicitation support."""

from typing import Any, Callable, Mapping, Optional, Union


GopherAgentElicitationAction = str


class GopherAgentElicitationRequest:
    """Server-provided MCP elicitation/create request."""

    def __init__(
        self,
        mode: str,
        elicitation_id: Optional[str] = None,
        message: Optional[str] = None,
        url: Optional[str] = None,
        request_id_json: Optional[str] = None,
        raw_json: Optional[str] = None,
        raw_params_json: Optional[str] = None,
    ) -> None:
        if not isinstance(mode, str):
            raise ValueError("elicitation mode must be a string")
        self.mode = mode
        self.elicitation_id = _optional_string(elicitation_id, "elicitation_id")
        self.message = _optional_string(message, "message")
        self.url = _optional_string(url, "url")
        self.request_id_json = _optional_string(request_id_json, "request_id_json")
        self.raw_json = _optional_string(raw_json, "raw_json")
        self.raw_params_json = _optional_string(raw_params_json, "raw_params_json")


class GopherAgentElicitationResponse:
    """Application response to an MCP elicitation request."""

    def __init__(self, action: GopherAgentElicitationAction) -> None:
        self.action = normalize_elicitation_action(action)


GopherAgentElicitationHandler = Callable[
    [GopherAgentElicitationRequest],
    Union[GopherAgentElicitationResponse, GopherAgentElicitationAction],
]


class GopherAgentElicitationOptions:
    """Options for MCP server-to-client elicitation handling."""

    def __init__(
        self,
        handler: Optional[GopherAgentElicitationHandler] = None,
        timeout_ms: Optional[int] = None,
        open_browser: Optional[bool] = None,
    ) -> None:
        if handler is not None and not callable(handler):
            raise ValueError("elicitation handler must be callable")
        if timeout_ms is not None:
            if not isinstance(timeout_ms, (int, float)) or not _is_finite(timeout_ms):
                raise ValueError("elicitation timeout_ms must be a finite number")
            timeout_ms = max(0, int(timeout_ms))
        if open_browser is not None and not isinstance(open_browser, bool):
            raise ValueError("elicitation open_browser must be a boolean")
        self.handler = handler
        self.timeout_ms = timeout_ms
        self.open_browser = open_browser


def normalize_elicitation_options(
    options: Optional[
        Union[GopherAgentElicitationOptions, Mapping[str, Any]]
    ] = None,
) -> GopherAgentElicitationOptions:
    """Normalize elicitation options, defaulting omitted options to enabled."""
    if options is None:
        return GopherAgentElicitationOptions()

    if isinstance(options, GopherAgentElicitationOptions):
        return options

    if isinstance(options, Mapping):
        timeout_ms = (
            options.get("timeout_ms")
            if "timeout_ms" in options
            else options.get("timeoutMs")
        )
        open_browser = (
            options.get("open_browser")
            if "open_browser" in options
            else options.get("openBrowser")
        )
        return GopherAgentElicitationOptions(
            handler=options.get("handler"),
            timeout_ms=timeout_ms,
            open_browser=open_browser,
        )

    raise ValueError(
        "elicitation options must be a GopherAgentElicitationOptions instance "
        "or mapping"
    )


def normalize_elicitation_action(
    response: Union[GopherAgentElicitationResponse, GopherAgentElicitationAction]
) -> GopherAgentElicitationAction:
    """Normalize and validate an MCP elicitation action."""
    action = response.action if isinstance(response, GopherAgentElicitationResponse) else response
    if action in ("accept", "decline", "cancel"):
        return action
    raise ValueError(f"unsupported MCP elicitation action: {action}")


def _optional_string(value: Optional[str], name: str) -> Optional[str]:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"elicitation {name} must be a string")
    return value


def _is_finite(value: Union[int, float]) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))
