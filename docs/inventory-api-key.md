# Multiple MCP sources with an API key

This guide describes the unreleased SDK in this checkout.

API-key factories can select multiple servers and remote gateways in one call:

```python
from gopher_mcp_python import GopherAgent, GopherAgentCreateOptions

options = GopherAgentCreateOptions(
    server_ids=["mail", "calendar"],
    gateway_names=["Production"],
)
agent = GopherAgent.create_with_api_key(provider, model, api_key, options)
try:
    print(agent.run("List my available tools"))
finally:
    agent.dispose()
```

Use your provider and model values and its LLM credentials. `api_key` is the
Gopher project key used for inventory access. MCP authorization uses each
source's configured credentials or OAuth grant.

## Selection and the inventory request

| Python option | JSON request field |
| --- | --- |
| `server_ids` | `serverId` |
| `server_names` | `serverName` |
| `gateway_ids` | `gatewayId` |
| `gateway_names` | `gatewayName` |

Options accept lists of nonblank strings. Exact values, case, whitespace,
and order are preserved; repeated strings are removed. Mappings can use the
Python option names or JSON field names. `GopherSourceSelection(...)` is also
accepted by `GopherAgentCreateOptions(source_selection=...)`.

The positional ID/name in `create_with_server_id`, `create_with_server_name`,
`create_with_gateway_id`, and `create_with_gateway_name` is prepended to its
array. Other supplied selectors remain additive. For example:

```python
agent = GopherAgent.create_with_server_id(
    provider, model, api_key, "mail",
    {"server_ids": ["calendar", "mail"], "gateway_names": ["Production"]},
)
```

This sends one authenticated `POST /v1/mcp-servers` with this JSON body:

```json
{"serverId":["mail","calendar"],"serverName":[],"gatewayId":[],"gatewayName":["Production"]}
```

All four empty arrays select all sources the key is authorized to use.
`GOPHER_SDK_TEST=true` selects `https://api-test.gopher.security`; the default
is `https://api.gopher.security`. The inventory request rejects redirects and
has a 30-second transport/body-read budget. HTTP/backend errors omit response
bodies and credentials.

The backend's successful `data.servers` array defines the inventory. Python
validates it and passes it to native JSON creation without another inventory
fetch, including when explicit MCP credentials or disabled OAuth are supplied.
Gateways stay remote MCP endpoints; their backing servers remain managed by
the gateway. Exact duplicate entries are collapsed, conflicting runtime names
are rejected, and source config/headers are preserved. URL and inline JSON
factories reject inventory selectors.

When gateway selectors are present, every requested gateway must appear as a
remote route whose decoded URL path is `/v1/mcp/gateways/<id>/mcp` or
`/v1/mcp/gateways/<id>/sse` (an optional trailing slash is accepted). Query
strings, fragments, and `type: gateway` metadata cannot make a backing-server
URL qualify as a gateway. Gateway-only results must contain selected gateway
routes. Mixed selections may also include explicitly selected servers; other
returned sources cause the entire response to be rejected before OAuth or
native creation.

Python intentionally rejects distinct entries sharing a runtime name, even when
their IDs differ. Native gopher-orch v0.1.45 instead generates `name__id` aliases
for such collisions. Python keeps the API's names unchanged for runtime option
matching; select nonconflicting routes or assign unique names in the backend.
Exact duplicate entries are still collapsed.

Remote inventory requires an explicit HTTP or WebSocket transport. It rejects
stdio entries and `${VAR}` references in effective endpoint URLs, header values,
and the registry `base_url`, before OAuth discovery or native creation. These
references are rejected because the native loader also expands them. Unsupported
non-empty registry collections are rejected so they cannot bypass source
validation. Literal placeholders in descriptions and unused fallback configs
are preserved. Caller-supplied inline JSON keeps its existing stdio and
environment-substitution behavior.

## Independent OAuth grants

Public sources and a single compatible OAuth binding keep the existing Python
OAuth/JSON creation path. When automatic discovery finds multiple distinct
OAuth bindings, Python uses native embedded authorization interface v1. Native
code owns discovery, PKCE, registrations, per-source grants, refresh, and the
local authorization page. Python presents that page and services host callbacks.
A shared issuer with different resources still needs distinct grants.

For several missing grants, complete the connections on the local page and
choose Continue. Already cached grants can avoid presenting a page. Finishing
MCP authorization preserves the existing provider elicitation handler, which
can still run during tool discovery and execution.

Pass `oauth={"mode": "disabled"}` or explicit runtime `access_token` /
`Authorization` to skip automatic OAuth. These options retain their existing
global credential semantics. Source-specific credentials can live in each
inventory entry's `config.headers` or runtime `server_options`:

```python
options = GopherAgentCreateOptions(
    server_ids=["mail", "calendar"],
    server_options=[{"server_name": "mail", "access_token": mail_token}],
)
```

