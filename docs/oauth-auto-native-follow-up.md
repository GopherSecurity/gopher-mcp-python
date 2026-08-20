# Optional Native OAuth E2E Follow-Up

The custom IdP OAuth verification suite is the stable pull-request signal. It
starts local OAuth and protected MCP endpoint harnesses, lets
`GopherAgent.create_with_url` resolve OAuth automatically, and asserts that the
native FFI boundary receives runtime options containing the refreshed bearer
token.

A full native end-to-end test can be added later, but it should stay separate
from the stable PR gate unless it is fully deterministic.

## Proposed Shape

Reuse the same model as `docs/oauth-auto-custom-idp.md`:

- local custom OAuth/OIDC IdP
- local protected MCP server endpoint
- local protected MCP gateway endpoint
- refresh-token-backed OAuth setup

Add one deterministic protected MCP tool:

```text
tool: whoami
input: {}
output: { "subject": "test-user@example.test" }
```

Then create a real `GopherAgent` through `GopherAgent.create_with_url` and run a
query that must call the protected `whoami` tool. The test should assert the
authenticated result, not just successful agent creation.

## When To Enable

Keep this path manual, scheduled, or non-blocking until these dependencies are
controlled:

- native package availability for each target platform
- deterministic LLM/provider behavior or a reliable test provider
- stable local MCP tool execution behavior
- clear runtime bounds suitable for CI

Until those are in place, the focused custom IdP tests remain the correct PR
gate because they verify the SDK OAuth flow without external service or native
runtime flake.
