"""Integration tests for the Auth MCP Server."""

import json

import pytest
from flask.testing import FlaskClient


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_returns_200(self, client: FlaskClient):
        """Test health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_json(self, client: FlaskClient):
        """Test health endpoint returns JSON."""
        response = client.get("/health")
        assert response.content_type == "application/json"

    def test_status_is_ok(self, client: FlaskClient):
        """Test health response has status 'ok'."""
        response = client.get("/health")
        data = response.get_json()
        assert data["status"] == "ok"

    def test_has_timestamp(self, client: FlaskClient):
        """Test health response has timestamp."""
        response = client.get("/health")
        data = response.get_json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)

    def test_has_uptime(self, client: FlaskClient):
        """Test health response has uptime."""
        response = client.get("/health")
        data = response.get_json()
        assert "uptime" in data
        assert isinstance(data["uptime"], int)


class TestOAuthProtectedResource:
    """Tests for /.well-known/oauth-protected-resource endpoint."""

    def test_returns_200(self, client: FlaskClient):
        """Test endpoint returns 200."""
        response = client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200

    def test_returns_json(self, client: FlaskClient):
        """Test endpoint returns JSON."""
        response = client.get("/.well-known/oauth-protected-resource")
        assert response.content_type == "application/json"

    def test_has_resource(self, client: FlaskClient):
        """Test response has resource field."""
        response = client.get("/.well-known/oauth-protected-resource")
        data = response.get_json()
        assert "resource" in data
        assert "/mcp" in data["resource"]

    def test_has_authorization_servers(self, client: FlaskClient):
        """Test response has authorization_servers."""
        response = client.get("/.well-known/oauth-protected-resource")
        data = response.get_json()
        assert "authorization_servers" in data
        assert isinstance(data["authorization_servers"], list)

    def test_has_scopes_supported(self, client: FlaskClient):
        """Test response has scopes_supported."""
        response = client.get("/.well-known/oauth-protected-resource")
        data = response.get_json()
        assert "scopes_supported" in data
        assert isinstance(data["scopes_supported"], list)

    def test_has_cors_headers(self, client: FlaskClient):
        """Test response has CORS headers."""
        response = client.get("/.well-known/oauth-protected-resource")
        assert "Access-Control-Allow-Origin" in response.headers

    def test_mcp_specific_endpoint(self, client: FlaskClient):
        """Test MCP-specific protected resource endpoint."""
        response = client.get("/.well-known/oauth-protected-resource/mcp")
        assert response.status_code == 200
        data = response.get_json()
        assert "resource" in data


class TestOpenIDConfiguration:
    """Tests for /.well-known/openid-configuration endpoint."""

    def test_returns_200(self, client: FlaskClient):
        """Test endpoint returns 200."""
        response = client.get("/.well-known/openid-configuration")
        assert response.status_code == 200

    def test_has_issuer(self, client: FlaskClient):
        """Test response has issuer."""
        response = client.get("/.well-known/openid-configuration")
        data = response.get_json()
        assert "issuer" in data

    def test_has_authorization_endpoint(self, client: FlaskClient):
        """Test response has authorization_endpoint."""
        response = client.get("/.well-known/openid-configuration")
        data = response.get_json()
        assert "authorization_endpoint" in data

    def test_has_token_endpoint(self, client: FlaskClient):
        """Test response has token_endpoint."""
        response = client.get("/.well-known/openid-configuration")
        data = response.get_json()
        assert "token_endpoint" in data

    def test_has_scopes_supported(self, client: FlaskClient):
        """Test response has scopes_supported."""
        response = client.get("/.well-known/openid-configuration")
        data = response.get_json()
        assert "scopes_supported" in data
        assert "openid" in data["scopes_supported"]


class TestOAuthAuthorizationServer:
    """Tests for /.well-known/oauth-authorization-server endpoint."""

    def test_returns_200(self, client: FlaskClient):
        """Test endpoint returns 200."""
        response = client.get("/.well-known/oauth-authorization-server")
        assert response.status_code == 200

    def test_has_response_types_supported(self, client: FlaskClient):
        """Test response has response_types_supported."""
        response = client.get("/.well-known/oauth-authorization-server")
        data = response.get_json()
        assert "response_types_supported" in data
        assert "code" in data["response_types_supported"]

    def test_has_grant_types_supported(self, client: FlaskClient):
        """Test response has grant_types_supported."""
        response = client.get("/.well-known/oauth-authorization-server")
        data = response.get_json()
        assert "grant_types_supported" in data
        assert "authorization_code" in data["grant_types_supported"]


class TestMcpEndpoint:
    """Tests for POST /mcp endpoint."""

    def test_initialize(self, client: FlaskClient, json_rpc_initialize_request):
        """Test initialize method."""
        response = client.post(
            "/mcp",
            json=json_rpc_initialize_request,
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert data["result"]["protocolVersion"] == "2024-11-05"

    def test_tools_list(self, client: FlaskClient, json_rpc_tools_list_request):
        """Test tools/list method."""
        response = client.post(
            "/mcp",
            json=json_rpc_tools_list_request,
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "result" in data
        assert "tools" in data["result"]
        # Should have weather tools registered
        tool_names = [t["name"] for t in data["result"]["tools"]]
        assert "get-weather" in tool_names

    def test_tools_call_get_weather(self, client: FlaskClient, json_rpc_tools_call_request):
        """Test tools/call for get-weather."""
        response = client.post(
            "/mcp",
            json=json_rpc_tools_call_request,
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "result" in data
        assert "content" in data["result"]
        content = json.loads(data["result"]["content"][0]["text"])
        assert content["city"] == "London"
        assert "temperature" in content
        assert "condition" in content

    def test_invalid_json_returns_parse_error(self, client: FlaskClient):
        """Test invalid JSON returns parse error."""
        response = client.post(
            "/mcp",
            data="not valid json",
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "error" in data
        assert data["error"]["code"] == -32700  # PARSE_ERROR

    def test_method_not_found(self, client: FlaskClient):
        """Test unknown method returns method not found error."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "unknown/method",
                "params": {},
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "error" in data
        assert data["error"]["code"] == -32601  # METHOD_NOT_FOUND

    def test_has_cors_headers(self, client: FlaskClient, json_rpc_initialize_request):
        """Test response has CORS headers."""
        response = client.post(
            "/mcp",
            json=json_rpc_initialize_request,
            content_type="application/json",
        )
        assert "Access-Control-Allow-Origin" in response.headers


