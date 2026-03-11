"""Tests for MCP JSON-RPC handler."""


from py_auth_mcp_server.routes.mcp_handler import (
    JsonRpcError,
    JsonRpcErrorCode,
    JsonRpcResponse,
    ToolContentItem,
    ToolResult,
    ToolSpec,
)


class TestJsonRpcTypes:
    """Tests for JSON-RPC type classes."""

    def test_json_rpc_error_to_dict(self):
        """Test JsonRpcError.to_dict()."""
        error = JsonRpcError(
            code=JsonRpcErrorCode.INVALID_REQUEST,
            message="Invalid request",
            data={"details": "test"},
        )
        result = error.to_dict()
        assert result["code"] == -32600
        assert result["message"] == "Invalid request"
        assert result["data"] == {"details": "test"}

    def test_json_rpc_error_without_data(self):
        """Test JsonRpcError.to_dict() without data."""
        error = JsonRpcError(code=-32600, message="Error")
        result = error.to_dict()
        assert "data" not in result

    def test_json_rpc_response_with_result(self):
        """Test JsonRpcResponse.to_dict() with result."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id=1,
            result={"status": "ok"},
        )
        result = response.to_dict()
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert result["result"] == {"status": "ok"}
        assert "error" not in result

    def test_json_rpc_response_with_error(self):
        """Test JsonRpcResponse.to_dict() with error."""
        response = JsonRpcResponse(
            jsonrpc="2.0",
            id=1,
            error=JsonRpcError(code=-32600, message="Error"),
        )
        result = response.to_dict()
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert result["error"]["code"] == -32600
        assert "result" not in result


class TestToolTypes:
    """Tests for tool type classes."""

    def test_tool_spec_to_dict(self):
        """Test ToolSpec.to_dict()."""
        spec = ToolSpec(
            name="test-tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "param": {"type": "string"},
                },
            },
        )
        result = spec.to_dict()
        assert result["name"] == "test-tool"
        assert result["description"] == "A test tool"
        assert result["inputSchema"]["type"] == "object"

    def test_tool_content_item_to_dict(self):
        """Test ToolContentItem.to_dict()."""
        item = ToolContentItem(
            type="text",
            text="Hello, world!",
        )
        result = item.to_dict()
        assert result["type"] == "text"
        assert result["text"] == "Hello, world!"
        assert "data" not in result
        assert "mimeType" not in result

    def test_tool_result_to_dict(self):
        """Test ToolResult.to_dict()."""
        tool_result = ToolResult(
            content=[
                ToolContentItem(type="text", text="Result"),
            ],
            is_error=False,
        )
        result = tool_result.to_dict()
        assert len(result["content"]) == 1
        assert result["content"][0]["text"] == "Result"
        assert "isError" not in result

    def test_tool_result_with_error(self):
        """Test ToolResult.to_dict() with error."""
        tool_result = ToolResult(
            content=[ToolContentItem(type="text", text="Error")],
            is_error=True,
        )
        result = tool_result.to_dict()
        assert result["isError"] is True


class TestMcpHandlerRegisterTool:
    """Tests for McpHandler.register_tool()."""

    def test_register_tool(self, mcp_handler):
        """Test registering a tool."""
        mcp_handler.register_tool(
            name="test-tool",
            description="Test tool",
            input_schema={"type": "object", "properties": {}},
            handler=lambda args: ToolResult(
                content=[ToolContentItem(type="text", text="ok")]
            ),
        )
        tools = mcp_handler.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "test-tool"

    def test_tool_decorator(self, mcp_handler):
        """Test @tool decorator."""

        @mcp_handler.tool(
            name="decorated-tool",
            description="Decorated tool",
            input_schema={"type": "object", "properties": {}},
        )
        def my_tool(args):
            return ToolResult(content=[ToolContentItem(type="text", text="ok")])

        tools = mcp_handler.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "decorated-tool"


class TestMcpHandlerGetTools:
    """Tests for McpHandler.get_tools()."""

    def test_empty_initially(self, mcp_handler):
        """Test handler has no tools initially."""
        tools = mcp_handler.get_tools()
        assert len(tools) == 0

    def test_returns_registered_tools(self, mcp_handler):
        """Test get_tools returns registered tools."""
        mcp_handler.register_tool(
            name="tool1",
            description="Tool 1",
            input_schema={"type": "object", "properties": {}},
            handler=lambda args: ToolResult(content=[]),
        )
        mcp_handler.register_tool(
            name="tool2",
            description="Tool 2",
            input_schema={"type": "object", "properties": {}},
            handler=lambda args: ToolResult(content=[]),
        )
        tools = mcp_handler.get_tools()
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "tool1" in names
        assert "tool2" in names


class TestMcpHandlerHandleRequest:
    """Tests for McpHandler.handle_request()."""

    def test_initialize_method(self, mcp_handler):
        """Test handling initialize method."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        response = mcp_handler.handle_request(request)
        assert response.id == 1
        assert response.error is None
        assert response.result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in response.result
        assert "serverInfo" in response.result

    def test_tools_list_method(self, mcp_handler):
        """Test handling tools/list method."""
        mcp_handler.register_tool(
            name="test-tool",
            description="Test",
            input_schema={"type": "object", "properties": {}},
            handler=lambda args: ToolResult(content=[]),
        )
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        response = mcp_handler.handle_request(request)
        assert response.error is None
        assert len(response.result["tools"]) == 1
        assert response.result["tools"][0]["name"] == "test-tool"

    def test_tools_call_method(self, mcp_handler):
        """Test handling tools/call method."""
        mcp_handler.register_tool(
            name="echo",
            description="Echo tool",
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
            },
            handler=lambda args: ToolResult(
                content=[ToolContentItem(type="text", text=args.get("message", ""))]
            ),
        )
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"message": "Hello"},
            },
        }
        response = mcp_handler.handle_request(request)
        assert response.error is None
        assert response.result["content"][0]["text"] == "Hello"

    def test_ping_method(self, mcp_handler):
        """Test handling ping method."""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "ping",
            "params": {},
        }
        response = mcp_handler.handle_request(request)
        assert response.error is None
        assert response.result == {}

    def test_method_not_found(self, mcp_handler):
        """Test method not found error."""
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "unknown/method",
            "params": {},
        }
        response = mcp_handler.handle_request(request)
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert "unknown/method" in response.error.message

    def test_invalid_request_not_object(self, mcp_handler):
        """Test invalid request (not an object)."""
        response = mcp_handler.handle_request("not an object")
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST

    def test_invalid_request_missing_jsonrpc(self, mcp_handler):
        """Test invalid request (missing jsonrpc)."""
        request = {"id": 1, "method": "ping"}
        response = mcp_handler.handle_request(request)
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST

    def test_invalid_request_wrong_jsonrpc(self, mcp_handler):
        """Test invalid request (wrong jsonrpc version)."""
        request = {"jsonrpc": "1.0", "id": 1, "method": "ping"}
        response = mcp_handler.handle_request(request)
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST

    def test_invalid_request_missing_method(self, mcp_handler):
        """Test invalid request (missing method)."""
        request = {"jsonrpc": "2.0", "id": 1}
        response = mcp_handler.handle_request(request)
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.INVALID_REQUEST

    def test_invalid_params(self, mcp_handler):
        """Test invalid params (not an object)."""
        request = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": "string"}
        response = mcp_handler.handle_request(request)
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.INVALID_PARAMS

    def test_tool_not_found(self, mcp_handler):
        """Test tool not found error."""
        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "nonexistent-tool", "arguments": {}},
        }
        response = mcp_handler.handle_request(request)
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert "nonexistent-tool" in response.error.message

    def test_tools_call_invalid_name(self, mcp_handler):
        """Test tools/call with invalid name parameter."""
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": 123, "arguments": {}},
        }
        response = mcp_handler.handle_request(request)
        assert response.error is not None
        assert response.error.code == JsonRpcErrorCode.INVALID_PARAMS

    def test_notification_no_id(self, mcp_handler):
        """Test notification (no id) is handled."""
        request = {
            "jsonrpc": "2.0",
            "method": "ping",
            "params": {},
        }
        response = mcp_handler.handle_request(request)
        assert response.id is None
        assert response.error is None
