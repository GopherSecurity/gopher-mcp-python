"""OAuth auto verification with custom IdP."""

from __future__ import annotations

from typing import Dict, List, Optional

import gopher_mcp_python.agent as agent_module
import gopher_mcp_python.oauth_resolver as oauth_resolver
from gopher_mcp_python import GopherAgent
from gopher_mcp_python.runtime_options import GopherAgentTokenRecord
from tests.helpers.custom_oauth_test_idp import (
    OAUTH_TEST_ACCESS_TOKEN,
    OAUTH_TEST_CLIENT_SECRET,
    OAUTH_TEST_REFRESH_TOKEN,
    start_custom_oauth_test_idp,
)
from tests.helpers.custom_protected_mcp_endpoints import (
    CustomProtectedMcpEndpoint,
    CustomProtectedMcpEndpointsOptions,
    start_custom_protected_mcp_endpoints,
)


PROVIDER = "AnthropicProvider"
MODEL = "test-model"


class _FakeLibrary:
    def __init__(self) -> None:
        self.calls: List[tuple] = []

    def agent_create_by_url(self, provider, model, url, runtime_options=None):
        self.calls.append(("url", provider, model, url, runtime_options))
        return 4001

    def agent_release(self, handle):
        self.calls.append(("release", handle))

    def get_last_error_message(self):
        return None

    def clear_error(self):
        self.calls.append(("clear_error",))


class _RefreshTokenStore:
    def __init__(self) -> None:
        self.tokens: Dict[str, GopherAgentTokenRecord] = {}
        self.set_calls: List[tuple] = []
        self.delete_calls: List[str] = []

    async def get(self, key: str) -> Optional[GopherAgentTokenRecord]:
        if key not in self.tokens:
            return GopherAgentTokenRecord(
                access_token="expired-access-token",
                refresh_token=OAUTH_TEST_REFRESH_TOKEN,
                token_type="Bearer",
                expires_at=0,
            )
        return self.tokens[key]

    async def set(self, key: str, token: GopherAgentTokenRecord) -> None:
        self.set_calls.append((key, token))
        self.tokens[key] = token

    async def delete(self, key: str) -> None:
        self.delete_calls.append(key)
        self.tokens.pop(key, None)


def test_injects_refreshed_token_for_direct_mcp_server_endpoint(
    monkeypatch,
    capsys,
) -> None:
    _expect_refreshed_token_injected_for_endpoint_name(
        monkeypatch,
        capsys,
        endpoint_name="server",
    )


def test_injects_refreshed_token_for_mcp_gateway_endpoint(
    monkeypatch,
    capsys,
) -> None:
    _expect_refreshed_token_injected_for_endpoint_name(
        monkeypatch,
        capsys,
        endpoint_name="gateway",
    )


def _expect_refreshed_token_injected_for_endpoint_name(
    monkeypatch,
    capsys,
    endpoint_name: str,
) -> None:
    idp = start_custom_oauth_test_idp()
    endpoints = start_custom_protected_mcp_endpoints(
        CustomProtectedMcpEndpointsOptions(
            authorization_server=idp.issuer,
            access_token=OAUTH_TEST_ACCESS_TOKEN,
        )
    )
    try:
        _expect_refreshed_token_injected_for_endpoint(
            monkeypatch,
            endpoint=getattr(endpoints, endpoint_name),
        )
    finally:
        endpoints.close()
        idp.close()
        oauth_resolver.set_oauth_resolver_hooks_for_test()
        oauth_resolver.set_oauth_url_runtime_options_resolver_for_test()

    captured = capsys.readouterr()
    assert OAUTH_TEST_CLIENT_SECRET not in captured.out
    assert OAUTH_TEST_CLIENT_SECRET not in captured.err
    assert OAUTH_TEST_REFRESH_TOKEN not in captured.out
    assert OAUTH_TEST_REFRESH_TOKEN not in captured.err
    assert OAUTH_TEST_ACCESS_TOKEN not in captured.out
    assert OAUTH_TEST_ACCESS_TOKEN not in captured.err


def _expect_refreshed_token_injected_for_endpoint(
    monkeypatch,
    endpoint: CustomProtectedMcpEndpoint,
) -> None:
    fake = _FakeLibrary()
    token_store = _RefreshTokenStore()
    monkeypatch.setattr(agent_module, "_initialized", True)
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary,
        "get_instance",
        staticmethod(lambda: fake),
    )

    agent = GopherAgent.create_with_url(
        PROVIDER,
        MODEL,
        endpoint.mcp_url,
        {
            "oauth": {
                "token_store": token_store,
            },
        },
    )

    call = fake.calls[0]
    assert call[:4] == ("url", PROVIDER, MODEL, endpoint.mcp_url)
    assert call[4].access_token == OAUTH_TEST_ACCESS_TOKEN
    assert token_store.set_calls
    assert token_store.set_calls[0][1].access_token == OAUTH_TEST_ACCESS_TOKEN
    assert token_store.set_calls[0][1].token_type == "Bearer"
    agent.dispose()
