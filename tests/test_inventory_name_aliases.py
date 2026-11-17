"""Mirror native inventory name collision handling without changing source bindings."""

import asyncio
from itertools import permutations
import json

import pytest

import gopher_mcp_python.agent as agent_module
import gopher_mcp_python.oauth_resolver as oauth_resolver
import gopher_mcp_python.server_config as transport
from gopher_mcp_python import AgentError, GopherAgent, GopherAgentRuntimeOptions
from gopher_mcp_python.inventory_response import normalize_inventory_response
from gopher_mcp_python.oauth_discovery import McpOAuthChallenge
from gopher_mcp_python.oauth_server_targets import extract_mcp_server_targets


def source(name, identifier, kind="servers"):
    return {
        "name": name,
        "id": identifier,
        "transport": "http",
        "config": {
            "url": f"https://mcp.example/v1/mcp/{kind}/endpoint/mcp",
            "headers": {"Authorization": f"Bearer fixture-{identifier}"},
        },
    }


def envelope(rows):
    return json.dumps({"succeeded": True, "data": {"servers": rows}})


def normalize(rows, selection=None):
    return json.loads(normalize_inventory_response(envelope(rows), selection))["data"][
        "servers"
    ]


def test_collision_aliases_change_only_names_and_collapse_exact_duplicates():
    direct, gateway, unrelated = (
        source("Shared", "s1"),
        source("Shared", "g1", "gateways"),
        source("Unchanged", "other"),
    )
    rows = normalize([direct, gateway, gateway, unrelated])
    assert [row["name"] for row in rows] == ["Shared__s1", "Shared__g1", "Unchanged"]
    assert rows[:2] == [
        dict(direct, name="Shared__s1"),
        dict(gateway, name="Shared__g1"),
    ]
    assert rows[2] == unrelated
    targets = extract_mcp_server_targets(server_config=envelope(rows))
    assert [target["server_id"] for target in targets] == ["s1", "g1", "other"]
    assert [target["headers"] for target in targets] == [
        row["config"]["headers"] for row in rows
    ]


def test_aliases_are_stable_across_response_order_and_revalidation():
    a, b, reserved = (
        source("Shared", "a"),
        source("Shared", "a_", "gateways"),
        source("Shared__a", "c"),
    )
    expected = {"a": "Shared__a_", "a_": "Shared__a__", "c": "Shared__a"}
    for ordered in permutations([a, b, reserved]):
        normalized = normalize(ordered)
        assert {row["id"]: row["name"] for row in normalized} == expected
        assert normalize(normalized) == normalized


@pytest.mark.parametrize("field", ["id", "serverId", "server_id"])
def test_alias_suffix_uses_native_identity_precedence(field):
    a, b = source("Shared", "a"), source("Shared", "b")
    del a["id"]
    a[field] = "chosen"
    if field == "id":
        a["serverId"] = "ignored"
    if field != "server_id":
        a["server_id"] = "ignored-too"
    assert [row["name"] for row in normalize([a, b])] == ["Shared__chosen", "Shared__b"]


@pytest.mark.parametrize(
    "identifier, expected",
    [
        ("a/b ?#%", "a%2Fb%20%3F%23%25"),
        ("é+值", "%C3%A9%2B%E5%80%BC"),
        ("A-z_09.~", "A-z_09.~"),
    ],
)
def test_alias_suffix_uses_native_percent_encoding(identifier, expected):
    original = source("Shared", identifier)
    assert normalize([original, source("Shared", "other")])[0] == dict(
        original, name="Shared__" + expected
    )


@pytest.mark.parametrize(
    "identity", [{}, {"id": ""}, {"id": "", "serverId": "ignored"}, {"id": "same"}]
)
def test_ambiguous_collisions_fail_without_echoing_private_source_details(identity):
    a = source("Shared", "same")
    b = source("Shared", "different", "gateways")
    del b["id"]
    b.update(identity)
    with pytest.raises(AgentError, match="distinct nonempty IDs") as error:
        normalize([a, b])
    assert "fixture-" not in str(error.value)
    assert "https://" not in str(error.value)


def test_unique_names_are_unchanged_even_without_ids():
    a, b = source("First", "a"), source("Second", "b")
    del a["id"]
    assert normalize([a, a, b]) == [a, b]


def test_gateway_selection_uses_original_names_before_aliases():
    gateways = [source("Shared", "g1", "gateways"), source("Shared", "g2", "gateways")]
    rows = normalize(gateways, {"gatewayName": ["Shared"], "gatewayId": ["g1", "g2"]})
    assert [row["name"] for row in rows] == ["Shared__g1", "Shared__g2"]
    with pytest.raises(AgentError, match="gateway"):
        normalize(gateways, {"gatewayName": ["Shared__g1"]})


def test_name_aliasing_cannot_hide_backing_server_substitution():
    gateway, direct = source("Shared", "g1", "gateways"), source("Shared", "s1")
    with pytest.raises(AgentError, match="gateway selection"):
        normalize([gateway, direct], {"gatewayName": ["Shared"]})
    rows = normalize([gateway, direct], {"gatewayName": ["Shared"], "serverId": ["s1"]})
    assert [row["name"] for row in rows] == ["Shared__g1", "Shared__s1"]


def test_legacy_oauth_grant_targets_only_the_aliased_protected_source(monkeypatch):
    protected, public = source("Shared", "protected"), source("Shared", "public")
    protected["config"]["url"] = "https://protected.example/mcp"
    public["config"]["url"] = "https://public.example/mcp"
    config = envelope(normalize([protected, public]))

    async def probe(url):
        requires = "protected" in url
        return McpOAuthChallenge(
            url=url, requires_oauth=requires, http_status=401 if requires else 200
        )

    async def acquire(*args):
        return GopherAgentRuntimeOptions(access_token="protected-token")

    monkeypatch.setattr(oauth_resolver, "_probe_challenge", probe)
    monkeypatch.setattr(oauth_resolver, "_acquire_token", acquire)
    result = asyncio.run(
        oauth_resolver.resolve_runtime_options_with_oauth(
            server_config=config, defer_multiple_oauth=True
        )
    )
    assert result.access_token is None
    assert result.server_options == [
        {
            "server_name": "Shared__protected",
            "access_token": "protected-token",
            "headers": {"Authorization": "Bearer protected-token"},
        }
    ]
    assert json.loads(config)["data"]["servers"][1]["config"] == public["config"]


def test_api_factory_passes_aliased_names_and_unchanged_routes_to_native_once(
    monkeypatch,
):
    sources = [source("Shared", "a"), source("Shared", "b")]
    requests, created = [], []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return envelope(sources).encode()

    def request(req, timeout):
        requests.append(req)
        return Response()

    class Library:
        def agent_create_by_json(self, provider, model, config, options):
            created.append(json.loads(config)["data"]["servers"])
            return 123

        def agent_release(self, handle):
            pass

    monkeypatch.setattr(transport, "urlopen", request)
    monkeypatch.setattr(
        agent_module.GopherOrchLibrary, "get_instance", lambda: Library()
    )
    agent = GopherAgent.create_with_api_key(
        "provider", "model", "project-key", {"oauth": {"mode": "disabled"}}
    )
    try:
        assert len(requests) == len(created) == 1
        assert created[0] == [
            dict(sources[0], name="Shared__a"),
            dict(sources[1], name="Shared__b"),
        ]
    finally:
        agent.dispose()
