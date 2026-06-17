# examples/api — Python SDK examples for the seven `create_by_*` factories

This directory holds the Python siblings of the C++ SDK examples under
[`gopher-orch/examples/sdk/api/`](../../third_party/gopher-orch/examples/sdk/api/)
and the TypeScript siblings under
[`gopher-mcp-js/examples/api/`](https://github.com/GopherSecurity/gopher-mcp-js/tree/main/examples/api).
Each `.py` file mirrors its `.cc` and `.ts` counterparts one-to-one
and exercises exactly one of the seven `create_by_*` factories the
SDK exposes through `GopherAgent`.

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

Each `.py` file ships with a `*_run.sh` wrapper that sets the native
library path, exports `PYTHONPATH` so the in-repo package is
importable without `pip install`, and forwards positional arguments
as queries.

## Quick start

1. Build the native library (one-time, repeats after a submodule bump):

   ```sh
   cd /Users/james/Desktop/dev/gopher-mcp-python
   ./build.sh
   ```

   This builds `third_party/gopher-orch` and drops the resulting
   `libgopher-orch.dylib` / `.so` / `.dll` into `native/lib/`.

2. Install the Python package in editable mode so the examples can
   import `gopher_mcp_python` without manual `PYTHONPATH` tweaking:

   ```sh
   pip install -e .
   ```

   The wrappers also export `PYTHONPATH` as a belt-and-braces measure,
   so you can skip this step if you only want to run the wrappers
   themselves.

3. Pick a factory and run the matching wrapper:

   ```sh
   export GOPHER_API_KEY=...
   export LLM_MODEL=<your-model-id>
   export ANTHROPIC_API_KEY=...
   ./examples/api/create_by_api_key_run.sh "What time is it in Tokyo?"
   ```

   Positional arguments to the wrapper become queries; with no
   arguments each example runs a canned query so a first invocation
   produces visible output.

4. To target a specific MCP server, MCP gateway, or one-off URL, set
   the corresponding routing env var and run the matching wrapper.
   See the table below.

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

Notes:

- `LLM_PROVIDER` defaults to `AnthropicProvider` in every example.
- `LLM_MODEL` has no default; each example refuses to start until the
  variable is set rather than calling into the FFI with a placeholder.
  This matches the env-var-required path the JS side picked so the
  examples never surface a stale or fictional model identifier.
- The LLM provider's own credentials (`ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `GOOGLE_API_KEY`, etc.) are required by the
  backing provider rather than by the SDK directly; the wrappers
  warn if `ANTHROPIC_API_KEY` is unset since `AnthropicProvider` is
  the default.

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
`gopher-orch/docs/Agent.md` ("Simple creation factories" section) so
the Python-side documentation stays aligned with the upstream C++
docs and the TypeScript port.

## How the examples find the SDK

Each `.py` file imports `GopherAgent` from the installed
`gopher_mcp_python` package:

```python
from gopher_mcp_python import GopherAgent
```

Resolution flow:

- During development: `pip install -e .` from the repo root makes
  the in-tree `gopher_mcp_python/` directory importable. The
  wrappers also set `PYTHONPATH="$PROJECT_DIR"` so the import works
  without a prior `pip install -e .`.
- Downstream: a consumer who runs `pip install gopher-mcp-python`
  and copies one of these examples into their own project does
  not need any import-path edit — the same line works against the
  PyPI-installed package as-is.

This differs from the JS sibling, which uses `import { GopherAgent }
from '../../src'` to keep the example tied to the in-repo TypeScript
sources. Python uses package-install semantics so the same `from
gopher_mcp_python import GopherAgent` line works in both the in-repo
and the installed-from-PyPI cases without modification.

## How the wrappers find the native library

Each `*_run.sh` script:

1. Resolves `PROJECT_DIR` to the `gopher-mcp-python` repo root (two
   `dirname` calls because the scripts sit at `examples/api/`
   rather than `examples/`).
2. Exits early with a pointer at `./build.sh` if
   `$PROJECT_DIR/native/lib` is missing.
3. Runs a pre-flight `python3 -c "import gopher_mcp_python"` and
   prints a `pip install -e .` hint on failure. The `.ts` side did
   not need this step because `npx tsx` + relative import work out
   of the box; Python requires the package on `sys.path`.
4. Exports `DYLD_LIBRARY_PATH` (macOS) and `LD_LIBRARY_PATH`
   (Linux) to `$PROJECT_DIR/native/lib` so the ctypes loader picks
   up the freshly built dylib from `build.sh` rather than the
   pip-installed platform package or any system-installed copy.
5. Exports `PYTHONPATH="$PROJECT_DIR"` so the in-tree package is
   importable even when `pip install -e .` has not been run.
6. Invokes `python3 examples/api/<file>.py "$@"` so positional
   arguments pass straight through as queries.

If you need to point at a different library location entirely, set
`GOPHER_MCP_PYTHON_LIBRARY_PATH` before invoking the wrapper. That
env var is checked first by `gopher_mcp_python/ffi/library.py` and
bypasses the `native/lib/` and platform-package resolution steps.

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
