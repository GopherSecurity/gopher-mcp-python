"""Pytest fixtures for py_auth_mcp_server tests."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

from gopher_mcp_python.ffi.auth import AuthContext
from py_auth_mcp_server import AuthServerConfig, create_app, create_default_config
from py_auth_mcp_server.routes.mcp_handler import McpHandler


@pytest.fixture
def sample_config() -> AuthServerConfig:
    """Create a sample configuration for testing.

    Returns:
        AuthServerConfig with auth_disabled=True.
    """
    return create_default_config(
        host="127.0.0.1",
        port=5000,
        server_url="http://localhost:5000",
        auth_disabled=True,
        allowed_scopes="openid profile email mcp:read mcp:admin",
    )


@pytest.fixture
def app(sample_config: AuthServerConfig) -> Flask:
    """Create a Flask application for testing.

    Args:
        sample_config: Test configuration.

    Returns:
        Configured Flask application.
    """
    application = create_app(config=sample_config)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create a test client for the Flask application.

    Args:
        app: Flask application.

    Returns:
        Flask test client.
    """
    return app.test_client()


@pytest.fixture
def mcp_handler() -> McpHandler:
    """Create a fresh McpHandler instance for testing.

    Returns:
        New McpHandler instance.
    """
    return McpHandler()


@pytest.fixture
def mock_auth_context() -> AuthContext:
    """Create a mock AuthContext with test data.

    Returns:
        AuthContext with sample values.
    """
    return AuthContext(
        user_id="test-user-123",
        scopes="openid profile email mcp:read",
        audience="test-audience",
        token_expiry=9999999999,
        authenticated=True,
    )


@pytest.fixture
def mock_admin_auth_context() -> AuthContext:
    """Create a mock AuthContext with admin scopes.

    Returns:
        AuthContext with mcp:admin scope.
    """
    return AuthContext(
        user_id="admin-user-456",
        scopes="openid profile email mcp:read mcp:admin",
        audience="test-audience",
        token_expiry=9999999999,
        authenticated=True,
    )


@pytest.fixture
def mock_unauthenticated_context() -> AuthContext:
    """Create a mock unauthenticated AuthContext.

    Returns:
        AuthContext with authenticated=False.
    """
    return AuthContext(
        user_id="",
        scopes="",
        audience="",
        token_expiry=0,
        authenticated=False,
    )


@pytest.fixture
def json_rpc_initialize_request() -> dict:
    """Create a JSON-RPC initialize request.

    Returns:
        JSON-RPC request for initialize method.
    """
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0",
            },
        },
    }


@pytest.fixture
def json_rpc_tools_list_request() -> dict:
    """Create a JSON-RPC tools/list request.

    Returns:
        JSON-RPC request for tools/list method.
    """
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }


@pytest.fixture
def json_rpc_tools_call_request() -> dict:
    """Create a JSON-RPC tools/call request for get-weather.

    Returns:
        JSON-RPC request for tools/call method.
    """
    return {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get-weather",
            "arguments": {
                "city": "London",
            },
        },
    }
