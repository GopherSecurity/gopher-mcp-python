"""Tests for custom protected MCP endpoint harness."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from tests.helpers.custom_oauth_test_idp import (
    OAUTH_TEST_ACCESS_TOKEN,
    start_custom_oauth_test_idp,
)
from tests.helpers.custom_protected_mcp_endpoints import (
    CustomProtectedMcpEndpoint,
    CustomProtectedMcpEndpointsOptions,
    start_custom_protected_mcp_endpoints,
)


def test_server_and_gateway_endpoints_advertise_oauth_protection() -> None:
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
        )
    )
    try:
        for endpoint in (endpoints.server, endpoints.gateway):
            response = _post_json(endpoint.mcp_url, {"jsonrpc": "2.0", "id": "probe"})
            assert response.status == 401
            assert response.headers["WWW-Authenticate"] == (
                'Bearer realm="mcp", resource_metadata="'
                f'{endpoint.resource_metadata_url}"'
            )
    finally:
        endpoints.close()
        idp.close()


def test_server_and_gateway_metadata_points_to_custom_idp_issuer() -> None:
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
        )
    )
    try:
        for endpoint in (endpoints.server, endpoints.gateway):
            metadata = _fetch_json(endpoint.resource_metadata_url)
            assert metadata == {
                "resource": endpoint.mcp_url,
                "authorization_servers": [idp.issuer],
                "scopes_supported": ["openid", "profile", "email"],
            }
    finally:
        endpoints.close()
        idp.close()


def test_server_and_gateway_endpoints_reject_wrong_bearer_token() -> None:
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
        )
    )
    try:
        for endpoint in (endpoints.server, endpoints.gateway):
            response = _post_json(
                endpoint.mcp_url,
                {"jsonrpc": "2.0", "id": "wrong-token"},
                access_token="wrong-token",
            )
            assert response.status == 401
    finally:
        endpoints.close()
        idp.close()


def test_server_and_gateway_endpoints_accept_deterministic_bearer_token() -> None:
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
        )
    )
    try:
        for endpoint in (endpoints.server, endpoints.gateway):
            body = _post_authenticated(endpoint)
            assert body["result"] == {
                "endpoint": endpoint.kind,
                "authenticated": True,
            }
    finally:
        endpoints.close()
        idp.close()


def test_close_stops_both_local_endpoints() -> None:
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
        )
    )
    server_metadata_url = endpoints.server.resource_metadata_url
    gateway_metadata_url = endpoints.gateway.resource_metadata_url
    endpoints.close()
    idp.close()

    with pytest.raises(urllib.error.URLError):
        _fetch_json(server_metadata_url)
    with pytest.raises(urllib.error.URLError):
        _fetch_json(gateway_metadata_url)


def _post_authenticated(endpoint: CustomProtectedMcpEndpoint) -> object:
    response = _post_json(
        endpoint.mcp_url,
        {"jsonrpc": "2.0", "id": endpoint.kind},
        access_token=OAUTH_TEST_ACCESS_TOKEN,
    )
    assert response.status == 200
    return response.body


class _Response:
    def __init__(
        self,
        status: int,
        headers: dict,
        body: object = None,
    ) -> None:
        self.status = status
        self.headers = headers
        self.body = body


def _fetch_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(
    url: str,
    body: object,
    access_token: str = "",
) -> _Response:
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers=headers,
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response_body = response.read()
            parsed_body = json.loads(response_body.decode("utf-8"))
            return _Response(response.status, dict(response.headers), parsed_body)
    except urllib.error.HTTPError as exc:
        return _Response(exc.code, dict(exc.headers))
