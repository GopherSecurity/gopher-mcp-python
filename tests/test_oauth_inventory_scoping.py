"""Keep legacy single-binding OAuth credentials confined to their sources."""

import asyncio
import ctypes
import json
from types import SimpleNamespace

import pytest

import gopher_mcp_python.oauth_resolver as resolver
from gopher_mcp_python import (
    GopherAgentConfig,
    GopherAgentCreateOptions,
    GopherAgentRuntimeOptions,
)
from gopher_mcp_python.ffi.library import (
    GopherOrchLibrary,
    GopherOrchServerAgentOptions,
)
from gopher_mcp_python.oauth_discovery import (
    McpOAuthChallenge,
    OAuthProtectedResourceMetadata,
)
from gopher_mcp_python.runtime_options import (
    normalize_create_options,
    normalize_runtime_options,
)


def config(names):
    return json.dumps(
        {
            "servers": [
                {
                    "name": name,
                    "transport": "http",
                    "config": {"url": "https://" + name + ".example/mcp"},
                }
                for name in names
            ]
        }
    )


def test_grant_is_scoped_to_protected_source_and_keeps_explicit_credentials(
    monkeypatch,
):
    async def probe(url):
        return McpOAuthChallenge(
            url=url,
            http_status=401 if "protected" in url else 200,
            requires_oauth="protected" in url,
        )

    async def acquire(*args):
        return GopherAgentRuntimeOptions(access_token="oauth-token")

    monkeypatch.setattr(resolver, "_probe_challenge", probe)
    monkeypatch.setattr(resolver, "_acquire_token", acquire)
    base = GopherAgentRuntimeOptions(
        headers={"X-Tenant": "tenant"},
        server_options=[{"server_name": "keyed", "access_token": "configured"}],
    )
    result = asyncio.run(
        resolver.resolve_runtime_options_with_oauth(
            server_config=config(["protected", "public", "keyed"]),
            runtime_options=base,
            defer_multiple_oauth=True,
        )
    )
    assert result.access_token is None
    assert result.headers == {"X-Tenant": "tenant"}
    assert result.server_options == [
        {
            "server_name": "keyed",
            "access_token": "configured",
            "headers": {"Authorization": "Bearer configured"},
        },
        {
            "server_name": "protected",
            "access_token": "oauth-token",
            "headers": {"Authorization": "Bearer oauth-token"},
        },
    ]


def test_equivalent_metadata_bindings_keep_legacy_acquisition(monkeypatch):
    async def probe(url):
        return McpOAuthChallenge(
            url=url,
            requires_oauth=True,
            http_status=401,
            resource_metadata_url=url + "/metadata",
        )

    async def acquire(challenges, oauth):
        assert {c.resource for c in challenges} == {"https://canonical.example/mcp"}
        return GopherAgentRuntimeOptions(access_token="equivalent")

    monkeypatch.setattr(resolver, "_probe_challenge", probe)
    monkeypatch.setattr(resolver, "_acquire_token", acquire)
    monkeypatch.setattr(
        resolver,
        "fetch_oauth_protected_resource_metadata",
        lambda url: OAuthProtectedResourceMetadata(
            "https://canonical.example/mcp", ["https://issuer.example"], ["read"], "{}"
        ),
    )
    result = asyncio.run(
        resolver.resolve_runtime_options_with_oauth(
            server_config=config(["one", "two"]), defer_multiple_oauth=True
        )
    )
    assert result.access_token is None
    assert len(result.server_options) == 2
    with pytest.raises(resolver.MultipleMcpOAuthRequired):
        asyncio.run(
            resolver.resolve_runtime_options_with_oauth(
                server_config=config(["one", "two"]),
                oauth={"assemble": {"clients": {"one": {"client_id": "custom"}}}},
                defer_multiple_oauth=True,
            )
        )


def test_runtime_headers_and_matching_source_credentials_reach_probes(monkeypatch):
    calls = []

    def probe(url, headers=None):
        calls.append(headers)
        return McpOAuthChallenge(url=url, http_status=200, requires_oauth=False)

    monkeypatch.setattr(resolver, "probe_mcp_oauth_challenge", probe)
    options = GopherAgentRuntimeOptions(
        headers={"X-Tenant": "global"},
        server_options=[{"server_name": "one", "access_token": "one-only"}],
    )
    asyncio.run(
        resolver.resolve_runtime_options_with_oauth(
            server_config=config(["one", "two"]), runtime_options=options
        )
    )
    assert calls == [
        {"X-Tenant": "global", "Authorization": "Bearer one-only"},
        {"X-Tenant": "global"},
    ]


def test_server_options_survive_normalization_builder_and_native_storage():
    options = GopherAgentCreateOptions(
        server_ids=["one"],
        server_options=[
            {
                "server_name": "one",
                "access_token": "one-only",
                "headers": {"X-Source": "yes"},
            }
        ],
    )
    config = (
        GopherAgentConfig.builder()
        .provider("p")
        .model("m")
        .api_key("key")
        .runtime_options(options)
        .headers({"X-Global": "yes"})
        .build()
    )
    runtime = normalize_runtime_options(config.runtime_options)
    assert normalize_create_options(runtime).server_options == options.server_options
    library = object.__new__(GopherOrchLibrary)
    library._supports_elicitation_callback_options = lambda: True
    storage = library._build_agent_options(runtime)
    raw = storage.options
    assert raw.server_option_count == 1
    server = ctypes.cast(
        raw.server_options, ctypes.POINTER(GopherOrchServerAgentOptions)
    )[0]
    assert server.server_name == b"one"
    assert server.access_token == b"one-only"
    assert {
        server.headers[i].name: server.headers[i].value
        for i in range(server.header_count)
    } == {b"X-Source": b"yes", b"Authorization": b"Bearer one-only"}
    assert options.server_options[0]["access_token"] == "one-only"


@pytest.mark.parametrize(
    "options",
    [
        {},
        "",
        [{"headers": {}}],
        [{"server_name": "one", "unknown": "no"}],
        [{"url": "x\0y"}],
    ],
)
def test_invalid_source_runtime_options_fail_before_normalizing_to_empty(options):
    with pytest.raises(ValueError):
        normalize_runtime_options({"server_options": options})
    with pytest.raises(ValueError):
        normalize_create_options({"server_options": options})
