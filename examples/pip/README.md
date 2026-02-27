# Using gopher-orch SDK via pip

This guide shows how to use the gopher-orch Python SDK when installed via pip.

## Installation

```bash
pip install gopher-orch
```

The package will automatically detect your platform and load the native library from the corresponding platform-specific package.

### Supported Platforms

| Platform | Architecture | Package |
|----------|-------------|---------|
| macOS | ARM64 (Apple Silicon) | gopher-orch-native-darwin-arm64 |
| macOS | x64 (Intel) | gopher-orch-native-darwin-x64 |
| Linux | x64 | gopher-orch-native-linux-x64 |
| Linux | ARM64 | gopher-orch-native-linux-arm64 |
| Windows | x64 | gopher-orch-native-win32-x64 |
| Windows | ARM64 | gopher-orch-native-win32-arm64 |

### Installing from PyPI

```bash
pip install gopher-orch
```

## Quick Start

### Using API Key

```python
from gopher_orch import GopherAgent

# Create agent with API key (fetches server config from Gopher API)
agent = GopherAgent.create_with_api_key(
    'AnthropicProvider',
    'claude-3-haiku-20240307',
    'your-gopher-api-key'
)

# Run a query
answer = agent.run('What is the weather like in New York?')
print(answer)

# Clean up when done
agent.dispose()
```

### Using Server Configuration

```python
import json
from gopher_orch import GopherAgent

# Server configuration JSON
server_config = json.dumps({
    "succeeded": True,
    "code": 200000000,
    "message": "success",
    "data": {
        "servers": [
            {
                "version": "2025-01-09",
                "serverId": "1",
                "name": "my-mcp-server",
                "transport": "http_sse",
                "config": {
                    "url": "http://localhost:3001/mcp",
                    "headers": {}
                },
                "connectTimeout": 5000,
                "requestTimeout": 30000,
            },
        ],
    },
})

# Create agent with server config
agent = GopherAgent.create_with_server_config(
    'AnthropicProvider',
    'claude-3-haiku-20240307',
    server_config
)

# Run a query
answer = agent.run('List available tools')
print(answer)

# Clean up when done
agent.dispose()
```

## Running the Examples

### Prerequisites

1. Python 3.8+ installed
2. ANTHROPIC_API_KEY environment variable set

### API Key Example (Recommended)

Use this approach when you have a Gopher API key. The server configuration is fetched automatically from the Gopher API.

```bash
cd examples/pip

# Set your Gopher API key
export GOPHER_API_KEY=your_api_key_here

# Use default (latest) SDK version from PyPI
./client_example_api_run.sh

# Or specify a specific version
SDK_VERSION=0.1.0.dev20260208150923 ./client_example_api_run.sh

# Pass a custom question
./client_example_api_run.sh "What tools are available?"
```

### Server Config Example

Use this approach when you want to specify MCP servers directly via JSON configuration.

**Additional Prerequisites:**
- MCP servers running (see examples/server3001 and examples/server3002)

```bash
cd examples/pip

# Use default (latest) SDK version from PyPI
./client_example_json_run.sh

# Or specify a specific version
SDK_VERSION=0.1.0.dev20260208150923 ./client_example_json_run.sh
```

### Run manually

```bash
# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install from PyPI
pip install gopher-orch gopher-orch-native-darwin-arm64

# Run the API key example
export GOPHER_API_KEY=your_api_key_here
python client_example_api.py

# Or run the server config example (requires local MCP servers)
python client_example_json.py
```

## API Reference

### GopherAgent

#### Static Methods

- `GopherAgent.create_with_api_key(provider, model, api_key)` - Create agent using Gopher API key
- `GopherAgent.create_with_server_config(provider, model, server_config_json)` - Create agent with server configuration JSON

#### Instance Methods

- `agent.run(query, timeout_ms=30000)` - Run a query and return the response
- `agent.dispose()` - Release resources (must be called when done)

## Troubleshooting

### Native library not found

If you see "Failed to load gopher-orch library", ensure:

1. You're on a supported platform
2. The platform-specific package is installed
3. Try reinstalling: `pip install --force-reinstall gopher-orch`

### Permission errors on macOS

If you get permission errors loading the library:

```bash
xattr -d com.apple.quarantine $(python -c "import gopher_orch_native_darwin_arm64; print(gopher_orch_native_darwin_arm64.get_library_file())")
```

## Environment Variables

- `ANTHROPIC_API_KEY` - Required for using Anthropic models
- `GOPHER_API_KEY` - Required for `create_with_api_key()` - get one from https://gopher.security
- `DEBUG=1` - Enable debug logging for library loading
- `GOPHER_ORCH_LIBRARY_PATH` - Override the native library path
- `SDK_VERSION` - Override the SDK version when running example scripts
