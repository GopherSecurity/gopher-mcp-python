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
URL = "http://127.0.0.1:8080/mcp"


pytestmark = pytest.mark.skipif(
    not GopherOrchLibrary.is_available(),
    reason="Native library not available -- run ./build.sh first",
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
    # create_with_url rejects empty url before any FFI work happens.
    # Mirrors the CreateByUrlRejectsEmptyUrl case in the C++ suite.
    # ----------------------------------------------------------------

    def test_create_with_url_rejects_empty_url(self) -> None:
        with pytest.raises(AgentError):
            GopherAgent.create_with_url(PROVIDER, MODEL, "")

    # ----------------------------------------------------------------
    # Unknown provider. create_with_url synthesises a local http_sse
    # config and reaches create_by_json on the native side, which
    # rejects an unknown provider name. The factory must surface that
    # as AgentError.
    # ----------------------------------------------------------------

    def test_create_with_url_rejects_unknown_provider(self) -> None:
        with pytest.raises(AgentError):
            GopherAgent.create_with_url(BAD_PROVIDER, MODEL, URL)

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