class TestRpcEndpoint:
    """Tests for POST /rpc endpoint (alternative to /mcp)."""

    def test_rpc_endpoint_works(self, client: FlaskClient, json_rpc_initialize_request):
        """Test /rpc endpoint works same as /mcp."""
        response = client.post(
            "/rpc",
            json=json_rpc_initialize_request,
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "result" in data
        assert data["result"]["protocolVersion"] == "2024-11-05"


class TestCorsPreflightHandlers:
    """Tests for CORS preflight (OPTIONS) handlers."""

    def test_mcp_options(self, client: FlaskClient):
        """Test OPTIONS /mcp returns correct headers."""
        response = client.options("/mcp")
        assert response.status_code == 204
        assert "Access-Control-Allow-Methods" in response.headers

    def test_rpc_options(self, client: FlaskClient):
        """Test OPTIONS /rpc returns correct headers."""
        response = client.options("/rpc")
        assert response.status_code == 204

    def test_oauth_protected_resource_options(self, client: FlaskClient):
        """Test OPTIONS /.well-known/oauth-protected-resource."""
        response = client.options("/.well-known/oauth-protected-resource")
        assert response.status_code == 204

    def test_oauth_register_options(self, client: FlaskClient):
        """Test OPTIONS /oauth/register."""
        response = client.options("/oauth/register")
        assert response.status_code == 204


class TestOAuthRegisterEndpoint:
    """Tests for POST /oauth/register endpoint."""

    def test_returns_201(self, client: FlaskClient):
        """Test endpoint returns 201."""
        response = client.post(
            "/oauth/register",
            json={"redirect_uris": ["http://localhost:8080/callback"]},
            content_type="application/json",
        )
        assert response.status_code == 201

    def test_returns_client_id(self, client: FlaskClient):
        """Test response has client_id."""
        response = client.post(
            "/oauth/register",
            json={},
            content_type="application/json",
        )
        data = response.get_json()
        assert "client_id" in data

    def test_preserves_redirect_uris(self, client: FlaskClient):
        """Test redirect_uris are preserved."""
        uris = ["http://localhost:8080/callback", "http://localhost:3000/auth"]
        response = client.post(
            "/oauth/register",
            json={"redirect_uris": uris},
            content_type="application/json",
        )
        data = response.get_json()
        assert data["redirect_uris"] == uris


class TestFullFlow:
    """Tests for complete MCP flow."""

    def test_initialize_then_tools_list_then_call(self, client: FlaskClient):
        """Test complete flow: initialize -> tools/list -> tools/call."""
        # Initialize
        init_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
            content_type="application/json",
        )
        assert init_response.status_code == 200
        init_data = init_response.get_json()
        assert "result" in init_data

        # List tools
        list_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
            content_type="application/json",
        )
        assert list_response.status_code == 200
        list_data = list_response.get_json()
        assert "tools" in list_data["result"]
        assert len(list_data["result"]["tools"]) >= 3  # At least 3 weather tools

        # Call get-weather tool
        call_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get-weather",
                    "arguments": {"city": "New York"},
                },
            },
            content_type="application/json",
        )
        assert call_response.status_code == 200
        call_data = call_response.get_json()
        assert "result" in call_data
        weather = json.loads(call_data["result"]["content"][0]["text"])
        assert weather["city"] == "New York"

    def test_get_forecast_without_auth(self, client: FlaskClient):
        """Test get-forecast works when auth is disabled."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get-forecast",
                    "arguments": {"city": "Tokyo"},
                },
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        # Auth is disabled, so should succeed
        assert "result" in data
        forecast = json.loads(data["result"]["content"][0]["text"])
        assert forecast["city"] == "Tokyo"
        assert len(forecast["forecast"]) == 5

    def test_get_weather_alerts_without_auth(self, client: FlaskClient):
        """Test get-weather-alerts works when auth is disabled."""
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get-weather-alerts",
                    "arguments": {"region": "California"},
                },
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        # Auth is disabled, so should succeed
        assert "result" in data
        alerts = json.loads(data["result"]["content"][0]["text"])
        assert "region" in alerts
        assert "alerts" in alerts
