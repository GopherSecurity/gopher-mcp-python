/**
 * @file client_example_json.ts
 * @brief TypeScript example using JSON server configuration
 */
import { GopherAgent } from '../dist/index.js';

// Server configuration for local MCP servers
const serverConfig = JSON.stringify({
  succeeded: true,
  code: 200000000,
  message: 'success',
  data: {
    servers: [
      {
        version: '2025-01-09',
        serverId: '1',
        name: 'server1',
        transport: 'http_sse',
        config: { url: 'http://127.0.0.1:3001/rpc', headers: {} },
        connectTimeout: 5000,
        requestTimeout: 30000,
      },
      {
        version: '2025-01-09',
        serverId: '2',
        name: 'server2',
        transport: 'http_sse',
        config: { url: 'http://127.0.0.1:3002/rpc', headers: {} },
        connectTimeout: 5000,
        requestTimeout: 30000,
      },
    ],
  },
});

async function main(): Promise<void> {
  const provider = 'AnthropicProvider';
  const model = 'claude-3-haiku-20240307';
  const agent = GopherAgent.create({ provider, model, serverConfig });
  console.log('GopherAgent created!');

  const args = process.argv.slice(2);
  const question = (args.length > 0)  ?
      args[0] : 'What is the weather like in New York?';
  console.log(`Question: ${question}`);
  const answer = agent.run(question);
  console.log('Answer:');
  console.log(answer);
}

main().catch(error => {
  console.error('Error:', (error as Error).message);
  process.exit(1);
});
