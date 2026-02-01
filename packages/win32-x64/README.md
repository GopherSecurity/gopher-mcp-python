# gopher-orch-native-win32-x64

Native library package for gopher-orch (Windows x64).

## Installation

This package is automatically installed as a dependency of `gopher-orch` on compatible platforms.

```bash
pip install gopher-orch
```

## Manual Installation

```bash
pip install gopher-orch-native-win32-x64
```

## Platform

- **OS**: Windows
- **Architecture**: x64

## Usage

This package is not meant to be used directly. It provides the native library for the main `gopher-orch` package.

```python
from gopher_orch import GopherAgent

agent = GopherAgent.create_with_server_config(provider, model, config)
answer = agent.run("Hello!")
agent.dispose()
```

## License

MIT
