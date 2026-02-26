# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Centralized Version Management**
  - Add `scripts/update_version.py` to update version across all files
  - Add `python scripts/update_version.py <version>` script
  - Workflow now reads version from `pyproject.toml` instead of hardcoded env

## [0.1.0] - 2026-02-08

### Added

- **Initial PyPI Release**
  - Platform-specific packages for native binaries
    - `gopher-orch-native-darwin-arm64`
    - `gopher-orch-native-darwin-x64`
    - `gopher-orch-native-linux-arm64`
    - `gopher-orch-native-linux-x64`
    - `gopher-orch-native-win32-arm64`
    - `gopher-orch-native-win32-x64`
  - Main `gopher-orch` package with Python bindings

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
  - Automatic download of gopher-orch native binaries
  - Multi-platform support (6 platforms)

---

[Unreleased]: https://github.com/GopherSecurity/gopher-mcp-python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/GopherSecurity/gopher-mcp-python/releases/tag/v0.1.0
