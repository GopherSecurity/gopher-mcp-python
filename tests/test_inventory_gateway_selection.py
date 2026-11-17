"""Enforce gateway routing before SDK OAuth probing or native JSON creation."""

import json
from urllib.parse import parse_qsl, urlsplit

import pytest

import gopher_mcp_python.agent as agent_module
import gopher_mcp_python.server_config as transport
from gopher_mcp_python import AgentError, GopherAgent
from gopher_mcp_python.inventory_response import normalize_inventory_response


def source(name="Production", source_id="g1", kind="gateways", path_id=None):
    return {
        "id": source_id,
        "name": name,
        "transport": "http",
        "config": {
            "url": f"https://mcp.example/v1/mcp/{kind}/{path_id or source_id}/mcp",
            "headers": {"Authorization": "Bearer source-token"},
        },
    }


def envelope(sources):
    return json.dumps({"succeeded": True, "data": {"servers": sources}})


def normalize(sources, selection):
    return json.loads(normalize_inventory_response(envelope(sources), selection))[
        "data"
    ]["servers"]


@pytest.mark.parametrize(
    "selection", [{"gatewayId": ["g1"]}, {"gatewayName": ["Production"]}]
)
@pytest.mark.parametrize(
    "response_kind",
    ["empty", "backing-only", "gateway-plus-backing", "unrequested-gateway"],
)
def test_gateway_only_selection_rejects_flattening_or_unrequested_routes(
    selection, response_kind
):
    gateway = source()
    backing = source(kind="servers")
    backing["type"] = "gateway"
    rows = {
        "empty": [],
        "backing-only": [backing],
        "gateway-plus-backing": [gateway, source("Backing", "s1", "servers")],
        "unrequested-gateway": [gateway, source("Other", "g2")],
    }[response_kind]
    with pytest.raises(AgentError, match="gateway"):
        normalize(rows, selection)


@pytest.mark.parametrize("scheme", ["https", "http", "wss", "ws"])
@pytest.mark.parametrize(
    "suffix", ["/mcp", "/sse", "/mcp/", "/sse/?session=fixture#fragment"]
)
def test_gateway_paths_match_metadata_or_decoded_path_identity(scheme, suffix):
    gateway = source(source_id="numeric-id")
    gateway["config"][
        "url"
    ] = f"{scheme}://mcp.example/%76%31/mcp/gateways/public%2Did{suffix}"
    selection = {
        "gatewayId": ["numeric-id", "public-id"],
        "gatewayName": ["Production"],
    }
    assert normalize([gateway, gateway], selection) == [gateway]


@pytest.mark.parametrize("identity_key", ["id", "serverId", "server_id"])
def test_gateway_metadata_uses_native_identity_fields(identity_key):
    gateway = source(source_id="public-id")
    del gateway["id"]
    gateway[identity_key] = "numeric-id"
    assert normalize([gateway], {"gatewayId": ["numeric-id", "public-id"]}) == [gateway]


@pytest.mark.parametrize(
    "url",
    [
        "https://mcp.example/v1/mcp/servers/g1/mcp?next=/v1/mcp/gateways/g1/mcp",
        "https://mcp.example/v1/mcp/servers/g1/mcp#/v1/mcp/gateways/g1/mcp",
        "https://mcp.example/prefix/v1/mcp/gateways/g1/mcp",
        "https://mcp.example/v1/mcp/gateways/g1/mcp/extra",
        "https://mcp.example/v1/mcp/gateways/../mcp",
        "https://mcp.example/v1/mcp/gateways/%2e%2e/mcp",
        "https://mcp.example/v1/mcp/gateways/g1%2fother/mcp",
        "https://mcp.example/v1/mcp/gateways/g1%5cother/mcp",
        "https://mcp.example/v1/mcp/gateways/g1%00/mcp",
        "https://mcp.example/v1/mcp/gateways/g1%0a/mcp",
        "https://mcp.example/v1/mcp/gateways/g1%zz/mcp",
        "https://mcp.example/v1/mcp/gateways/g1/mcp/../../servers/s1/mcp",
        "https://mcp.example/v1/mcp/gateways/g1/mcp\n",
        "ftp://mcp.example/v1/mcp/gateways/g1/mcp",
        "https:///v1/mcp/gateways/g1/mcp",
        "https://[invalid/v1/mcp/gateways/g1/mcp",
        "https://mcp.example:invalid/v1/mcp/gateways/g1/mcp",
        "https://mcp.example/custom-mcp",
    ],
)
def test_gateway_markers_cannot_override_invalid_or_backing_url_paths(url):
    gateway = source()
    gateway.update(type="gateway", gatewayId="g1")
    gateway["config"]["url"] = url
    with pytest.raises(AgentError, match="gateway"):
        normalize([gateway], {"gatewayId": ["g1"]})


@pytest.mark.parametrize(
    "selection",
    [
        {"gatewayId": ["g1", "g2"]},
        {"gatewayName": ["Production", "Staging"]},
        {"gatewayId": ["missing"], "serverId": ["s1"]},
        {"gatewayId": ["g1"], "gatewayName": ["wrong"], "serverId": ["s1"]},
    ],
)
def test_every_requested_gateway_must_be_present_even_for_mixed_selection(selection):
    gateway, direct = source(), source("Direct", "s1", "servers")
    with pytest.raises(AgentError, match="gateway"):
        normalize([gateway, direct], selection)


