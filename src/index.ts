/**
 * @file index.ts
 * @brief Main entry point for @gopher/orch TypeScript SDK
 *
 * @example
 * ```typescript
 * import { GopherAgent } from '@gopher/orch';
 *
 * const agent = GopherAgent.create({
 *   provider: 'AnthropicProvider',
 *   model: 'claude-3-haiku-20240307',
 *   apiKey: 'your-api-key'
 * });
 *
 * const answer = agent.run('What time is it in Tokyo?');
 * console.log(answer);
 *
 * agent.dispose();
 * ```
 */

// Main classes
export { GopherAgent, GopherAgentConfig, ServerConfig } from './agent.js';

// Backward compatibility aliases
export { ReActAgent, ServerConfigHelper } from './agent.js';

// Type definitions
export * from './types.js';

// Low-level FFI access for advanced usage
export { library, initializeLibrary, shutdownLibrary, getLastError, clearError } from './ffi.js';

// Version
export const version = '0.1.0';
