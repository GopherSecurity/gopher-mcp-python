# OAuth Auto Verification With Custom IdP

The stable OAuth auto verification path uses local test fixtures instead of
Gmail, hosted Gopher services, or real OAuth provider credentials. It verifies
the Python SDK behavior that matters for automatic OAuth:

- discovering OAuth protection from an MCP endpoint
- reading protected resource metadata
- using OAuth authorization server metadata
- refreshing a cached token through the token endpoint
- injecting the refreshed bearer token into `GopherAgent.create_with_url`
  runtime options before the native FFI call

The tests cover both endpoint shapes used by deployments:

- direct MCP server endpoint
- MCP gateway endpoint

Fixture credentials such as `test-client`, `test-secret`, and
`test-refresh-token` are local test data. They are not GitHub Secrets, and the
suite asserts that fixture secrets do not appear in captured output or errors.

## Local Command

Run the deterministic custom IdP suite with:

```bash
scripts/test-oauth-custom-idp.sh
```

The script runs:

```bash
python -m pytest \
  tests/test_oauth_auto_custom_idp.py \
  tests/test_oauth_auto_custom_idp_failures.py \
  tests/test_custom_oauth_test_idp.py \
  tests/test_custom_protected_mcp_endpoints.py \
  tests/test_oauth_test_token_helper.py
```

Extra pytest arguments can be passed through:

```bash
scripts/test-oauth-custom-idp.sh -q
```

## CI Coverage

`.github/workflows/oauth-verify.yml` runs the same suite on pull requests and
manual dispatch. It installs the package with development dependencies and does
not require hosted endpoints, Gmail accounts, OAuth client secrets, refresh
tokens, LLM provider keys, or other real credentials.

## Live Smoke Tests

Gmail or real Gopher endpoint verification remains useful as an optional smoke
test because it proves compatibility with external provider policy, hosted
gateway configuration, and real account consent. Those checks are operationally
different from SDK correctness tests: they depend on provider availability,
account security rules, valid refresh tokens, and live service configuration.

Keep live smoke tests manual, scheduled, or otherwise separate from the stable
pull-request gate. The API example workflow and docs live under
`examples/api/`.

For a possible full native end-to-end extension, see
[`oauth-auto-native-follow-up.md`](oauth-auto-native-follow-up.md).
