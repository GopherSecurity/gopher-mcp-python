"""Remote inventory is network configuration, never local execution or env input."""

import json

import pytest

from gopher_mcp_python.errors import AgentError
from gopher_mcp_python.inventory_response import normalize_inventory_response
from gopher_mcp_python.oauth_server_targets import extract_mcp_server_targets

NETWORK_TRANSPORTS = [
    "http_sse",
    "http-sse",
    "sse",
    "streamable_http",
    "streamable-http",
    "http_stream",
    "http",
    "websocket",
    "ws",
]


def entry(name="mail", **extra):
    return dict(
        name=name, transport="http", config={"url": "https://example/mcp"}, **extra
    )


def envelope(rows, **extra):
    return json.dumps({"succeeded": True, "data": dict(servers=rows, **extra)})


def test_preserves_routes_and_deduplicates():
    row = entry(id="id", serverId="wrong")
    result = normalize_inventory_response(envelope([row, row, entry("gateway")]))
    assert len(json.loads(result)["data"]["servers"]) == 2
    assert extract_mcp_server_targets(server_config=result)[0]["server_id"] == "id"


def test_authoritative_config_url_is_used_by_oauth_targets():
    row = entry()
    row["url"] = "https://unused.invalid/${UNUSED_REFERENCE}"
    result = normalize_inventory_response(envelope([row]))
    assert (
        extract_mcp_server_targets(server_config=result)[0]["url"]
        == row["config"]["url"]
    )


def test_gateway_summaries_preserve_only_connectable_server_sources():
    rows = [entry("mail"), entry("calendar")]
    body = envelope(rows, gateways=[{"gatewayId": "g1", "name": "mail"}])
    normalized = normalize_inventory_response(body)
    assert json.loads(normalized)["data"] == {"servers": rows}
    assert len(extract_mcp_server_targets(server_config=normalized)) == 2


@pytest.mark.parametrize(
    "selection", [{"gatewayId": ["g1"]}, {"gatewayName": ["Production"]}]
)
def test_gateway_summaries_cannot_satisfy_selected_gateway_routes(selection):
    body = envelope([entry()], gateways=[{"gatewayId": "g1", "name": "Production"}])
    with pytest.raises(AgentError, match="gateway"):
        normalize_inventory_response(body, selection)


@pytest.mark.parametrize(
    "summaries",
    [
        None,
        {},
        "metadata",
        [None],
        [{}],
        [{"gatewayId": "g1"}],
        [{"gatewayId": "", "name": "Production"}],
        [{"gatewayId": "g1", "name": 123}],
        [{"gatewayId": "g1", "name": "Production", "members": ["mail"]}],
        [
            {
                "gatewayId": "g1",
                "name": "Production",
                "config": {"url": "https://remote.invalid/${HOST_SECRET}"},
            }
        ],
    ],
)
def test_gateway_summary_extensions_are_rejected_without_guessing_endpoints(summaries):
    with pytest.raises(AgentError, match="gateway summaries") as error:
        normalize_inventory_response(envelope([entry()], gateways=summaries))
    assert "HOST_SECRET" not in str(error.value)


@pytest.mark.parametrize(
    "body",
    [
        "{}",
        "[]",
        '{"succeeded":false,"message":"secret"}',
        envelope([entry(), entry(config2={})]),
        envelope([{"name": "bad", "transport": "http"}]),
    ],
)
def test_invalid_response_is_rejected_without_body(body):
    with pytest.raises(AgentError) as error:
        normalize_inventory_response(body)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "row",
    [
        {"name": "command", "config": {"command": "sh", "args": ["-c", "echo unsafe"]}},
        {"name": "command", "stdio": {"command": "sh"}},
        {"name": "command", "transport": "stdio", "config": {"command": "sh"}},
        {"name": "command", "transport": "stdio", "stdio": {"command": "sh"}},
        {"name": "command", "transport": None, "config": {"command": "sh"}},
    ],
)
def test_remote_local_command_and_implicit_transports_are_rejected(row):
    with pytest.raises(AgentError, match="explicit network transport"):
        normalize_inventory_response(envelope([row]))