@pytest.mark.parametrize(
    "direct_selection", [{"serverId": ["s1"]}, {"serverName": ["Direct"]}]
)
def test_mixed_selection_accepts_only_explicitly_selected_direct_sources(
    direct_selection,
):
    gateway, direct = source(), source("Direct", "s1", "servers")
    selection = dict(direct_selection, gatewayId=["g1"])
    assert normalize([gateway, direct], selection) == [gateway, direct]
    with pytest.raises(AgentError, match="gateway"):
        normalize([gateway, direct, source("Backing", "s2", "servers")], selection)


def test_mixed_direct_path_identity_and_source_id_precedence():
    gateway, direct = source(), source("Direct", "numeric-id", "servers", "public-id")
    gateway["serverId"] = "ignored-alias"
    assert normalize(
        [gateway, direct], {"gatewayId": ["g1"], "serverId": ["public-id"]}
    ) == [gateway, direct]
    with pytest.raises(AgentError, match="gateway"):
        normalize([gateway], {"gatewayId": ["ignored-alias"]})


def test_effective_config_controls_route_classification():
    gateway = source()
    gateway["url"] = "https://mcp.example/v1/mcp/servers/g1/mcp"
    gateway["http_sse"] = {"url": gateway["url"]}
    assert normalize([gateway], {"gatewayId": ["g1"]}) == [gateway]
    gateway["http_sse"] = dict(gateway["config"])
    gateway["config"]["url"] = gateway["url"]
    with pytest.raises(AgentError, match="gateway"):
        normalize([gateway], {"gatewayId": ["g1"]})


def test_effective_fallback_gateway_endpoint_is_checked():
    gateway = source()
    gateway["http_sse"] = gateway.pop("config")
    normalized = normalize([gateway], {"gatewayId": ["g1"]})
    assert normalized[0]["config"] == gateway["http_sse"]


def test_no_gateway_selector_preserves_custom_endpoint_and_default_selection():
    direct = source("Direct", "s1", "servers")
    direct["config"]["url"] = "https://custom.example/mcp"
    assert normalize([direct], {}) == [direct]
    assert normalize([direct], {"serverId": ["s1"]}) == [direct]
    assert normalize([], {}) == []


def test_distinct_duplicate_names_receive_native_runtime_aliases():
    sources = normalize([source("Shared", "g1"), source("Shared", "g2")], {})
    assert [source["name"] for source in sources] == ["Shared__g1", "Shared__g2"]


FACTORIES = [
    ("create_with_gateway_id", "g1", {}),
    ("create_with_gateway_name", "Production", {}),
    ("create_with_api_key", None, {"gateway_ids": ["g1"]}),
    ("create_with_server_id", "s1", {"gateway_ids": ["g1"]}),
    ("create_with_server_name", "Direct", {"gateway_names": ["Production"]}),
]


def install_inventory(monkeypatch, rows):
    requests = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return envelope(rows).encode()

    def fetch(request, timeout):
        if request.method == "GET":
            selected = {
                key: []
                for key in ("serverId", "serverName", "gatewayId", "gatewayName")
            }
            for key, value in parse_qsl(urlsplit(request.full_url).query):
                selected[key].append(value)
        else:
            selected = json.loads(request.data)
        requests.append(selected)
        return Response()

    monkeypatch.setattr(transport, "urlopen", fetch)
    return requests


@pytest.mark.parametrize("method, positional, selectors", FACTORIES)
@pytest.mark.parametrize(
    "auth", [{}, {"oauth": {"mode": "disabled"}}, {"access_token": "explicit-token"}]
)
def test_gateway_validation_runs_before_oauth_or_native_for_every_factory(
    monkeypatch, method, positional, selectors, auth
):
    requests = install_inventory(monkeypatch, [source(kind="servers")])

    def native_access():
        pytest.fail("Flattened inventory reached native initialization")

    async def oauth_access(*args, **kwargs):
        pytest.fail("Flattened inventory reached OAuth resolution")

    monkeypatch.setattr(agent_module.GopherOrchLibrary, "get_instance", native_access)
    monkeypatch.setattr(
        agent_module.oauth_resolver, "resolve_runtime_options_with_oauth", oauth_access
    )
    args = ["provider", "model", "project-key"] + ([positional] if positional else [])
    with pytest.raises(AgentError, match="gateway"):
        getattr(GopherAgent, method)(*args, runtime_options=dict(auth, **selectors))
    assert len(requests) == 1
    assert requests[0]["gatewayId"] or requests[0]["gatewayName"]


def test_positional_and_additive_gateway_selection_reaches_one_native_json_creation(
    monkeypatch,
):
    gateways = [source(), source("Staging", "g2")]
    direct = source("Direct", "s1", "servers")
    requests = install_inventory(monkeypatch, gateways + [direct])
    created = []

    class Library:
        def agent_create_by_json(self, provider, model, config, options):
            created.append(json.loads(config)["data"]["servers"])
            return 123

        def agent_release(self, handle):
            pass

    monkeypatch.setattr(
        agent_module.GopherOrchLibrary, "get_instance", lambda: Library()
    )
    agent = GopherAgent.create_with_gateway_id(
        "provider",
        "model",
        "project-key",
        "g1",
        {
            "gateway_ids": ["g2"],
            "server_ids": ["s1"],
            "oauth": {"mode": "disabled"},
        },
    )
    try:
        assert len(requests) == 1
        assert requests[0]["gatewayId"] == ["g1", "g2"]
        assert requests[0]["serverId"] == ["s1"]
        assert created == [gateways + [direct]]
    finally:
        agent.dispose()
