"""Failure-mode tests for custom IdP OAuth auto verification."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

import pytest

import gopher_mcp_python.agent as agent_module
import gopher_mcp_python.oauth_resolver as oauth_resolver
from gopher_mcp_python import GopherAgent
from gopher_mcp_python.runtime_options import GopherAgentTokenRecord
from tests.helpers.custom_oauth_test_idp import (
    OAUTH_TEST_ACCESS_TOKEN,
    OAUTH_TEST_CLIENT_ID,
    OAUTH_TEST_CLIENT_SECRET,
    OAUTH_TEST_REFRESH_TOKEN,
    start_custom_oauth_test_idp,
)
from tests.helpers.custom_protected_mcp_endpoints import (
    CustomProtectedMcpEndpointsOptions,
    start_custom_protected_mcp_endpoints,
)
from tests.helpers.oauth_test_token import refresh_test_oauth_token


PROVIDER = "AnthropicProvider"
MODEL = "test-model"
FIXTURE_SECRETS = [
    OAUTH_TEST_CLIENT_SECRET,
    OAUTH_TEST_REFRESH_TOKEN,
    OAUTH_TEST_ACCESS_TOKEN,
]


class _FakeLibrary:
    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def agent_create_by_url(self, provider, model, url, runtime_options=None):
        self.calls.append(("url", provider, model, url, runtime_options))
        return 5001

    def agent_release(self, handle):
        self.calls.append(("release", handle))

    def get_last_error_message(self):
        return None

    def clear_error(self):
        self.calls.append(("clear_error",))


class _RefreshTokenStore:
    def __init__(self, refresh_token: str) -> None:
        self.refresh_token = refresh_token
        self.deleted_keys: List[str] = []

    async def get(self, key: str) -> Optional[GopherAgentTokenRecord]:
        return GopherAgentTokenRecord(
            access_token="expired-access-token",
            refresh_token=self.refresh_token,
            token_type="Bearer",
            expires_at=0,
        )

    async def set(self, key: str, token: GopherAgentTokenRecord) -> None:
        return None

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


def test_wrong_refresh_token_returns_secret_safe_invalid_grant_failure() -> None:
    idp = start_custom_oauth_test_idp()
    try:
        _expect_failure_without_fixture_secrets(
            lambda: refresh_test_oauth_token(
                token_endpoint=idp.token_endpoint,
                client_id=OAUTH_TEST_CLIENT_ID,
                client_secret=OAUTH_TEST_CLIENT_SECRET,
                refresh_token="wrong-refresh-token",
            ),
            "invalid_grant",
        )
    finally:
        idp.close()


def test_wrong_client_credentials_return_secret_safe_invalid_client_failure() -> None:
    idp = start_custom_oauth_test_idp()
    try:
        _expect_failure_without_fixture_secrets(
            lambda: refresh_test_oauth_token(
                token_endpoint=idp.token_endpoint,
                client_id="wrong-client",
                client_secret=OAUTH_TEST_CLIENT_SECRET,
                refresh_token=OAUTH_TEST_REFRESH_TOKEN,
            ),
            "invalid_client",
        )
    finally:
        idp.close()


def test_unsupported_grant_type_returns_clear_oauth_failure() -> None:
    idp = start_custom_oauth_test_idp()
    try:
        response = _post_form(
            idp.token_endpoint,
            {
                "grant_type": "client_credentials",
                "client_id": OAUTH_TEST_CLIENT_ID,
                "client_secret": OAUTH_TEST_CLIENT_SECRET,
            },
        )
    finally:
        idp.close()

    assert response.status == 400
    assert response.body == {"error": "unsupported_grant_type"}


def test_missing_protected_resource_metadata_fields_fail_clearly(monkeypatch) -> None:
    fake = _install_fake_library(monkeypatch)
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
            protected_resource_metadata={"resource": "missing-authorization-servers"},
        )
    )
    try:
        _expect_failure_without_fixture_secrets(
            lambda: GopherAgent.create_with_url(
                PROVIDER,
                MODEL,
                endpoints.server.mcp_url,
            ),
            "authorization_servers",
        )
    finally:
        endpoints.close()
        idp.close()
        oauth_resolver.set_oauth_resolver_hooks_for_test()
        oauth_resolver.set_oauth_url_runtime_options_resolver_for_test()

    assert fake.calls == []


def test_wrong_bearer_token_is_rejected_by_protected_endpoint() -> None:
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
        )
    )
    try:
        response = _post_json(
            endpoints.server.mcp_url,
            {"jsonrpc": "2.0", "id": "wrong-token"},
            access_token="wrong-token",
        )
    finally:
        endpoints.close()
        idp.close()

    assert response.status == 401
    assert response.headers["WWW-Authenticate"].endswith(
        f'{endpoints.server.resource_metadata_url}"'
    )


def test_sdk_refresh_failure_stays_secret_safe_before_fallback_failure(
    monkeypatch,
) -> None:
    _install_fake_library(monkeypatch)
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
        )
    )
    token_store = _RefreshTokenStore("wrong-refresh-token")

    def open_authorization_url(url, open_browser=None):
        raise RuntimeError("authorization fallback disabled for failure test")

    monkeypatch.setattr(oauth_resolver, "open_authorization_url", open_authorization_url)

    try:
        _expect_failure_without_fixture_secrets(
            lambda: GopherAgent.create_with_url(
                PROVIDER,
                MODEL,
                endpoints.server.mcp_url,
                {
                    "oauth": {
                        "token_store": token_store,
                    },
                },
            ),
            "authorization fallback disabled for failure test",
        )
    finally:
        endpoints.close()
        idp.close()
        oauth_resolver.set_oauth_resolver_hooks_for_test()
        oauth_resolver.set_oauth_url_runtime_options_resolver_for_test()

    assert token_store.deleted_keys


def _install_fake_library(monkeypatch) -> _FakeLibrary:
    fake = _FakeLibrary()
    monkeypatch.setattr(agent_module, "_initialized", True)
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary,
        "get_instance",
        staticmethod(lambda: fake),
    )
    return fake


def _expect_failure_without_fixture_secrets(call, expected_message: str) -> None:
    with pytest.raises(Exception) as exc_info:
        call()

    message = str(exc_info.value)
    assert expected_message in message
    for secret in FIXTURE_SECRETS:
        assert secret not in message


class _Response:
    def __init__(self, status: int, headers: dict, body: object = None) -> None:
        self.status = status
        self.headers = headers
        self.body = body


def _post_form(url: str, params: Dict[str, str]) -> _Response:
    data = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return _send_request(request)


def _post_json(url: str, body: object, access_token: str = "") -> _Response:
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    return _send_request(request)


def _send_request(request: urllib.request.Request) -> _Response:
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read()
            parsed_body = json.loads(body.decode("utf-8")) if body else None
            return _Response(response.status, dict(response.headers), parsed_body)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read()
        except ConnectionError:
            body = b""
        parsed_body = json.loads(body.decode("utf-8")) if body else None
        return _Response(exc.code, dict(exc.headers), parsed_body)