Each `server_options` entry selects a source by `server_id`, `server_name`, or
`url` and accepts `access_token` and `headers`. Selectors match additively; use a
unique runtime name to target a source when URLs overlap. Automatically acquired
single-binding tokens are scoped to protected sources, preserving public sources
and existing credentials on other entries.

`oauth.assemble` accepts these Python settings for the native path:

| Setting | Behavior |
| --- | --- |
| `on_authorization_url(url, flow)` | Optional sync/async page presenter; `flow` is `single` or `assemble`. Defaults to opening a browser. |
| `on_progress(rows)` | Optional sync/async callback receiving only `{source, state}` entries. |
| `identity_namespace` | Stable nonblank application/user identity; required with a custom token store. Otherwise a fresh per-creation identity is used. |
| `cancel_event` | Event with `is_set()`; cancels pending authorization/creation. |
| `timeout_ms` | Human authorization budget, default 600000; range 100–1800000. |
| `network_timeout_ms` | Native network request budget, default 10000; range 100–30000. |
| `discovery_timeout_ms` | Native discovery budget, default 30000; range 100–120000. |
| `clients` | Source ID/name to client settings: `client_id`, optional `client_secret`, `token_endpoint_auth_method` (`none` or `client_secret_post`), and `scopes`. |
| `allow_loopback_http` | Default false. Enable only for local HTTP OAuth fixtures. |

The host also bounds creation, including unfinished callbacks, by the sum of
the three budgets. Callbacks should finish or cooperate with cancellation.
With `oauth.open_browser=False`, supply a page presenter; missing/failed browser
presentation raises `AUTH_PRESENTATION_REQUIRED`. Treat the local page URL as a
private capability: deliver it to the intended user's UI and keep it out of logs.

## Async applications and custom token stores

Each synchronous factory has an async counterpart named `create_*_async`;
`create_async(config)` supports the config builder. Native calls execute off
the application event loop. For example:

```python
agent = await GopherAgent.create_with_api_key_async(
    provider, model, api_key,
    {"server_ids": ["mail", "calendar"], "oauth": {
        "token_store": store,
        "assemble": {"identity_namespace": user_id},
    }},
)
try:
    answer = await agent.run_async("List my available tools")
finally:
    await agent.dispose_async()
```

A native host thread polls custom-store requests throughout the agent lifetime,
including refresh during queries. Async stores/presenters used by native
assembly run on the async factory's caller loop. Keep that loop running and use
`run_async()` there. Synchronous creation uses the host thread's loop for native
store callbacks. Existing single-binding Python OAuth retains its token-store
thread/loop contract described in [Threading and ownership](threading-and-ownership.md).
Provider elicitation handlers retain their existing synchronous callback contract.

Custom stores implement async `get`, `set`, and `delete`. Persist
`GopherAgentTokenRecord.embedded_grant` intact; native grant expiry uses seconds,
while the record's `expires_at` uses milliseconds. Keys are bound to identity,
source, issuer, resource, scopes, and client identity. These privileged records
can include refresh tokens and client secrets and belong in protected storage.

An agent still permits one active query. Cancelling `run_async()` leaves the
native call running and retains resources until it exits. Disposal stops new
queries; `dispose_async()` waits for any active call, native release, and host
shutdown. Cancelling an async factory cancels unfinished authorization and
releases a late native result.

## Native compatibility and verification

The submodule is pinned to `gopher-orch` v0.1.45 at commit `ac84f1b3` with embedded
authorization v1. The publishing workflow downloads v0.1.45 native artifacts
for every supported platform. A version string alone does not establish
compatibility: older binaries with the same label can lack the interface.
Multiple independent OAuth flows fail with `EMBEDDED_AUTH_UNAVAILABLE` when
the loaded binary lacks v1;
legacy creation continues to work.

After installing the local Python package, check the actual artifact:

```bash
GOPHER_ORCH_LIBRARY_PATH=/absolute/path/to/libgopher-orch.dylib \
  python3 scripts/check-embedded-auth-native.py
```

Run shared conformance, host lifecycle, and actual native integration tests:

```bash
python3 -m pytest tests/test_inventory_conformance.py tests/test_embedded_auth*.py
GOPHER_EMBEDDED_AUTH_TEST_LIBRARY=/absolute/path/to/libgopher-orch.dylib \
  python3 -m pytest tests/test_embedded_auth_native.py
```

The native suite uses local OAuth/MCP fixtures and dummy LLM credentials. It
checks native agent handoff and cached grant refresh without querying a live LLM.
It covers separate issuers, shared issuers with separate resources, concurrent
identities, cancellation, store failure, provider elicitation, and single-grant
isolation from public sources. The ordinary
suite skips these native checks unless the artifact path is supplied. OAuth CI
runs shared inventory and host contracts on Linux and macOS; native artifact
checks should also pass before publishing platform packages.

These tests verify the local SDK/native contract. Confirm deployed inventory
POST access and selector resolution with an authorized backend before rollout.
