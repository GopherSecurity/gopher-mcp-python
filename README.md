# gopher-mcp-python Python SDK

Python SDK for gopher-mcp-python, providing AI agent orchestration with native C++ performance through ctypes FFI bindings.

## Features

- Python 3.8+ compatibility
- pip/setuptools build system
- ctypes FFI bindings to native library
- GopherAgent class with builder pattern configuration
- Context manager support for automatic resource cleanup
- Typed errors (AgentError, ApiKeyError, ConnectionError, TimeoutError)
- Comprehensive test suite with pytest

## Requirements

- Python 3.8 or higher
- `venv` and `pip` for PyPI installation, examples, and development workflows
- Native gopher-mcp-python library (built from source)
- On Linux, system OpenSSL runtime libraries (`libssl` / `libcrypto`) from
  your distribution. Native wheels do not bundle OpenSSL, so OS security
  updates remain effective.

On Debian/Ubuntu, install the Python venv and pip packages before using the
PyPI install path, running examples, or setting up development dependencies:

```bash
sudo apt-get install python3 python3-venv python3-pip
```

## Installation

### From Source

1. Clone the repository:
```bash
git clone https://github.com/GopherSecurity/gopher-mcp-python.git
cd gopher-mcp-python
```

2. Build the native library:
```bash
./build.sh
```

3. Install the Python package:
```bash
python3 -m pip install -e .
```

## Quick Start

### Using API Key

```python
from gopher_mcp_python import GopherAgent, GopherAgentConfig

# Create configuration with API key
config = (GopherAgentConfig.builder()
    .provider("AnthropicProvider")
    .model("claude-3-haiku-20240307")
    .api_key("your-api-key")
    .build())

# Create and use agent with context manager
with GopherAgent.create(config) as agent:
    response = agent.run("What time is it in Tokyo?")
    print(response)
```

### Using JSON Server Configuration

```python
from gopher_mcp_python import GopherAgent, GopherAgentConfig

# Create configuration with server config
config = (GopherAgentConfig.builder()
    .provider("AnthropicProvider")
    .model("claude-3-haiku-20240307")
    .server_config('{"mcpServers": [...]}')
    .build())

# Create agent
agent = GopherAgent.create(config)
try:
    response = agent.run("What is the weather?")
    print(response)
finally:
    agent.dispose()
```

### Using Convenience Methods

```python
from gopher_mcp_python import GopherAgent

# Create with API key (shorthand)
agent = GopherAgent.create_with_api_key(
    provider="AnthropicProvider",
    model="claude-3-haiku-20240307",
    api_key="your-api-key"
)

# Or with server config
agent = GopherAgent.create_with_server_config(
    provider="AnthropicProvider",
    model="claude-3-haiku-20240307",
    server_config='{"mcpServers": [...]}'
)
```

### Getting Detailed Results

```python
from gopher_mcp_python import GopherAgent

with GopherAgent.create(config) as agent:
    result = agent.run_detailed("What time is it?")

    if result.is_success():
        print(f"Response: {result.response}")
        print(f"Iterations: {result.iteration_count}")
        print(f"Tokens used: {result.tokens_used}")
    elif result.is_timeout():
        print(f"Request timed out: {result.error_message}")
    else:
        print(f"Error: {result.error_message}")
```

## API Reference

### GopherAgent

Main class for interacting with the gopher-mcp-python native library.

#### Static Methods

- `GopherAgent.init()` - Initialize the library (called automatically)
- `GopherAgent.shutdown()` - Shutdown the library
- `GopherAgent.is_initialized()` - Check if library is initialized
- `GopherAgent.create(config)` - Create an agent with configuration
- `GopherAgent.create_with_api_key(provider, model, api_key)` - Convenience method
- `GopherAgent.create_with_server_config(provider, model, server_config)` - Convenience method

#### Instance Methods

- `agent.run(query, timeout_ms=60000)` - Run a query and get response string
- `agent.run_detailed(query, timeout_ms=60000)` - Run a query and get AgentResult
- `agent.dispose()` - Release resources
- `agent.is_disposed()` - Check if agent is disposed

### GopherAgentConfig

Configuration class with builder pattern.

```python
config = (GopherAgentConfig.builder()
    .provider("AnthropicProvider")  # Required
    .model("claude-3-haiku-20240307")  # Required
    .api_key("key")  # Either api_key or server_config required
    .server_config("{...}")  # Either api_key or server_config required
    .build())
```

### AgentResult

Result class with status and metadata.

- `result.response` - Response text
- `result.status` - AgentResultStatus enum
- `result.iteration_count` - Number of iterations
- `result.tokens_used` - Tokens consumed
- `result.error_message` - Error message (if applicable)
- `result.is_success()` - Check if successful
- `result.is_error()` - Check if error
- `result.is_timeout()` - Check if timeout

### Exceptions

- `AgentError` - Base exception for agent errors
- `ApiKeyError` - Invalid API key
- `ConnectionError` - Connection failed
- `TimeoutError` - Operation timed out

## Development

### Running Tests

```bash
pytest
```

For deterministic OAuth auto verification with a local custom IdP and local MCP
server/gateway endpoints, see
[`docs/oauth-auto-custom-idp.md`](docs/oauth-auto-custom-idp.md).

### Code Formatting

This project uses Black for code formatting and Ruff for linting.

Format code:
```bash
black .
```

Check formatting without modifying:
```bash
black --check .
```

Run linter:
```bash
ruff check .
```

Fix linting issues:
```bash
ruff check --fix .
```

### Building the Native Library

```bash
./build.sh
```

### Clean Build

```bash
./build.sh --clean
```

## Environment Variables

- `GOPHER_MCP_PYTHON_LIBRARY_PATH` - Custom path to native library
- `DEBUG` - Enable debug output for library loading

## License

See LICENSE file for details.
