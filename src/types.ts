/**
 * @file types.ts
 * @brief TypeScript type definitions for gopher-orch SDK
 */

/**
 * MCP server configuration
 */
export interface ServerConfig {
  version: string;
  serverId: string;
  name: string;
  transport: string;
  config: {
    url: string;
    headers: Record<string, string>;
  };
  connectTimeout: number;
  requestTimeout: number;
}

/**
 * API response structure from server config fetch
 */
export interface ApiResponse {
  succeeded: boolean;
  code: number;
  message: string;
  data: {
    servers: ServerConfig[];
  };
}

/**
 * Agent configuration options
 */
export interface AgentConfig {
  provider: string;
  model: string;
  systemPrompt?: string;
  maxIterations?: number;
  temperature?: number;
}

/**
 * Result from agent query execution
 */
export interface AgentResult {
  response: string;
  status: 'success' | 'error' | 'timeout';
  iterationCount?: number;
  tokensUsed?: number;
}

/**
 * Base error class for agent operations
 */
export class AgentError extends Error {
  constructor(message: string, public code?: string) {
    super(message);
    this.name = 'AgentError';
  }
}

/**
 * Error for API key related issues
 */
export class ApiKeyError extends AgentError {
  constructor(message: string = 'Invalid or missing API key') {
    super(message, 'API_KEY_ERROR');
    this.name = 'ApiKeyError';
  }
}

/**
 * Error for MCP server connection issues
 */
export class ConnectionError extends AgentError {
  constructor(message: string = 'Failed to connect to MCP servers') {
    super(message, 'CONNECTION_ERROR');
    this.name = 'ConnectionError';
  }
}

/**
 * Error for operation timeout
 */
export class TimeoutError extends AgentError {
  constructor(message: string = 'Agent execution timed out') {
    super(message, 'TIMEOUT_ERROR');
    this.name = 'TimeoutError';
  }
}
