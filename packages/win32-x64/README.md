# gopher-security-mcp-native-win32-x64

Native library package for gopher-security-mcp (Windows x64).

## Installation

This package is automatically installed as a dependency of `gopher-security-mcp` on compatible platforms.

```bash
pip install gopher-security-mcp
```

## Manual Installation

```bash
pip install gopher-security-mcp-native-win32-x64
```

## Platform

- **OS**: Windows
- **Architecture**: x64

## Usage

This package is not meant to be used directly. It provides the native library for the main `gopher-security-mcp` package.

```python
from gopher_security_mcp import GopherAgent

agent = GopherAgent.create_with_server_config(provider, model, config)
answer = agent.run("Hello!")
agent.dispose()
```

## License

MIT
