# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]


## [0.1.34] - 2026-08-16

### Changed

- Pin `gopher-orch` native library to [v0.1.34](https://github.com/GopherSecurity/gopher-orch/releases/tag/v0.1.34).

#### SDK changes since v0.1.30

- Use PyPI libs for create by URL example
- Keep OAuth on existing factories (#15)
- Fix hosted MCP OAuth fallback (#15)
- Fix agent finalizer fallback (#15)
- Fix OAuth parity coverage (#15)
- Fix OAuth async agent factories (#15)
- Fix OAuth helper modules (#15)
- Fix OAuth create option types (#15)
- Fix agent options ABI (#15)
- Fix native owned string cleanup (#15)
- Fail PR example verification on bundled OpenSSL
- Relax Linux example native rpath checks
- Use stable draft id for Python live verification
- Stabilize Python example missing-env checks
- Clean up failed Python example verification projects
- Redact live example verifier output
- Verify Linux native dependencies in examples
- Strengthen Python example live verification
- Relax Python example verification on PRs
- Verify Python examples against PR checkout
- Clean up Python native verifier probe
- Fix Python example verifier workflow syntax
- Add Python SDK example verification
- Add Python native platform search paths
- Pin Linux builder base image
- Clarify auth error exports
- Fix versioned native library resolution
- Verify Linux native package dependencies
- Avoid bundling OpenSSL in Linux wheels
- Document run null-response behavior
- Fix Python debug hint in agent errors
- Clarify Python packaging requirements
- Support Linux native builds for Python SDK
- Improve Python build script parity
- Expand Python auth public exports
- Add Python native platform search paths
- Improve Python native loader diagnostics
- Raise Python agent errors for null runs
- Improve Python agent create errors
- Remove checked-in header example binaries
- Cover header example empty token behavior
- Harden header example verification script
- Keep build submodules pinned by default
- Fix runtime options layering

#### gopher-orch v0.1.34 highlights


### Added
- Add structured OAuth discovery errors (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Add per-server runtime credentials (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Add MCP OAuth challenge probe (https://github.com/GopherSecurity/gopher-orch/pull/159)
### Changed
- make format
- Document SDK OAuth native usage (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Extend FFI agent runtime options (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Preserve per-server credentials for tool calls (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Apply per-server credentials during discovery (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Complete OAuth client SDK accessors (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Expose MCP OAuth discovery over C API (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Fetch OAuth authorization metadata (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Fetch OAuth protected resource metadata (https://github.com/GopherSecurity/gopher-orch/pull/159)
- Lock down SDK runtime auth headers (https://github.com/GopherSecurity/gopher-orch/pull/159)
- make format
- Cover gateway OAuth token proxy workaround
- Guard gateway auto OAuth metadata adoption
- Isolate gateway passthrough backend routes
- Clarify gateway backend auth failures
- Fail fast on unsupported gateway backend auth (https://github.com/GopherSecurity/gopher-orch/pull/147)
- Pin Presidio to GHCR 2.2.362 instead of tracking mcr :latest
- Keep the backend manifest and audit token out of the pod spec
### Fixed
- Fix Windows ARM64 OAuth discovery build
- Fix gateway OAuth token exchange for Postman
- Fix gateway OAuth passthrough discovery
- Fix gateway streamable HTTP curl stop handling

## [0.1.30] - 2026-07-05

### Changed

- Pin `gopher-orch` native library to [v0.1.30](https://github.com/GopherSecurity/gopher-orch/releases/tag/v0.1.30).

#### SDK changes since v0.1.23

- Improve release notes validation and CI extraction
- Clarify Python packaging requirements
- Support Linux native builds for Python SDK
- Improve Python build script parity
- Expand Python auth public exports
- Add Python native platform search paths
- Improve Python native loader diagnostics
- Raise Python agent errors for null runs
- Improve Python agent create errors
- Add dynamic header verification runner (#11)
- Add dynamic header create_by_url example (#11)
- Pass runtime options through agents (#11)
- Bind agent runtime options FFI (#11)
- Add agent runtime options API (#11)
- Build latest local native libs (#11)
- Update gopher-orch submodule (#11)
- Format code
- Switch examples/api/ to resolve against PyPI fix (#9)
- Auto-populate CHANGELOG.md in dump-version.sh (#9)
- Add examples/api/README.md fix (#9)
- Add seven *_run.sh wrappers for the examples/api/ create_by_* set fix (#9)
- Add Python example for create_with_url fix (#9)
- Add Python example for create_with_gateway_name fix (#9)
- Add Python example for create_with_gateway_id fix (#9)
- Add Python example for create_with_server_name fix (#9)
- Add Python example for create_with_server_id fix (#9)
- Add Python example for create_with_server_config fix (#9)
- Add Python example for create_with_api_key fix (#9)
- Add contract tests for the five new routing factories fix (#9)
- Surface the FFI handle type at the package root fix (#9)
- Document the builder gap for the new routing factories fix (#9)
- Expose five new ReActAgent factories on GopherAgent fix (#9)
- Bind five new ReActAgent factories in ctypes FFI layer fix (#9)
- Track gopher-orch br_release branch and bump submodule to 0.1.23 (#9)

#### gopher-orch v0.1.30 highlights


### Added
- Add MCP tools discovery fallback
- Add access token gateway verification example
### Changed
- Prefer direct discovery for API HTTP gateways
- Prefer Streamable HTTP MCP transport
- Improve agent creation FFI errors

## [0.1.23] - 2026-06-18

### Changed

- Pin `gopher-orch` native library to [v0.1.23](https://github.com/GopherSecurity/gopher-orch/releases/tag/v0.1.23).

#### SDK changes since v0.1.21

- Improve release notes validation and CI extraction
- Auto-populate CHANGELOG.md in dump-version.sh
- Add examples/api/README.md fix (#9)
- Add seven *_run.sh wrappers for the examples/api/ create_by_* set fix (#9)
- Add Python example for create_with_url fix (#9)
- Add Python example for create_with_gateway_name fix (#9)
- Add Python example for create_with_gateway_id fix (#9)
- Add Python example for create_with_server_name fix (#9)
- Add Python example for create_with_server_id fix (#9)
- Add Python example for create_with_server_config fix (#9)
- Add Python example for create_with_api_key fix (#9)
- Add contract tests for the five new routing factories fix (#9)
- Surface the FFI handle type at the package root fix (#9)
- Document the builder gap for the new routing factories fix (#9)
- Expose five new ReActAgent factories on GopherAgent fix (#9)
- Bind five new ReActAgent factories in ctypes FFI layer fix (#9)
- Track gopher-orch br_release branch and bump submodule to 0.1.23 (#9)

#### gopher-orch v0.1.23 highlights


### Added
- Add SDK examples for the six remaining create_by_* factories (#116)
- Add SDK example for ReActAgent::createByApiKey (#116)
- Add FFI unit tests for the five new agent create_by_* entry points (#116)
- Add CHANGELOG entry for the five new ReActAgent factories (#116)
- Add unit tests for the five new ReActAgent factories (#116)
- Implement createByUrl: synthesize http_sse config and delegate (#116)
- Implement createByServerId / createByServerName / createByGatewayId / createByGatewayName (#116)
- Add query-string overload to ApiEngine::fetchMcpServers (#116)
### Changed
- Hardcode provider and model in createByApiKey example (#116)
- Expose five new agent factories through the C FFI (#116)
- Document the five new ReActAgent simple-creation factories (#116)
- Declare five new ReActAgent factory methods (#116)
- Unstaged changes: CMakeLists.txt,third_party/gopher-mcp

## [0.1.21] - 2026-04-29

### Added

- Add bundling libs for macOS and Linux

## [0.1.16] - 2026-04-24

### Changed

- Keep the same version as native library

## [0.1.15] - 2026-04-22

### Added

- Add PyPI package URL and install command to GitHub release notes
- Auto-update GOPHER_ORCH_VERSION in CI via dump-version.sh

### Changed

- Switch auth example to always use PyPI packages instead of local build
- Update GOPHER_ORCH_VERSION from v0.1.2 to v0.1.14 so native package includes auth config C API

### Fixed

- Fix auth example not working with PyPI package due to missing native auth config symbols (was using gopher-orch v0.1.2 binaries)

## [0.1.14] - 2026-04-21

### Added

- Add `/oauth/token` proxy route to forward token exchange to IdP, injecting client_id/client_secret — required for MCP clients like claude.ai (#6)
- Add token validation in McpAuthMiddleware (was only checking Bearer presence, not validating JWT) (#6)
- Add RequestLoggingMiddleware for debugging MCP and OAuth flows (#6)
- Add empty release notes validation in dump-version.sh — errors out if all Added/Changed/Fixed sections are empty

### Changed

- Improve CI release notes extraction: try versioned section `[X.Y.Z]` first, then `[Unreleased]`, with proper fallbacks
- Update gopher-orch submodule to `main` branch
- Fix example pyproject.toml dependencies: replace Flask with Starlette/uvicorn, add httpx

### Fixed

- Fix OAuth flow for claude.ai: MCP clients need `/oauth/token` proxy to exchange auth codes for tokens (#6)
- Fix CI release notes showing empty What's Changed section
- Fix release notes fallback regex for extracting versioned sections from CHANGELOG.md

## [0.1.2] - 2026-03-12

## [0.1.1] - 2026-02-28

## [0.1.0-20260227-124047] - 2026-02-27

### Changed

- **Package Rename** from `gopher-orch` to `gopher-mcp-python`
  - Main package: `gopher-mcp-python` (was `gopher-orch`)
  - Import: `from gopher_mcp_python import GopherAgent` (was `gopher_orch`)
  - Platform packages renamed from `gopher-orch-native-*` to `gopher-mcp-python-native-*`
  - Environment variable: `GOPHER_MCP_PYTHON_LIBRARY_PATH` (was `GOPHER_ORCH_LIBRARY_PATH`)

### Added

- **Centralized Version Management**
  - Add `scripts/update_version.py` to update version across all files
  - Add `python scripts/update_version.py <version>` script
  - Workflow now reads version from `pyproject.toml` instead of hardcoded env

### Fixed

- Fix native library loading - keep library name as `libgopher-orch` (from C++ project)
- Make `gopher_orch_set_log_level` function optional for compatibility

## [0.1.0] - 2026-02-08

### Added

- **Initial PyPI Release**
  - Platform-specific packages for native binaries
    - `gopher-mcp-python-native-darwin-arm64`
    - `gopher-mcp-python-native-darwin-x64`
    - `gopher-mcp-python-native-linux-arm64`
    - `gopher-mcp-python-native-linux-x64`
    - `gopher-mcp-python-native-win32-arm64`
    - `gopher-mcp-python-native-win32-x64`
  - Main `gopher-mcp-python` package with Python bindings

- **Core Features**
  - `GopherAgent` class for AI agent orchestration
  - `GopherAgentConfig` builder pattern for configuration
  - `create()` - Create agent with configuration
  - `run()` - Execute queries with tool support
  - Native FFI bindings via ctypes

- **Examples**
  - JSON configuration example (`client_example_json.py`)
  - API key example (`client_example_api.py`)

- **CI/CD**
  - GitHub Actions workflow for publishing to TestPyPI
  - Automatic download of gopher-mcp-python native binaries
  - Multi-platform support (6 platforms)

---

[Unreleased]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...HEAD
[0.1.34]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.34[0.1.30]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.30[0.1.23]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.23[0.1.21]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.21[0.1.16]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.16[0.1.15]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.15[0.1.14]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.14[0.1.2]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.2[0.1.1]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0-20260227-124047...v0.1.1[0.1.0-20260227-124047]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0...v0.1.0-20260227-124047
[0.1.0]: https://github.com/GopherSecurity/gopher-mcp-python/releases/tag/v0.1.0
