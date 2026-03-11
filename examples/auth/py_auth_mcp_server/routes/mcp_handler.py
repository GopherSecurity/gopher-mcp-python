"""MCP Handler - JSON-RPC 2.0 Implementation.

Implements the Model Context Protocol (MCP) JSON-RPC handler
for tool registration and invocation.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict

from flask import Blueprint, Flask, Response, g, jsonify, request


class JsonRpcErrorCode:
    """Standard JSON-RPC error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class JsonRpcError:
    """JSON-RPC 2.0 Error structure."""

    code: int
    message: str
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            result["data"] = self.data
        return result


@dataclass
class JsonRpcRequest:
    """JSON-RPC 2.0 Request structure."""

    jsonrpc: str
    method: str
    id: str | int | None = None
    params: dict[str, Any] | None = None


@dataclass
class JsonRpcResponse:
    """JSON-RPC 2.0 Response structure."""

    jsonrpc: str
    id: str | int | None
    result: Any = None
    error: JsonRpcError | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        response: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            response["error"] = self.error.to_dict()
        else:
            response["result"] = self.result
        return response


class ToolInputProperty(TypedDict, total=False):
    """Tool input property schema."""

    type: str
    description: str
    enum: list[str]


class ToolInputSchema(TypedDict, total=False):
    """Tool input schema."""

    type: str
    properties: dict[str, ToolInputProperty]
    required: list[str]


@dataclass
class ToolSpec:
    """Tool specification for MCP."""

    name: str
    description: str
    input_schema: ToolInputSchema

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class ToolContentItem:
    """Tool result content item."""

    type: str  # 'text', 'image', or 'resource'
    text: str | None = None
    data: str | None = None
    mime_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"type": self.type}
        if self.text is not None:
            result["text"] = self.text
        if self.data is not None:
            result["data"] = self.data
        if self.mime_type is not None:
            result["mimeType"] = self.mime_type
        return result


@dataclass
class ToolResult:
    """Tool execution result."""

    content: list[ToolContentItem] = field(default_factory=list)
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"content": [c.to_dict() for c in self.content]}
        if self.is_error:
            result["isError"] = self.is_error
        return result


# Type alias for tool handler function
ToolHandler = Callable[[dict[str, Any]], ToolResult]


@dataclass
class RegisteredTool:
    """Registered tool with spec and handler."""

    spec: ToolSpec
    handler: ToolHandler


