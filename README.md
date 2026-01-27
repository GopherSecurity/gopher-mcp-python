# gopher-orch - Python SDK

Python SDK for Gopher Orch - AI Agent orchestration framework with native C++ performance.

## Table of Contents

- [Features](#features)
- [When to Use This SDK](#when-to-use-this-sdk)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Building from Source](#building-from-source)
  - [Prerequisites](#prerequisites)
  - [Step 1: Clone the Repository](#step-1-clone-the-repository)
  - [Step 2: Build Everything](#step-2-build-everything)
  - [Step 3: Verify the Build](#step-3-verify-the-build)
  - [Step 4: Run Tests](#step-4-run-tests)
- [Native Library Details](#native-library-details)
  - [Library Location](#library-location)
  - [Platform-Specific Library Names](#platform-specific-library-names)
  - [Custom Library Path](#custom-library-path)
  - [Library Search Order](#library-search-order)
- [API Documentation](#api-documentation)
  - [GopherAgent](#gopheragent)
  - [ServerConfig](#serverconfig)
  - [Error Handling](#error-handling)
- [Examples](#examples)
  - [Basic Usage with API Key](#basic-usage-with-api-key)
  - [Using Local MCP Servers](#using-local-mcp-servers)
  - [Running the Example](#running-the-example)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Build Scripts](#build-scripts)
  - [Rebuilding Native Library](#rebuilding-native-library)
  - [Updating Submodules](#updating-submodules)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Links](#links)
- [Acknowledgments](#acknowledgments)

---

## Features

- **Native Performance** - Powered by C++ core with Python bindings via ctypes
- **AI Agent Framework** - Build intelligent agents with LLM integration
- **MCP Protocol** - Model Context Protocol client and server support
- **Tool Orchestration** - Manage and execute tools across multiple MCP servers
- **State Management** - Built-in state graph for complex workflows
- **Type Safety** - Full type hints and dataclass support

## When to Use This SDK

This SDK is ideal for:

- **Python applications** that need high-performance AI agent orchestration
- **Backend services** requiring MCP protocol support
- **Data science workflows** integrating AI agents
- **FastAPI/Flask services** adding AI capabilities
- **Jupyter notebooks** for interactive agent development

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Application                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                Python SDK (gopher_orch)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ GopherAgent │  │ ServerConfig│  │ Exception Classes   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │ FFI (ctypes)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Native Library (libgopher-orch)                │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐  │
│  │ Agent Engine  │  │ LLM Providers │  │ MCP Client      │  │
│  │               │  │ - Anthropic   │  │ - HTTP/SSE      │  │
│  │               │  │ - OpenAI      │  │ - Tool Registry │  │
│  └───────────────┘  └───────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Servers                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Weather API │  │ Database    │  │ Custom Tools        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Option 1: pip (when published)

```bash
pip install gopher-orch
```

### Option 2: Build from Source

See [Building from Source](#building-from-source) section below.

## Quick Start

```python
from gopher_orch import GopherAgent, GopherAgentConfig

# Create an agent with API key (fetches server config from remote API)
config = GopherAgentConfig(
    provider="AnthropicProvider",
    model="claude-3-haiku-20240307",
    api_key="your-api-key"
)

agent = GopherAgent.create(config)

# Run the agent
result = agent.run("What is the weather in Tokyo?")
print(result)

# Cleanup (optional - happens automatically)
agent.dispose()
```

Or use context manager for automatic cleanup:

```python
with GopherAgent.create(config) as agent:
    result = agent.run("What is the weather in Tokyo?")
    print(result)
```

---

## Building from Source

This SDK wraps a native C++ library via ctypes. You must build the native library before using the SDK.

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | >= 3.9 | With pip |
| Git | Latest | For cloning and submodules |
| CMake | >= 3.15 | Native library build system |
| C++ Compiler | C++14+ | Clang (macOS), GCC (Linux), MSVC (Windows) |

**Platform-specific requirements:**

- **macOS**: Xcode Command Line Tools (`xcode-select --install`)
- **Linux**: `build-essential`, `libssl-dev`
- **Windows**: Visual Studio 2019+ with C++ workload

### Step 1: Clone the Repository

```bash
git clone https://github.com/GopherSecurity/gopher-mcp-python.git
cd gopher-mcp-python
```

### Step 2: Build Everything

**Using build.sh (recommended)**

The `build.sh` script handles everything automatically:

```bash
./build.sh
```

**Using build.sh with Multiple GitHub Accounts:**

If you have multiple GitHub accounts configured with SSH host aliases, use the `GITHUB_SSH_HOST` environment variable:

```bash
# Use custom SSH host alias for cloning private submodules
GITHUB_SSH_HOST=your-ssh-alias ./build.sh

# Example: if your ~/.ssh/config has "Host github-work" for work account
GITHUB_SSH_HOST=github-work ./build.sh
```

**What happens during build:**

1. **Submodule update** - Initializes and updates submodules (with SSH URL rewriting if `GITHUB_SSH_HOST` is set)
2. **CMake configure** - Configures the C++ build with Release settings
3. **Native compilation** - Compiles C++ to shared libraries
4. **Library installation** - Copies libraries to `native/lib/`
5. **Dependency copying** - Copies required dependencies (gopher-mcp, fmt)
6. **Python setup** - Creates virtual environment and installs dependencies
7. **Tests** - Runs pytest tests
8. **Package** - Builds wheel/sdist

### Step 3: Verify the Build

```bash
# Check native libraries were built
ls -la native/lib/

# Expected output (macOS):
# libgopher-orch.dylib
# libgopher-mcp.dylib
# libgopher-mcp-event.dylib
# libfmt.dylib

# Verify Python installation
source .venv/bin/activate
python -c "from gopher_orch import GopherAgent; print('OK')"
```

### Step 4: Run Tests

```bash
source .venv/bin/activate
pytest
```

---

## Native Library Details

### Library Location

After building, native libraries are installed to:

```
native/
├── lib/                          # Shared libraries
│   ├── libgopher-orch.dylib     # Main orchestration library (macOS)
│   ├── libgopher-orch.so        # Main orchestration library (Linux)
│   ├── libgopher-mcp.dylib      # MCP protocol library
│   ├── libgopher-mcp-event.dylib # Event handling
│   └── libfmt.dylib             # Formatting library
└── include/                      # C++ headers (for development)
    └── orch/
        └── core/
```

### Platform-Specific Library Names

| Platform | Library Extension | Example |
|----------|------------------|---------|
| macOS | `.dylib` | `libgopher-orch.dylib` |
| Linux | `.so` | `libgopher-orch.so` |
| Windows | `.dll` | `gopher-orch.dll` |

### Custom Library Path

You can override the library search path using an environment variable:

```bash
export GOPHER_ORCH_LIBRARY_PATH=/path/to/libgopher-orch.dylib
```

### Library Search Order

The SDK searches for the native library in this order:

1. `GOPHER_ORCH_LIBRARY_PATH` environment variable
2. `native/lib/` relative to working directory
3. Relative to module location
4. System paths (`/usr/local/lib`, `/opt/homebrew/lib`, `/usr/lib`)

---

## API Documentation

### GopherAgent

The main class for creating and running AI agents:

```python
from gopher_orch import GopherAgent, GopherAgentConfig
from gopher_orch.result import AgentResult

# Initialize the library (called automatically on first create)
GopherAgent.init()

# Create with API key (fetches server config from remote API)
config = GopherAgentConfig(
    provider="AnthropicProvider",
    model="claude-3-haiku-20240307",
    api_key="your-api-key"
)
agent = GopherAgent.create(config)

# Or create with JSON server config
server_config = '''
{
    "succeeded": true,
    "data": {
        "servers": [{
            "serverId": "server1",
            "name": "My MCP Server",
            "transport": "http_sse",
            "config": {"url": "http://localhost:3001/mcp"}
        }]
    }
}
'''

agent = GopherAgent.create_with_server_config(
    "AnthropicProvider",
    "claude-3-haiku-20240307",
    server_config
)

# Run a query
result = agent.run("Your prompt here")

# Run with custom timeout (default: 60000ms)
result = agent.run("Your prompt here", timeout_ms=30000)

# Run with detailed result information
detailed: AgentResult = agent.run_detailed("Your prompt here")
# Returns AgentResult with: response, status, iteration_count, tokens_used

# Use as context manager (auto-cleanup)
with GopherAgent.create(config) as agent:
    result = agent.run("Your prompt")
# agent.dispose() called automatically

# Manual cleanup
agent.dispose()

# Shutdown library (optional - happens automatically on exit)
GopherAgent.shutdown()
```

### ServerConfig

Configuration options for the agent:

```python
from gopher_orch import GopherAgentConfig, GopherAgentConfigBuilder

# Direct construction
config = GopherAgentConfig(
    provider="AnthropicProvider",
    model="claude-3-haiku-20240307",
    api_key="your-api-key"  # OR server_config="..."
)

# Builder pattern
config = (
    GopherAgentConfigBuilder()
    .provider("AnthropicProvider")
    .model("claude-3-haiku-20240307")
    .api_key("your-api-key")
    .build()
)
```

### Error Handling

The SDK provides typed exceptions for different failure scenarios:

```python
from gopher_orch import GopherAgent
from gopher_orch.errors import (
    AgentException,
    ApiKeyException,
    ConnectionException,
    TimeoutException,
)

try:
    agent = GopherAgent.create(config)
    result = agent.run("query")
except ApiKeyException:
    print("Invalid API key")
except ConnectionException:
    print("Failed to connect to MCP servers")
except TimeoutException:
    print("Query timed out")
except AgentException as e:
    print(f"Agent error: {e}")
```

---

## Examples

### Basic Usage with API Key

```python
from gopher_orch import GopherAgent, GopherAgentConfig
import os

config = GopherAgentConfig(
    provider="AnthropicProvider",
    model="claude-3-haiku-20240307",
    api_key=os.environ.get("GOPHER_API_KEY")
)

agent = GopherAgent.create(config)
answer = agent.run("What time is it in London?")
print(f"Answer: {answer}")
agent.dispose()
```

### Using Local MCP Servers

```python
from gopher_orch import GopherAgent

SERVER_CONFIG = '''
{
    "succeeded": true,
    "code": 200,
    "message": "OK",
    "data": {
        "servers": [
            {
                "version": "1.0.0",
                "serverId": "weather-server",
                "name": "Weather Service",
                "transport": "http_sse",
                "config": {
                    "url": "http://localhost:3001/mcp",
                    "headers": {}
                },
                "connectTimeout": 5000,
                "requestTimeout": 30000
            }
        ]
    }
}
'''

agent = GopherAgent.create_with_server_config(
    "AnthropicProvider",
    "claude-3-haiku-20240307",
    SERVER_CONFIG
)

result = agent.run("What is the weather in New York?")
print(result)

agent.dispose()
```

### Running the Example

```bash
# Run with the convenience script (starts servers automatically)
cd examples
./client_example_json_run.sh

# Or manually:
# Terminal 1: Start server3001
cd examples/server3001 && npm install && npm run dev

# Terminal 2: Start server3002
cd examples/server3002 && npm install && npm run dev

# Terminal 3: Run the Python client
ANTHROPIC_API_KEY=your-key python examples/client_example_json.py
```

---

## Development

### Project Structure

```
gopher-mcp-python/
├── gopher_orch/
│   ├── __init__.py              # Package exports
│   ├── agent.py                 # Main GopherAgent class
│   ├── config.py                # Configuration classes
│   ├── result.py                # AgentResult and status enum
│   ├── errors.py                # Exception classes
│   └── ffi/                     # ctypes bindings
│       ├── __init__.py
│       └── library.py           # Native library wrapper
├── native/                      # Native libraries (generated)
│   ├── lib/                     # Shared libraries (.dylib, .so, .dll)
│   └── include/                 # C++ headers
├── third_party/                 # Git submodules
│   └── gopher-orch/             # C++ implementation
├── examples/                    # Example code
│   ├── client_example_json.py
│   ├── client_example_json_run.sh
│   ├── server3001/              # Mock weather MCP server
│   └── server3002/              # Mock tools MCP server
├── tests/                       # Test suite
│   ├── test_config.py
│   ├── test_result.py
│   ├── test_ffi.py
│   └── test_agent.py
├── build.sh                     # Build orchestration script
├── pyproject.toml               # Python package configuration
└── README.md
```

### Build Scripts

| Script | Description |
|--------|-------------|
| `./build.sh` | Full build (submodules + native + Python SDK) |
| `./build.sh --clean` | Clean CMake cache while preserving _deps |
| `./build.sh --clean --build` | Clean and rebuild |
| `GITHUB_SSH_HOST=alias ./build.sh` | Build with custom SSH host |
| `pytest` | Run tests |
| `ruff check .` | Lint Python code |
| `ruff format .` | Format Python code |
| `black .` | Format Python code (alternative) |

### Rebuilding Native Library

If you modify the C++ code or switch branches:

```bash
# Clean and rebuild (preserves downloaded dependencies)
./build.sh --clean --build
```

### Updating Submodules

To pull latest changes from native libraries:

```bash
# Update to latest commit
cd third_party/gopher-orch
git fetch origin
git checkout <commit-or-branch>
cd ../..

# Rebuild
./build.sh --clean --build
```

---

## Troubleshooting

### "Library not found" Error

**Cause**: Native library not built or not in expected location.

**Solution**:
```bash
# Rebuild native library
./build.sh

# Verify library exists
ls native/lib/libgopher-orch.*
```

### "Submodule is empty" Error

**Cause**: Git submodules not initialized.

**Solution**:
```bash
git submodule update --init --recursive
```

### CMake Configuration Fails

**Cause**: Missing dependencies or wrong CMake version.

**Solution**:
```bash
# macOS
brew install cmake

# Linux (Ubuntu/Debian)
sudo apt-get install cmake build-essential libssl-dev

# Verify version
cmake --version  # Should be >= 3.15
```

### OSError: Library Not Found at Runtime

**Cause**: ctypes can't find the native library.

**Solution**:
```bash
# Set library path explicitly
export GOPHER_ORCH_LIBRARY_PATH=/path/to/libgopher-orch.dylib

# Or run from project root
cd /path/to/gopher-mcp-python
python your_script.py
```

### Build Fails on Apple Silicon (M1/M2)

**Cause**: Architecture mismatch.

**Solution**:
```bash
# Ensure using native arm64 toolchain
arch -arm64 ./build.sh
```

---

## Contributing

Contributions are welcome! Please read our contributing guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Ensure submodules are initialized (`git submodule update --init --recursive`)
4. Make your changes
5. Run tests (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [GitHub Repository](https://github.com/GopherSecurity/gopher-mcp-python)
- [Java SDK](https://github.com/GopherSecurity/gopher-mcp-java)
- [TypeScript SDK](https://github.com/GopherSecurity/gopher-orch-js)
- [Native C++ Implementation](https://github.com/GopherSecurity/gopher-orch)
- [Model Context Protocol](https://modelcontextprotocol.io/)

## Acknowledgments

- Built on [gopher-orch](https://github.com/GopherSecurity/gopher-orch) C++ framework
- Uses [gopher-mcp](https://github.com/GopherSecurity/gopher-mcp) for MCP protocol
- Inspired by LangChain and LangGraph
- FFI bindings via [ctypes](https://docs.python.org/3/library/ctypes.html)
