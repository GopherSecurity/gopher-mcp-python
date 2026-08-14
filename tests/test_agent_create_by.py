"""
Contract tests for the five routing factories on GopherAgent.

Mirrors the failure-path test set in
gopher-orch/tests/gopher/orch/agent_create_by_test.cc which locks down
the nullptr-on-failure contract that the C FFI surfaces here as
AgentError. Happy-path coverage needs a stubbed HTTP listener capturing
the /v1/mcp-servers query string with the camelCase routing keys
(serverId / serverName / gatewayId / gatewayName); that infrastructure
is tracked separately, same as on the C++ side.
"""

import pytest

from gopher_mcp_python import AgentError, GopherAgent
from gopher_mcp_python.ffi import GopherOrchLibrary

PROVIDER = "AnthropicProvider"
MODEL = "test-model"
BAD_PROVIDER = "NotARealProvider"
URL = "http://127.0.0.1:1/mcp"

ROUTING_FACTORY_SYMBOLS = [
    "gopher_orch_agent_create_by_server_id",
    "gopher_orch_agent_create_by_server_name",
    "gopher_orch_agent_create_by_gateway_id",
    "gopher_orch_agent_create_by_gateway_name",
    "gopher_orch_agent_create_by_url",
]


def has_routing_factory_symbols() -> bool:
    lib = GopherOrchLibrary.get_instance()
    if lib is None or lib._lib is None:
        return False
    return all(hasattr(lib._lib, symbol) for symbol in ROUTING_FACTORY_SYMBOLS)


pytestmark = pytest.mark.skipif(
    not has_routing_factory_symbols(),
    reason=(
        "Native routing factory symbols not available -- use a libgopher-orch "
        "release that includes them"
    ),
)


class TestRoutingFactoryContracts:
    """Failure-path contract for the five routing factories on GopherAgent."""

    # ----------------------------------------------------------------
    # Empty api key. fetch_mcp_servers throws on the native side; the
    # factory must surface that as AgentError rather than returning a
    # partially-constructed agent or a null handle leaking through.
    # ----------------------------------------------------------------

    def test_create_with_server_id_rejects_empty_api_key(self) -> None:
        with pytest.raises(AgentError):
            GopherAgent.create_with_server_id(PROVIDER, MODEL, "", "srv-1")

    def test_create_with_server_name_rejects_empty_api_key(self) -> None:
        with pytest.raises(AgentError):
            GopherAgent.create_with_server_name(PROVIDER, MODEL, "", "my-server")

    def test_create_with_gateway_id_rejects_empty_api_key(self) -> None:
        with pytest.raises(AgentError):
            GopherAgent.create_with_gateway_id(PROVIDER, MODEL, "", "gw-1")

    def test_create_with_gateway_name_rejects_empty_api_key(self) -> None:
        with pytest.raises(AgentError):
            GopherAgent.create_with_gateway_name(PROVIDER, MODEL, "", "my-gateway")

    # ----------------------------------------------------------------
    # Mirrors the native CreateByUrlRejectsEmptyUrl case. The Python wrapper
    # delegates validation to libgopher-orch and surfaces it as AgentError.
    # ----------------------------------------------------------------

    def test_create_with_url_rejects_empty_url(self) -> None:
        with pytest.raises(AgentError):
            GopherAgent.create_with_url(PROVIDER, MODEL, "")

    # ----------------------------------------------------------------
    # Unknown provider. create_with_url synthesises a local http_sse
    # config and reaches create_by_json on the native side, which
    # rejects an unknown provider name. Use an unlikely local port so the test
    # does not accidentally talk to a developer service on 8080.
    # ----------------------------------------------------------------

    def test_create_with_url_rejects_unknown_provider(self) -> None:
        with pytest.raises(AgentError):
            GopherAgent.create_with_url(
                BAD_PROVIDER,
                MODEL,
                URL,
                {"oauth": {"mode": "disabled"}},
            )

    # ----------------------------------------------------------------
    # AgentError surfaces a non-empty message so SDK consumers can log
    # a meaningful diagnostic; the C side fills last_error() and the
    # wrapper pump should propagate it through. A future change to the
    # error pump that swallows the underlying C diagnostic gets caught
    # here immediately.
    # ----------------------------------------------------------------

    def test_create_with_server_id_surfaces_non_empty_message(self) -> None:
        with pytest.raises(AgentError) as exc_info:
            GopherAgent.create_with_server_id(PROVIDER, MODEL, "", "srv-1")
        assert len(str(exc_info.value)) > 0