def _set_cors_headers(response: Response) -> Response:
    """Set common CORS headers on response."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD"
    )
    response.headers["Access-Control-Allow-Headers"] = (
        "Accept, Accept-Language, Content-Language, Content-Type, Authorization, "
        "X-Requested-With, Origin, Cache-Control, Pragma, Mcp-Session-Id, "
        "Mcp-Protocol-Version"
    )
    response.headers["Access-Control-Expose-Headers"] = (
        "WWW-Authenticate, Content-Length, Content-Type"
    )
    response.headers["Access-Control-Max-Age"] = "86400"
    return response


class McpHandler:
    """MCP Handler class.

    Manages tool registration and JSON-RPC request handling.
    """

    def __init__(self) -> None:
        """Initialize the MCP handler."""
        self._tools: dict[str, RegisteredTool] = {}
        self._server_info = {
            "name": "py-auth-mcp-server",
            "version": "1.0.0",
        }

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: ToolInputSchema,
        handler: ToolHandler,
    ) -> None:
        """Register a tool with the handler.

        Args:
            name: Unique tool name.
            description: Tool description.
            input_schema: JSON schema for tool input.
            handler: Function to execute when tool is called.
        """
        spec = ToolSpec(name=name, description=description, input_schema=input_schema)
        self._tools[name] = RegisteredTool(spec=spec, handler=handler)

    def tool(
        self, name: str, description: str, input_schema: ToolInputSchema
    ) -> Callable[[ToolHandler], ToolHandler]:
        """Decorator to register a tool.

        Args:
            name: Unique tool name.
            description: Tool description.
            input_schema: JSON schema for tool input.

        Returns:
            Decorator function.
        """

        def decorator(handler: ToolHandler) -> ToolHandler:
            self.register_tool(name, description, input_schema, handler)
            return handler

        return decorator

    def get_tools(self) -> list[ToolSpec]:
        """Get list of registered tools."""
        return [t.spec for t in self._tools.values()]

    def handle_request(self, body: Any) -> JsonRpcResponse:
        """Handle a JSON-RPC request.

        Args:
            body: Request body.

        Returns:
            JSON-RPC response.
        """
        # Parse and validate request
        parse_result = self._parse_request(body)
        if isinstance(parse_result, JsonRpcError):
            return JsonRpcResponse(jsonrpc="2.0", id=None, error=parse_result)

        rpc_request = parse_result
        request_id = rpc_request.id

        try:
            result = self._dispatch_method(
                rpc_request.method, rpc_request.params or {}
            )
            return JsonRpcResponse(jsonrpc="2.0", id=request_id, result=result)
        except JsonRpcError as e:
            return JsonRpcResponse(jsonrpc="2.0", id=request_id, error=e)
        except Exception as e:
            error = JsonRpcError(
                code=JsonRpcErrorCode.INTERNAL_ERROR, message=str(e)
            )
            return JsonRpcResponse(jsonrpc="2.0", id=request_id, error=error)

    def _parse_request(self, body: Any) -> JsonRpcRequest | JsonRpcError:
        """Parse and validate a JSON-RPC request."""
        if not body or not isinstance(body, dict):
            return JsonRpcError(
                code=JsonRpcErrorCode.INVALID_REQUEST,
                message="Invalid request: expected object",
            )

        if body.get("jsonrpc") != "2.0":
            return JsonRpcError(
                code=JsonRpcErrorCode.INVALID_REQUEST,
                message='Invalid request: jsonrpc must be "2.0"',
            )

        method = body.get("method")
        if not isinstance(method, str):
            return JsonRpcError(
                code=JsonRpcErrorCode.INVALID_REQUEST,
                message="Invalid request: method must be a string",
            )

        params = body.get("params")
        if params is not None and not isinstance(params, dict):
            return JsonRpcError(
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: must be an object",
            )

        return JsonRpcRequest(
            jsonrpc="2.0",
            id=body.get("id"),
            method=method,
            params=params,
        )

    def _dispatch_method(
        self, method: str, params: dict[str, Any]
    ) -> Any:
        """Dispatch a method call to the appropriate handler."""
        if method == "initialize":
            return self._handle_initialize(params)
        elif method == "tools/list":
            return self._handle_tools_list()
        elif method == "tools/call":
            return self._handle_tools_call(params)
        elif method == "ping":
            return {}
        else:
            raise JsonRpcError(
                code=JsonRpcErrorCode.METHOD_NOT_FOUND,
                message=f"Method not found: {method}",
            )

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize method."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": self._server_info,
        }

    def _handle_tools_list(self) -> dict[str, Any]:
        """Handle tools/list method."""
        return {"tools": [t.to_dict() for t in self.get_tools()]}

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call method."""
        name = params.get("name")
        args = params.get("arguments", {})

        if not isinstance(name, str):
            raise JsonRpcError(
                code=JsonRpcErrorCode.INVALID_PARAMS,
                message="Invalid params: name must be a string",
            )

        tool = self._tools.get(name)
        if not tool:
            raise JsonRpcError(
                code=JsonRpcErrorCode.METHOD_NOT_FOUND,
                message=f"Tool not found: {name}",
            )

        result = tool.handler(args)
        return result.to_dict()


def create_mcp_blueprint(handler: McpHandler) -> Blueprint:
    """Create MCP handler blueprint.

    Args:
        handler: McpHandler instance.

    Returns:
        Flask Blueprint with MCP endpoints.
    """
    bp = Blueprint("mcp", __name__)

    @bp.route("/mcp", methods=["OPTIONS"])
    def cors_mcp() -> Response:
        response = Response("", status=204)
        response.headers["Content-Length"] = "0"
        return _set_cors_headers(response)

    @bp.route("/rpc", methods=["OPTIONS"])
    def cors_rpc() -> Response:
        response = Response("", status=204)
        response.headers["Content-Length"] = "0"
        return _set_cors_headers(response)

    @bp.route("/mcp", methods=["POST"])
    def handle_mcp() -> tuple[Response, int]:
        body = request.get_json(silent=True)
        if body is None:
            response = JsonRpcResponse(
                jsonrpc="2.0",
                id=None,
                error=JsonRpcError(
                    code=JsonRpcErrorCode.PARSE_ERROR,
                    message="Parse error: invalid JSON",
                ),
            )
        else:
            response = handler.handle_request(body)
        json_response = jsonify(response.to_dict())
        return _set_cors_headers(json_response), 200

    @bp.route("/rpc", methods=["POST"])
    def handle_rpc() -> tuple[Response, int]:
        body = request.get_json(silent=True)
        if body is None:
            response = JsonRpcResponse(
                jsonrpc="2.0",
                id=None,
                error=JsonRpcError(
                    code=JsonRpcErrorCode.PARSE_ERROR,
                    message="Parse error: invalid JSON",
                ),
            )
        else:
            response = handler.handle_request(body)
        json_response = jsonify(response.to_dict())
        return _set_cors_headers(json_response), 200

    return bp


def register_mcp_routes(app: Flask, handler: McpHandler) -> None:
    """Register MCP handler with Flask app.

    Args:
        app: Flask application.
        handler: McpHandler instance.
    """
    bp = create_mcp_blueprint(handler)
    app.register_blueprint(bp)
