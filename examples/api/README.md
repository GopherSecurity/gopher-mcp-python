# examples/api — Local Python SDK examples

The seven API examples use this checkout's `gopher_mcp_python/` source and local
native libraries through their `*_run.sh` wrappers. Each run prints the SDK source
and the exact native library file loaded.

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

## Quick start

1. Build the native libraries from the repository root if needed:

   ```sh
   ./build.sh
   ```

2. Set your example's environment variables. Every example needs `LLM_MODEL`
   and the selected provider's credentials:

   ```sh
   export LLM_MODEL=<your-model-id>
   export ANTHROPIC_API_KEY=...
   export GOPHER_API_KEY=...  # API-key and selector factories
   ```

3. Run the wrapper with optional queries:

   ```sh
   ./examples/api/create_by_api_key_run.sh "List my available tools"
   ```

The wrappers use `python3` by default. Set `PYTHON=/path/to/python` to select
another interpreter, including one in an existing virtual environment. The SDK
is imported directly from this checkout; there is no package installation or
network setup step. Existing `test-project-*` directories are unused.

## Manual run

Use the local launcher directly to get the same source and native selection:

```sh
python3 examples/api/_run_local.py create_by_api_key.py "List my available tools"
```

Standalone `create_by_*.py` files retain ordinary Python imports. When copying
one into another project, its SDK follows that project's Python environment.

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

The runners also recognize:

- `PYTHON` — Python interpreter, default `python3`.
- `GOPHER_MCP_PYTHON_LIBRARY_PATH` — explicit native library file or directory.
- `GOPHER_ORCH_LIBRARY_PATH` — alternative override, used when the first is unset.
- `ANTHROPIC_API_KEY` — credentials for the default `AnthropicProvider`.
- `DEBUG` — SDK/native load diagnostics.

`LLM_PROVIDER` defaults to `AnthropicProvider`. `LLM_MODEL` is required.

## Picking the right factory

| Factory | Selects | Inventory request |
| --- | --- | --- |
| `create_with_api_key` | All authorized sources, or supplied selector arrays | GET for zero/one selector; POST for multiple |
| `create_with_server_id` / `_server_name` | Positional server plus any additional selectors | GET for one selector; POST for multiple |
| `create_with_gateway_id` / `_gateway_name` | Remote gateway plus any additional selectors | GET for one selector; POST for multiple |
| `create_with_server_config` | Sources in inline JSON | None |
| `create_with_url` | One remote MCP endpoint | None |

A GET rejected with HTTP 405 is retried once as POST with the same selection.
Multiple-selector POST requests never fall back to GET or fan out. The same
30-second deadline covers both attempts and their response bodies.

The API response defines the sources. A gateway stays a remote MCP endpoint;
its backing servers are not expanded locally. Inventory selector arrays are
additive; all four empty arrays mean all authorized sources. Multiple distinct
OAuth bindings require embedded authorization v1 in the actual loaded binary.
See [API-key inventory and OAuth](../../docs/inventory-api-key.md).

`create_by_api_key.py` accepts optional JSON arrays in `GOPHER_SERVER_IDS`,
`GOPHER_SERVER_NAMES`, `GOPHER_GATEWAY_IDS`, and `GOPHER_GATEWAY_NAMES`:

```bash
export GOPHER_SERVER_IDS='["mail", "calendar"]'
export GOPHER_GATEWAY_NAMES='["Production"]'
python3 examples/api/create_by_api_key.py "List my available tools"
```

## How local libraries are selected

The shared launcher puts this repository first on Python's import path and
selects a native library in this order:

1. An explicit `GOPHER_MCP_PYTHON_LIBRARY_PATH` or `GOPHER_ORCH_LIBRARY_PATH`.
2. `native/<platform>-<arch>/lib`, such as `native/darwin-x64/lib`.
3. `native/current/lib`.
4. `native/lib`.
5. `third_party/gopher-orch/build/lib` or `build/bin`.
6. `third_party/gopher-orch/cmake-build-debug/lib` or `cmake-build-debug/bin`.

A directory override uses the SDK's version-aware library resolver. The launcher
then checks that the loaded binary matches the selected file before running the
example. A missing or unloadable local library stops execution with diagnostics.

To test a particular local build:

```sh
GOPHER_MCP_PYTHON_LIBRARY_PATH="$PWD/third_party/gopher-orch/build/lib" \
  ./examples/api/create_by_api_key_run.sh "List my available tools"
```

## Troubleshooting

If a native library is missing, run `./build.sh` from the repository root or set
an explicit library override. If loading fails, inspect the printed load
errors and confirm that the binary matches the selected Python interpreter's
platform and architecture. Rebuild after changing the native submodule revision.

Independent OAuth flows require embedded authorization interface v1. Check the
actual binary with:

```sh
PYTHONPATH=. GOPHER_MCP_PYTHON_LIBRARY_PATH="$PWD/native/current/lib" \
  python3 scripts/check-embedded-auth-native.py
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
