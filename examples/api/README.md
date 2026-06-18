# examples/api — Python SDK examples for the seven `create_by_*` factories

This directory holds the Python siblings of the C++ SDK examples under
[`gopher-orch/examples/sdk/api/`](../../third_party/gopher-orch/examples/sdk/api/)
and the TypeScript siblings under
[`gopher-mcp-js/examples/api/`](https://github.com/GopherSecurity/gopher-mcp-js/tree/main/examples/api).
Each `.py` file mirrors its `.cc` and `.ts` counterparts one-to-one
and exercises exactly one of the seven `create_by_*` factories the
SDK exposes through `GopherAgent`.

All examples in this directory resolve their dependencies from the
**PyPI-published** [`gopher-mcp-python`](https://pypi.org/project/gopher-mcp-python/)
package and its matching platform-specific native package — they do
not use the in-tree `gopher_mcp_python/` source or the locally-built
`native/lib/` directory. To work against the in-tree source instead,
see the existing `examples/client_example_json*` pair at the
`examples/` root.

## File-to-factory mapping

| C++ reference                  | Python port                    | TypeScript port                | `GopherAgent` factory          |
| ------------------------------ | ------------------------------ | ------------------------------ | ------------------------------ |
| `create_by_api_key.cc`         | `create_by_api_key.py`         | `create_by_api_key.ts`         | `create_with_api_key`          |
| `create_by_json.cc`            | `create_by_json.py`            | `create_by_json.ts`            | `create_with_server_config`    |
| `create_by_server_id.cc`       | `create_by_server_id.py`       | `create_by_server_id.ts`       | `create_with_server_id`        |
| `create_by_server_name.cc`     | `create_by_server_name.py`     | `create_by_server_name.ts`     | `create_with_server_name`      |
| `create_by_gateway_id.cc`      | `create_by_gateway_id.py`      | `create_by_gateway_id.ts`      | `create_with_gateway_id`       |
| `create_by_gateway_name.cc`    | `create_by_gateway_name.py`    | `create_by_gateway_name.ts`    | `create_with_gateway_name`     |
| `create_by_url.cc`             | `create_by_url.py`             | `create_by_url.ts`             | `create_with_url`              |

Each `.py` file ships with a `*_run.sh` wrapper that bootstraps a
fresh virtual environment, installs `gopher-mcp-python` plus the
matching platform native package from PyPI, and forwards positional
arguments to the example as queries.

## Quick start

1. Set the env vars your chosen example needs (see the matrix below).
   At minimum every example needs `LLM_MODEL` and the LLM
   provider's own credentials (`ANTHROPIC_API_KEY` for the default
   `AnthropicProvider`):

   ```sh
   export LLM_MODEL=<your-model-id>
   export ANTHROPIC_API_KEY=...
   export GOPHER_API_KEY=...            # only if your variant needs it
   ```

2. Run the wrapper. It will detect your platform, create
   `examples/api/test-project-<variant>/` with a fresh venv inside,
   `pip install gopher-mcp-python` plus the matching native package
   from PyPI, then run the `.py`:

   ```sh
   ./examples/api/create_by_api_key_run.sh "What time is it in Tokyo?"
   ```

   Positional arguments to the wrapper become queries; with no
   arguments each example runs a canned query so a first invocation
   produces visible output.

3. To pin a specific SDK version, set `SDK_VERSION` before invoking
   a wrapper. Otherwise the latest published version is installed:

   ```sh
   SDK_VERSION=0.1.23 ./examples/api/create_by_server_id_run.sh
   ```

The wrappers are idempotent: each run nukes its `test-project-*`
directory and rebuilds the venv from scratch so a stale install
cannot mask a problem. The `test-project-*` directories are
intentionally ignored by `.gitignore` at the repo root.

## Manual run (no wrapper)

If you would rather drive the venv yourself, the `.py` files are
self-contained and run against any environment that has
`gopher-mcp-python` and the matching native package installed:

```sh
python3 -m venv venv
source venv/bin/activate
pip install gopher-mcp-python gopher-mcp-python-native-darwin-arm64
export LLM_MODEL=<your-model-id>
export ANTHROPIC_API_KEY=...
python examples/api/create_by_api_key.py "What time is it in Tokyo?"
```

Substitute the right native package name for your platform; see the
list at [pypi.org/project/gopher-mcp-python](https://pypi.org/project/gopher-mcp-python/).

## Environment variables per example

| Example                  | Required                                                   | Optional                |
| ------------------------ | ---------------------------------------------------------- | ----------------------- |
| `create_by_api_key`      | `GOPHER_API_KEY`, `LLM_MODEL`                              | `LLM_PROVIDER`, `DEBUG` |
| `create_by_json`         | `LLM_MODEL`                                                | `LLM_PROVIDER`, `DEBUG` |
| `create_by_server_id`    | `GOPHER_API_KEY`, `GOPHER_MCP_SERVER_ID`, `LLM_MODEL`      | `LLM_PROVIDER`, `DEBUG` |
| `create_by_server_name`  | `GOPHER_API_KEY`, `GOPHER_MCP_SERVER_NAME`, `LLM_MODEL`    | `LLM_PROVIDER`, `DEBUG` |
| `create_by_gateway_id`   | `GOPHER_API_KEY`, `GOPHER_MCP_GATEWAY_ID`, `LLM_MODEL`     | `LLM_PROVIDER`, `DEBUG` |
| `create_by_gateway_name` | `GOPHER_API_KEY`, `GOPHER_MCP_GATEWAY_NAME`, `LLM_MODEL`   | `LLM_PROVIDER`, `DEBUG` |
| `create_by_url`          | `GOPHER_MCP_URL`, `LLM_MODEL`                              | `LLM_PROVIDER`, `DEBUG` |

The wrappers also recognise:

- `SDK_VERSION` — pin `gopher-mcp-python` and the platform native
  package to a specific PyPI version. Defaults to the latest.
- `ANTHROPIC_API_KEY` — required by the default `AnthropicProvider`;
  the wrappers warn if unset but do not fail.

Notes:

- `LLM_PROVIDER` defaults to `AnthropicProvider` in every example.
- `LLM_MODEL` has no default; each example refuses to start until
  the variable is set rather than calling into the FFI with a
  placeholder. This matches the env-var-required path the JS side
  picked so the examples never surface a stale or fictional model
  identifier.

## Picking the right factory

| Factory                       | Selects                                                         | Network call                                       |
| ----------------------------- | --------------------------------------------------------------- | -------------------------------------------------- |
| `create_with_api_key`         | Every MCP server the api key owns                               | `GET /v1/mcp-servers`                              |
| `create_with_server_config`   | Servers described in an inline JSON document                    | None                                               |
| `create_with_server_id`       | One MCP server by id                                            | `GET /v1/mcp-servers?serverId=...`                 |
| `create_with_server_name`     | One MCP server by name                                          | `GET /v1/mcp-servers?serverName=...`               |
| `create_with_gateway_id`      | All MCP servers under one gateway by id                         | `GET /v1/mcp-servers?gatewayId=...`                |
| `create_with_gateway_name`    | All MCP servers under one gateway by name                       | `GET /v1/mcp-servers?gatewayName=...`              |
| `create_with_url`             | One MCP server reachable at a known URL                         | None (synthesised locally to an `http_sse` entry)  |

The table mirrors the C++ canonical reference at
`gopher-orch/docs/Agent.md` ("Simple creation factories" section)
so the Python-side documentation stays aligned with the upstream
C++ docs and the TypeScript port.

The five routing factories
(`create_with_server_id` / `_server_name` / `_gateway_id` /
`_gateway_name` / `_url`) require `gopher-mcp-python` ≥ 0.1.23 on
PyPI. Earlier versions only expose `create_with_api_key` and
`create_with_server_config`.

## How the examples find the SDK

Each `.py` file imports `GopherAgent` from the
`gopher_mcp_python` package installed by the wrapper:

```python
from gopher_mcp_python import GopherAgent
```

Resolution flow:

- Through a wrapper (`create_by_*_run.sh`): the wrapper creates a
  fresh venv in `examples/api/test-project-<variant>/`,
  `pip install`-s `gopher-mcp-python` plus the matching platform
  native package from PyPI, then runs the example. The import
  resolves against the just-installed PyPI package, never against
  the in-tree `gopher_mcp_python/` source.
- Manual run: the example resolves against whatever
  `gopher_mcp_python` is on the active Python's `sys.path` —
  whatever you `pip install`-ed into your own venv.

A downstream consumer copying any of these examples into their own
project does not need to edit the import path — the same `from
gopher_mcp_python import GopherAgent` line works as long as the
package is installed.

## How the wrappers find the native library

The native `libgopher-orch.dylib` / `.so` / `.dll` is loaded by the
`ctypes` layer inside `gopher_mcp_python.ffi.library`. With the
PyPI-based wrappers, resolution happens entirely inside the venv:

1. The wrapper installs `gopher-mcp-python-native-<platform>-<arch>`
   alongside the main package; that package ships the native binary
   under its own `lib/` directory.
2. `gopher_mcp_python/ffi/library.py` walks `sys.path` looking for
   the matching `gopher_mcp_python_native_*` package and uses its
   `get_lib_path()` to locate the dylib.
3. `DYLD_LIBRARY_PATH` / `LD_LIBRARY_PATH` are **not** set by the
   wrappers — the loader finds the platform package via Python
   import semantics rather than a search path.

If you need to point at a different library location entirely
(for example a locally-built `libgopher-orch.dylib` for testing a
patch), set `GOPHER_MCP_PYTHON_LIBRARY_PATH` before invoking the
wrapper. That env var is checked first by
`gopher_mcp_python/ffi/library.py` and bypasses the platform-package
resolution step.

## Troubleshooting

### "Failed to load gopher-mcp-python library"

The matching platform native package was not installed. The
wrappers compute and install it automatically; if you are running
the `.py` manually, install both:

```sh
pip install gopher-mcp-python gopher-mcp-python-native-<platform>-<arch>
```

### Permission errors on macOS

Quarantine flags on a freshly-downloaded dylib can block load:

```sh
xattr -d com.apple.quarantine "$(python -c 'import gopher_mcp_python_native_darwin_arm64 as n; print(n.get_library_file())')"
```

### Routing factory raises `AgentError` against an older PyPI release

The five routing factories landed in `gopher-mcp-python` 0.1.23. If
the wrapper installs an older version, the higher-level factory
raises `AgentError` because the underlying C symbol is missing. Pin
to a recent release:

```sh
SDK_VERSION=0.1.23 ./examples/api/create_by_server_id_run.sh
```

## Cross-reference

- C++ canonical examples:
  `gopher-orch/examples/sdk/api/` (in the `third_party/gopher-orch`
  submodule of this repo).
- C++ canonical docs:
  `gopher-orch/docs/Agent.md` ("Simple creation factories"
  section).
- TypeScript siblings:
  [`gopher-mcp-js/examples/api/`](https://github.com/GopherSecurity/gopher-mcp-js/tree/main/examples/api).
- FFI binding layer:
  `gopher_mcp_python/ffi/library.py` (`agent_create_by_*` methods).
- High-level wrappers:
  `gopher_mcp_python/agent.py` (`GopherAgent.create_with_*` static
  methods).
- Contract tests:
  `tests/test_agent_create_by.py`.
- Sibling pip-style wrappers (older, two-variant superset):
  `examples/pip/` — same venv-bootstrap pattern these wrappers
  inherit.
