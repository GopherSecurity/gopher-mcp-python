/**
 * @file agent.ts
 * @brief TypeScript wrapper for GopherAgent functionality
 */

import { library, initializeLibrary, shutdownLibrary } from './ffi.js';
import {
  AgentResult,
  AgentError,
  ApiKeyError,
  TimeoutError,
  ApiResponse,
} from './types.js';

/**
 * Configuration options for creating a GopherAgent
 */
export interface GopherAgentConfig {
  /** Provider name (e.g., "AnthropicProvider") */
  provider: string;
  /** Model name (e.g., "claude-3-haiku-20240307") */
  model: string;
  /** API key for fetching remote server config (mutually exclusive with serverConfig) */
  apiKey?: string;
  /** JSON server configuration (mutually exclusive with apiKey) */
  serverConfig?: string;
}

// Agent handle type
interface AgentHandle {
  handle: unknown;
  isNull: () => boolean;
}

/**
 * GopherAgent - Main entry point for the gopher-orch TypeScript SDK
 *
 * Provides a clean, TypeScript-friendly interface to the gopher-orch agent functionality.
 *
 * @example
 * ```typescript
 * import { GopherAgent } from "@gopher/orch";
 *
 * // Create an agent with API key
 * const agent = GopherAgent.create({
 *   provider: 'AnthropicProvider',
 *   model: 'claude-3-haiku-20240307',
 *   apiKey: 'your-api-key'
 * });
 *
 * // Run a query
 * const answer = agent.run("What time is it in Tokyo?");
 * console.log(answer);
 *
 * // Cleanup (optional - happens automatically on exit)
 * agent.dispose();
 * ```
 */
export class GopherAgent {
  private handle: AgentHandle | null;
  private disposed: boolean = false;
  private static initialized: boolean = false;

  private constructor(handle: AgentHandle) {
    this.handle = handle;
  }

  /**
   * Initialize the gopher-orch library
   * Must be called before creating any agents
   *
   * @throws {AgentError} If initialization fails
   */
  static init(): void {
    if (GopherAgent.initialized) {
      return;
    }

    const success = initializeLibrary();
    if (!success) {
      throw new AgentError('Failed to initialize gopher-orch library');
    }

    library.gopher_orch_init();
    GopherAgent.initialized = true;

    // Setup automatic cleanup on process exit
    GopherAgent.setupCleanupHandlers();
  }

  /**
   * Shutdown the gopher-orch library
   * Called automatically on process exit, but can be called manually
   */
  static shutdown(): void {
    if (GopherAgent.initialized) {
      shutdownLibrary();
      GopherAgent.initialized = false;
    }
  }

  /**
   * Check if the library is initialized
   */
  static isInitialized(): boolean {
    return GopherAgent.initialized;
  }

  /**
   * Create a new GopherAgent instance
   *
   * @param config Configuration options
   * @returns GopherAgent instance
   * @throws {AgentError} If agent creation fails
   *
   * @example
   * ```typescript
   * // Create with API key (fetches server config from remote API)
   * const agent = GopherAgent.create({
   *   provider: 'AnthropicProvider',
   *   model: 'claude-3-haiku-20240307',
   *   apiKey: 'your-api-key'
   * });
   *
   * // Or create with JSON server config
   * const agent = GopherAgent.create({
   *   provider: 'AnthropicProvider',
   *   model: 'claude-3-haiku-20240307',
   *   serverConfig: '{"succeeded": true, "data": {...}}'
   * });
   * ```
   */
  static create(config: GopherAgentConfig): GopherAgent {
    if (!GopherAgent.initialized) {
      GopherAgent.init();
    }

    const { provider, model, apiKey, serverConfig } = config;

    if (!provider || !model) {
      throw new AgentError('Provider and model are required');
    }

    if (apiKey && serverConfig) {
      throw new AgentError('Cannot specify both apiKey and serverConfig');
    }

    if (!apiKey && !serverConfig) {
      throw new AgentError('Either apiKey or serverConfig is required');
    }

    let handle: AgentHandle | null;

    try {
      if (apiKey) {
        handle = library.gopher_orch_agent_create_by_api_key(provider, model, apiKey);
      } else {
        handle = library.gopher_orch_agent_create_by_json(provider, model, serverConfig!);
      }

      if (!handle || handle.isNull()) {
        // Try to get error message from FFI layer
        const lastError = library.gopher_orch_last_error();
        const errorMsg = lastError ? String(lastError) : 'Failed to create agent';
        library.gopher_orch_clear_error();
        throw new AgentError(errorMsg);
      }

      return new GopherAgent(handle);
    } catch (error) {
      if (error instanceof AgentError) {
        throw error;
      }
      throw new AgentError(`Failed to create agent: ${(error as Error).message}`);
    }
  }

