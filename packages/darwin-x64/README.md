# gopher-mcp-python-native-darwin-x64

Native library package for gopher-mcp-python (macOS Intel).

## Installation

This package is automatically installed as a dependency of `gopher-mcp-python` on compatible platforms.

```bash
pip install gopher-mcp-python
```

## Manual Installation

```bash
pip install gopher-mcp-python-native-darwin-x64
```

## Platform

- **OS**: macOS
- **Architecture**: Intel

## Usage

This package is not meant to be used directly. It provides the native library for the main `gopher-mcp-python` package.

```python
from gopher_mcp_python import GopherAgent

agent = GopherAgent.create_with_server_config(provider, model, config)
answer = agent.run("Hello!")
agent.dispose()
```

## License

Apache License 2.0
