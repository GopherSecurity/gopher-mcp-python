# @gopher/orch - TypeScript SDK

TypeScript SDK for Gopher Orch - AI Agent orchestration framework with native C++ performance.

## Features

- 🚀 **Native Performance** - Powered by C++ core with TypeScript bindings
- 🤖 **AI Agent Framework** - Build intelligent agents with LLM integration
- 🔌 **MCP Protocol** - Model Context Protocol client and server support
- 🔧 **Tool Orchestration** - Manage and execute tools across multiple servers
- 🔄 **State Management** - Built-in state graph for complex workflows
- 💪 **Type Safety** - Full TypeScript type definitions

## Installation

```bash
npm install @gopher/orch
```

## Quick Start

```typescript
import { GopherAgent } from '@gopher/orch';

// Create an agent with API key (fetches server config from remote API)
const agent = GopherAgent.create({
  provider: 'AnthropicProvider',
  model: 'claude-3-haiku-20240307',
  apiKey: 'your-api-key'
});

// Run the agent
const result = agent.run('What is the weather in Tokyo?');
console.log(result);

// Cleanup (optional - happens automatically on exit)
agent.dispose();
```

## Architecture

```
TypeScript SDK (gopher-orch-js)
     |
     | FFI Bindings
     v
Native Library (gopher-orch)
     |
     +-- Agent Framework
     +-- LLM Providers (Anthropic, OpenAI)
     +-- MCP Client/Server
     +-- Tool Registry
     +-- State Graph
```

## Building from Source

### Prerequisites

- Node.js >= 16
- CMake >= 3.15
- C++14 compatible compiler
- Git

### Build Steps

```bash
# Clone the repository
git clone https://github.com/GopherSecurity/gopher-orch-js.git
cd gopher-orch-js

# Initialize submodules
git submodule update --init --recursive

# Build native library and TypeScript
npm install
npm run build

# Run tests
npm test
```

## API Documentation

### GopherAgent

The main class for creating and running AI agents:

```typescript
import { GopherAgent } from '@gopher/orch';

// Initialize the library (called automatically on first create)
GopherAgent.init();

// Create with API key (fetches server config from remote API)
const agent = GopherAgent.create({
  provider: 'AnthropicProvider',
  model: 'claude-3-haiku-20240307',
  apiKey: 'your-api-key'
});

// Or create with JSON server config
const agent = GopherAgent.create({
  provider: 'AnthropicProvider',
  model: 'claude-3-haiku-20240307',
  serverConfig: '{"succeeded": true, "data": {...}}'
});

// Run a query
const result = agent.run('Your prompt here');

// Run with custom timeout (default: 60000ms)
const result = agent.run('Your prompt here', 30000);

// Run with detailed result information
const detailed = agent.runDetailed('Your prompt here');
// Returns: { response, status: 'success' | 'error' | 'timeout', iterationCount?, tokensUsed? }

// Cleanup (optional - happens automatically on exit)
agent.dispose();

// Shutdown library (optional - happens automatically on exit)
GopherAgent.shutdown();
```

### ServerConfig

Utility class for working with server configurations:

```typescript
import { ServerConfig } from '@gopher/orch';

// Fetch MCP server configurations from remote API
const config = ServerConfig.fetch('your-api-key');

// Create default configuration for local development
const defaultConfig = ServerConfig.createDefault();
```

### Error Handling

The SDK provides typed errors for different failure scenarios:

```typescript
import { AgentError, ApiKeyError, ConnectionError, TimeoutError } from '@gopher/orch';

try {
  const agent = GopherAgent.create({ provider, model, apiKey });
  const result = agent.run('query');
} catch (error) {
  if (error instanceof ApiKeyError) {
    console.error('Invalid API key');
  } else if (error instanceof ConnectionError) {
    console.error('Failed to connect to MCP servers');
  } else if (error instanceof TimeoutError) {
    console.error('Query timed out');
  } else if (error instanceof AgentError) {
    console.error('Agent error:', error.message);
  }
}
```

## Examples

### Basic Usage with API Key

```typescript
import { GopherAgent } from '@gopher/orch';

async function main() {
  // Create agent with API key (fetches server config from remote API)
  const agent = GopherAgent.create({
    provider: 'AnthropicProvider',
    model: 'claude-3-haiku-20240307',
    apiKey: 'your-api-key'
  });

  const question = 'What time is it in London?';
  console.log(`Question: ${question}`);

  const answer = agent.run(question);
  console.log('Answer:', answer);

  // Cleanup (optional - happens automatically on exit)
  agent.dispose();
}

main().catch(error => {
  console.error('Error:', error.message);
  process.exit(1);
});
```

### Using JSON Server Config

```typescript
import { GopherAgent, ServerConfig } from '@gopher/orch';

// Use default local development config
const serverConfig = ServerConfig.createDefault();

const agent = GopherAgent.create({
  provider: 'AnthropicProvider',
  model: 'claude-3-haiku-20240307',
  serverConfig: serverConfig
});

const result = agent.run('What is 2 + 2?');
console.log(result);

agent.dispose();
```

### With Detailed Results

```typescript
import { GopherAgent } from '@gopher/orch';

const agent = GopherAgent.create({
  provider: 'AnthropicProvider',
  model: 'claude-3-haiku-20240307',
  apiKey: 'your-api-key'
});

const result = agent.runDetailed('Explain quantum computing');

if (result.status === 'success') {
  console.log('Response:', result.response);
  console.log('Iterations:', result.iterationCount);
} else if (result.status === 'timeout') {
  console.log('Query timed out');
} else {
  console.log('Error:', result.response);
}

agent.dispose();
```

## Development

### Project Structure

```
gopher-orch-js/
├── src/                    # TypeScript source
│   ├── agent/             # Agent implementation
│   ├── llm/               # LLM provider interfaces
│   ├── mcp/               # MCP client/server
│   ├── tools/             # Tool management
│   ├── native/            # FFI bindings
│   └── index.ts           # Main entry point
├── native/                # Built native libraries
│   ├── lib/               # Shared libraries (.dylib, .so)
│   └── include/           # C++ headers
├── third_party/           # Native dependencies
│   └── gopher-orch/       # C++ implementation (submodule)
├── dist/                  # Compiled TypeScript
├── build.sh               # Native build script
├── package.json           # NPM configuration
└── tsconfig.json          # TypeScript configuration
```

### Build Scripts

- `npm run build:native` - Build native C++ library
- `npm run build` - Build TypeScript (automatically builds native first)
- `npm run watch` - Watch mode for TypeScript
- `npm test` - Run tests
- `npm run lint` - Lint TypeScript code
- `npm run clean` - Clean all build artifacts

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run specific test file
npm test -- agent.test.ts
```

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [GitHub Repository](https://github.com/GopherSecurity/gopher-orch-js)
- [Native C++ Implementation](https://github.com/GopherSecurity/gopher-orch)
- [Documentation](https://github.com/GopherSecurity/gopher-orch-js/docs)
- [Examples](https://github.com/GopherSecurity/gopher-orch-js/examples)

## Support

- GitHub Issues: [Report a bug](https://github.com/GopherSecurity/gopher-orch-js/issues)
- Discussions: [Ask a question](https://github.com/GopherSecurity/gopher-orch-js/discussions)

## Acknowledgments

- Built on top of [gopher-orch](https://github.com/GopherSecurity/gopher-orch) C++ framework
- Inspired by LangChain and LangGraph
- Uses [Model Context Protocol](https://modelcontextprotocol.io/)