@pytest.mark.parametrize("transport", NETWORK_TRANSPORTS)
def test_explicit_network_transports_keep_literal_endpoint_and_headers(transport):
    row = entry()
    row["transport"] = transport
    if transport in ("websocket", "ws"):
        row["config"]["url"] = "wss://example/mcp"
    row["config"]["headers"] = {"Authorization": "Bearer literal-token"}
    normalized = json.loads(normalize_inventory_response(envelope([row])))
    assert normalized["data"]["servers"] == [row]


@pytest.mark.parametrize("transport", NETWORK_TRANSPORTS)
@pytest.mark.parametrize("field", ["url", "headers"])
def test_remote_environment_references_are_rejected_without_reading_or_leaking_host_values(
    monkeypatch, transport, field
):
    key = "INVENTORY_FIXTURE_SECRET"
    secret = "host-secret-must-not-be-forwarded"
    monkeypatch.setenv(key, secret)
    row = entry()
    row["transport"] = transport
    if field == "url":
        row["config"]["url"] = "https://remote.invalid/?secret=${" + key + "}"
    else:
        row["config"]["headers"] = {"Authorization": "${" + key + "}"}
    with pytest.raises(
        AgentError, match="must not contain environment variable references"
    ) as error:
        normalize_inventory_response(envelope([row]))
    assert key not in str(error.value)
    assert secret not in str(error.value)


@pytest.mark.parametrize("field", ["url", "headers"])
@pytest.mark.parametrize(
    "fallback, transport",
    [("http_sse", "http"), ("streamable_http", "http"), ("websocket", "ws")],
)
def test_effective_fallback_environment_references_are_rejected(
    fallback, transport, field
):
    config = {"url": "https://example/mcp"}
    if field == "url":
        config["url"] += "/${UNSET_INVENTORY_SECRET}"
    else:
        config["headers"] = {"Authorization": "${UNSET_INVENTORY_SECRET}"}
    row = {"name": "fallback", "transport": transport, fallback: config}
    with pytest.raises(
        AgentError, match="must not contain environment variable references"
    ):
        normalize_inventory_response(envelope([row]))


def test_registry_base_url_reference_is_rejected_before_native_expansion(monkeypatch):
    monkeypatch.setenv("MCP_BASE_URL", "https://host-secret.invalid")
    with pytest.raises(
        AgentError, match="must not contain environment variable references"
    ):
        normalize_inventory_response(envelope([entry()], base_url="${MCP_BASE_URL}"))


@pytest.mark.parametrize(
    "field, value",
    [
        ("tools", [{"rest": {"url": "https://remote.invalid/${HOST_SECRET}"}}]),
        ("default_headers", {"Authorization": "${HOST_SECRET}"}),
        ("auth_presets", {"remote": {"value": "${HOST_SECRET}"}}),
        ("mcp_servers", [{"name": "command", "stdio": {"command": "sh"}}]),
    ],
)
def test_unvalidated_registry_collections_cannot_bypass_inventory_validation(
    field, value
):
    with pytest.raises(AgentError, match="Unsupported non-empty inventory collection"):
        normalize_inventory_response(envelope([entry()], **{field: value}))


def test_descriptive_literals_and_unused_fallbacks_are_preserved():
    reference = "${DOCUMENTATION_EXAMPLE}"
    row = entry(id=reference)
    row["name"] = "Example " + reference
    row["description"] = reference
    row["metadata"] = {reference: reference}
    row["config"]["headers"] = {reference: "literal-value"}
    row["config"]["extra"] = {"description": reference}
    row["http_sse"] = {
        "url": "https://unused.invalid/" + reference,
        "headers": {"Authorization": reference},
    }
    body = envelope([row], description=reference)
    normalized = json.loads(normalize_inventory_response(body))
    assert normalized["data"]["servers"] == [row]
    assert normalized["data"]["description"] == reference
    assert (
        extract_mcp_server_targets(server_config=json.dumps(normalized))[0]["url"]
        == row["config"]["url"]
    )