  /**
   * Run a query against the agent
   *
   * @param query The user query to process
   * @param timeoutMs Optional timeout in milliseconds (default: 60000)
   * @returns The agent's response
   * @throws {AgentError} If the query fails
   */
  run(query: string, timeoutMs: number = 60000): string {
    this.ensureNotDisposed();

    try {
      const response = library.gopher_orch_agent_run(this.handle, query, timeoutMs);
      return response;
    } catch (error) {
      throw new AgentError(`Query execution failed: ${(error as Error).message}`);
    }
  }

  /**
   * Run a query with detailed result information
   *
   * @param query The user query to process
   * @param timeoutMs Optional timeout in milliseconds
   * @returns AgentResult with response and metadata
   */
  runDetailed(query: string, timeoutMs: number = 60000): AgentResult {
    try {
      const response = this.run(query, timeoutMs);

      return {
        response,
        status: 'success',
        iterationCount: 1,
        tokensUsed: 0,
      };
    } catch (error) {
      if (error instanceof TimeoutError) {
        return {
          response: error.message,
          status: 'timeout',
        };
      } else {
        return {
          response: (error as Error).message,
          status: 'error',
        };
      }
    }
  }

  /**
   * Dispose of the agent and free resources
   */
  dispose(): void {
    if (!this.disposed) {
      if (this.handle) {
        library.gopher_orch_agent_release(this.handle);
        this.handle = null;
      }
      this.disposed = true;
    }
  }

  /**
   * Check if agent is disposed
   */
  isDisposed(): boolean {
    return this.disposed;
  }

  private ensureNotDisposed(): void {
    if (this.disposed) {
      throw new AgentError('Agent has been disposed');
    }
  }

  private static setupCleanupHandlers(): void {
    const cleanup = () => {
      GopherAgent.shutdown();
    };

    process.on('exit', cleanup);
    process.on('SIGTERM', () => {
      cleanup();
      process.exit(0);
    });
    process.on('SIGINT', () => {
      cleanup();
      process.exit(0);
    });
  }
}

// Backward compatibility alias
export { GopherAgent as ReActAgent };

/**
 * Utility functions for working with server configurations
 */
export class ServerConfig {
  /**
   * Fetch MCP server configurations from remote API
   *
   * @param apiKey API key for authentication
   * @returns Server configuration JSON string
   */
  static fetch(apiKey: string): string {
    if (!GopherAgent.isInitialized()) {
      GopherAgent.init();
    }

    try {
      if (!apiKey || apiKey.trim().length === 0) {
        throw new ApiKeyError('Invalid or missing API key');
      }

      return library.gopher_orch_api_fetch_servers(apiKey);
    } catch (error) {
      if (error instanceof AgentError) {
        throw error;
      }
      throw new AgentError(`Failed to fetch servers: ${(error as Error).message}`);
    }
  }

  /**
   * Create default server configuration for local development
   */
  static createDefault(): string {
    const defaultConfig: ApiResponse = {
      succeeded: true,
      code: 200000000,
      message: 'success',
      data: {
        servers: [
          {
            version: '2025-01-09',
            serverId: '1877234567890123456',
            name: 'local-dev-server',
            transport: 'http_sse',
            config: {
              url: 'http://127.0.0.1:3001/rpc',
              headers: {},
            },
            connectTimeout: 5000,
            requestTimeout: 30000,
          },
          {
            version: '2025-01-09',
            serverId: '1877234567890123457',
            name: 'local-dev-server2',
            transport: 'http_sse',
            config: {
              url: 'http://127.0.0.1:3002/rpc',
              headers: {},
            },
            connectTimeout: 5000,
            requestTimeout: 30000,
          },
        ],
      },
    };

    return JSON.stringify(defaultConfig);
  }
}

// Backward compatibility alias
export { ServerConfig as ServerConfigHelper };
