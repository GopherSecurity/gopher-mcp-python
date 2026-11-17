# Shared inventory conformance fixture

`conformance.json` is an unchanged copy of the shared native/JS inventory cases.
Keeping it in this repository lets SDK verification run without access to the
private native repository, including on pull requests from forks.

Source: `GopherSecurity/gopher-orch`,
`tests/fixtures/inventory/conformance.json` at commit `ac84f1b30831a1d9d9eb180c0247aa9934b636c3`
(`v0.1.45`).

SHA-256: `b2eef21407a47309cac30eef74813c2fa62c8e81c5e06a363b0fa9955ac4e1a5`.

When the pinned native revision changes the shared contract, copy the updated
fixture verbatim and update this source revision and checksum. From the SDK
repository root, compare a local native checkout with:

```sh
cmp tests/fixtures/inventory/conformance.json \
  third_party/gopher-orch/tests/fixtures/inventory/conformance.json
```
