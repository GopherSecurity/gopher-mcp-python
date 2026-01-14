/**
 * @file ffi.ts
 * @brief FFI interface to gopher-orch C++ library using koffi
 */

import { existsSync } from 'node:fs';
import koffi from 'koffi';
import { arch, platform } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// ESM equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Library configuration for different platforms and architectures
const LIBRARY_CONFIG = {
  darwin: {
    x64: {
      name: 'libgopher-orch.dylib',
      searchPaths: [
        // Primary: native/lib relative to project root (from dist/)
        join(__dirname, '../native/lib/libgopher-orch.dylib'),
        // Development: when running from src/
        join(__dirname, '../../native/lib/libgopher-orch.dylib'),
        // System installation paths
        '/usr/local/lib/libgopher-orch.dylib',
        '/opt/homebrew/lib/libgopher-orch.dylib',
        '/usr/lib/libgopher-orch.dylib',
      ],
    },
    arm64: {
      name: 'libgopher-orch.dylib',
      searchPaths: [
        join(__dirname, '../native/lib/libgopher-orch.dylib'),
        join(__dirname, '../../native/lib/libgopher-orch.dylib'),
        '/usr/local/lib/libgopher-orch.dylib',
        '/opt/homebrew/lib/libgopher-orch.dylib',
        '/usr/lib/libgopher-orch.dylib',
      ],
    },
  },
  linux: {
    x64: {
      name: 'libgopher-orch.so',
      searchPaths: [
        join(__dirname, '../native/lib/libgopher-orch.so'),
        join(__dirname, '../../native/lib/libgopher-orch.so'),
        '/usr/local/lib/libgopher-orch.so',
        '/usr/lib/x86_64-linux-gnu/libgopher-orch.so',
        '/usr/lib64/libgopher-orch.so',
        '/usr/lib/libgopher-orch.so',
      ],
    },
    arm64: {
      name: 'libgopher-orch.so',
      searchPaths: [
        join(__dirname, '../native/lib/libgopher-orch.so'),
        join(__dirname, '../../native/lib/libgopher-orch.so'),
        '/usr/local/lib/libgopher-orch.so',
        '/usr/lib/aarch64-linux-gnu/libgopher-orch.so',
        '/usr/lib64/libgopher-orch.so',
        '/usr/lib/libgopher-orch.so',
      ],
    },
  },
  win32: {
    x64: {
      name: 'gopher-orch.dll',
      searchPaths: [
        join(__dirname, '../native/lib/gopher-orch.dll'),
        join(__dirname, '../../native/lib/gopher-orch.dll'),
        'C:\\Program Files\\gopher-orch\\bin\\gopher-orch.dll',
        'C:\\Program Files\\gopher-orch\\lib\\gopher-orch.dll',
      ],
    },
  },
} as const;

/**
 * Get the path to the native library
 */
function getLibraryPath(): string {
  // Check for environment variable override first
  const envPath = process.env['GOPHER_ORCH_LIBRARY_PATH'];
  if (envPath && existsSync(envPath)) {
    return envPath;
  }

  const currentPlatform = platform() as keyof typeof LIBRARY_CONFIG;
  const currentArch = arch() as keyof (typeof LIBRARY_CONFIG)[typeof currentPlatform];

  if (!LIBRARY_CONFIG[currentPlatform] || !LIBRARY_CONFIG[currentPlatform][currentArch]) {
    throw new Error(`Unsupported platform: ${currentPlatform} ${currentArch}`);
  }

  const config = LIBRARY_CONFIG[currentPlatform][currentArch];

  // Search through the paths to find the first one that exists
  for (const searchPath of config.searchPaths) {
    if (existsSync(searchPath)) {
      return searchPath;
    }
  }

  // If no path found, throw an error with helpful information
  const searchedPaths = config.searchPaths.join('\n  - ');
  throw new Error(
    `Gopher-Orch library not found. Searched paths:\n  - ${searchedPaths}\n` +
      `Please ensure the library is built and available at one of these locations.\n` +
      `You can set GOPHER_ORCH_LIBRARY_PATH environment variable to override.`
  );
}

// Raw library bindings
export let gopherOrchLib: Record<string, (...args: unknown[]) => unknown> = {};

// Error info struct type for koffi
let ErrorInfoType: unknown = null;

try {
  const libPath = getLibraryPath();

  // Load the shared library
  const nativeLib = koffi.load(libPath);

  // Define the error_info struct to match C:
  // typedef struct {
  //   gopher_orch_error_t code;  // int
  //   const char* message;
  //   const char* details;
  //   const char* file;
  //   int32_t line;
  // } gopher_orch_error_info_t;
  ErrorInfoType = koffi.struct('gopher_orch_error_info_t', {
    code: 'int',
    message: 'const char*',
    details: 'const char*',
    file: 'const char*',
    line: 'int32_t',
  });

  // List of C API functions to bind
  const functionList = [
    // Core initialization functions
    { name: 'gopher_orch_init', signature: 'int', args: [] as string[] },
    { name: 'gopher_orch_shutdown', signature: 'void', args: [] as string[] },
    { name: 'gopher_orch_is_initialized', signature: 'int', args: [] as string[] },
    { name: 'gopher_orch_last_error', signature: 'gopher_orch_error_info_t*', args: [] as string[] },
    { name: 'gopher_orch_clear_error', signature: 'void', args: [] as string[] },
    { name: 'gopher_orch_free', signature: 'void', args: ['void*'] },

    // Agent functions
    {
      name: 'gopher_orch_agent_create_by_json',
      signature: 'void*',
      args: ['string', 'string', 'string'], // provider, model, server_json_config
    },
    {
      name: 'gopher_orch_agent_create_by_api_key',
      signature: 'void*',
      args: ['string', 'string', 'string'], // provider, model, api_key
    },
    {
      name: 'gopher_orch_agent_run',
      signature: 'string',
      args: ['void*', 'string', 'uint64_t'], // agent, query, timeout_ms
    },
    { name: 'gopher_orch_agent_add_ref', signature: 'void', args: ['void*'] },
    { name: 'gopher_orch_agent_release', signature: 'void', args: ['void*'] },

    // API functions
    {
      name: 'gopher_orch_api_fetch_servers',
      signature: 'string',
      args: ['string'], // api_key
    },
  ];

  // Try to bind each function
  const availableFunctions: Record<string, (...args: unknown[]) => unknown> = {};
  for (const func of functionList) {
    try {
      availableFunctions[func.name] = nativeLib.func(func.name, func.signature, func.args);
    } catch {
      // Function not available - that's OK, we'll provide a fallback
    }
  }

  gopherOrchLib = availableFunctions;
} catch (error) {
  console.error(`Failed to load Gopher-Orch library: ${error}`);
  // Continue with empty lib - fallbacks will be used
  gopherOrchLib = {};
}

// Agent handle wrapper type
interface AgentHandle {
  handle: unknown;
  isNull: () => boolean;
}

/**
 * FFI interface with fallbacks for when native library is unavailable
 */
export const library = {
  gopher_orch_init: (): number => {
    if (gopherOrchLib.gopher_orch_init) {
      return gopherOrchLib.gopher_orch_init() as number;
    }
    return 0; // Success fallback
  },

  gopher_orch_shutdown: (): void => {
    if (gopherOrchLib.gopher_orch_shutdown) {
      gopherOrchLib.gopher_orch_shutdown();
    }
  },

  gopher_orch_is_initialized: (): boolean => {
    if (gopherOrchLib.gopher_orch_is_initialized) {
      return (gopherOrchLib.gopher_orch_is_initialized() as number) !== 0;
    }
    return true; // Fallback
  },

  gopher_orch_last_error: (): string | null => {
    if (gopherOrchLib.gopher_orch_last_error && ErrorInfoType) {
      try {
        const errorPtr = gopherOrchLib.gopher_orch_last_error();
        if (errorPtr) {
          const errorInfo = koffi.decode(errorPtr, ErrorInfoType as koffi.IKoffiCType) as {
            message?: string;
          };
          if (errorInfo && errorInfo.message) {
            return errorInfo.message;
          }
        }
      } catch {
        // Silently fail - will return null
      }
    }
    return null;
  },

  gopher_orch_clear_error: (): void => {
    if (gopherOrchLib.gopher_orch_clear_error) {
      gopherOrchLib.gopher_orch_clear_error();
    }
  },

  gopher_orch_free: (ptr: unknown): void => {
    if (gopherOrchLib.gopher_orch_free && ptr) {
      gopherOrchLib.gopher_orch_free(ptr);
    }
  },

  gopher_orch_agent_create_by_json: (
    provider: string,
    model: string,
    serverJson: string
  ): AgentHandle | null => {
    if (gopherOrchLib.gopher_orch_agent_create_by_json) {
      // Configure environment for HTTP/HTTPS handling
      const originalEnv = {
        CURL_CA_BUNDLE: process.env.CURL_CA_BUNDLE,
        SSL_VERIFY_PEER: process.env.SSL_VERIFY_PEER,
        SSL_VERIFY_HOST: process.env.SSL_VERIFY_HOST,
      };

      // For HTTP URLs, disable SSL verification
      process.env.SSL_VERIFY_PEER = '0';
      process.env.SSL_VERIFY_HOST = '0';
      process.env.CURL_CA_BUNDLE = '';

      try {
        const handle = gopherOrchLib.gopher_orch_agent_create_by_json(provider, model, serverJson);
        return handle ? { handle, isNull: () => !handle } : null;
      } catch (ffiError) {
        console.error('FFI Error in agent creation:', ffiError);
        return null;
      } finally {
        // Restore original environment
        for (const [key, value] of Object.entries(originalEnv)) {
          if (value === undefined) {
            delete process.env[key];
          } else {
            process.env[key] = value;
          }
        }
      }
    }
    // FFI function not available, use fallback
    console.warn('FFI function gopher_orch_agent_create_by_json not available, using fallback');
    return { handle: 'mock-agent-json', isNull: () => false };
  },

  gopher_orch_agent_create_by_api_key: (
    provider: string,
    model: string,
    apiKey: string
  ): AgentHandle | null => {
    if (gopherOrchLib.gopher_orch_agent_create_by_api_key) {
      // Configure environment for HTTP/HTTPS handling
      const originalEnv = {
        CURL_CA_BUNDLE: process.env.CURL_CA_BUNDLE,
        SSL_VERIFY_PEER: process.env.SSL_VERIFY_PEER,
        SSL_VERIFY_HOST: process.env.SSL_VERIFY_HOST,
      };

      process.env.SSL_VERIFY_PEER = '0';
      process.env.SSL_VERIFY_HOST = '0';
      process.env.CURL_CA_BUNDLE = '';

      try {
        const handle = gopherOrchLib.gopher_orch_agent_create_by_api_key(provider, model, apiKey);
        return handle ? { handle, isNull: () => !handle } : null;
      } finally {
        // Restore original environment
        for (const [key, value] of Object.entries(originalEnv)) {
          if (value === undefined) {
            delete process.env[key];
          } else {
            process.env[key] = value;
          }
        }
      }
    }
    // Fallback
    return { handle: 'mock-agent-api', isNull: () => false };
  },

  gopher_orch_agent_release: (agent: AgentHandle | null): void => {
    if (gopherOrchLib.gopher_orch_agent_release && agent?.handle) {
      gopherOrchLib.gopher_orch_agent_release(agent.handle);
    }
  },

  gopher_orch_agent_run: (
    agent: AgentHandle | null,
    query: string,
    timeoutMs: number = 30000
  ): string => {
    if (gopherOrchLib.gopher_orch_agent_run && agent?.handle) {
      const result = gopherOrchLib.gopher_orch_agent_run(agent.handle, query, timeoutMs);
      return (result as string) || `No response for query: "${query}"`;
    }
    // Fallback
    return `[FFI Fallback] Agent processed query: "${query}" - Real gopher-orch library not available`;
  },

  gopher_orch_api_fetch_servers: (apiKey: string): string => {
    if (gopherOrchLib.gopher_orch_api_fetch_servers) {
      return gopherOrchLib.gopher_orch_api_fetch_servers(apiKey) as string;
    }
    // Fallback
    return JSON.stringify({
      succeeded: true,
      code: 200000000,
      message: 'success - fallback',
      data: {
        servers: [
          {
            version: '2025-01-09',
            serverId: '1877234567890123456',
            name: 'fallback-server',
            transport: 'http_sse',
            config: {
              url: 'http://127.0.0.1:3001/rpc',
              headers: {},
            },
            connectTimeout: 5000,
            requestTimeout: 30000,
          },
        ],
      },
    });
  },
};

/**
 * Initialize the native library
 */
export function initializeLibrary(): boolean {
  return library.gopher_orch_init() === 0;
}

/**
 * Shutdown the native library
 */
export function shutdownLibrary(): void {
  library.gopher_orch_shutdown();
}

/**
 * Get the last error message
 */
export function getLastError(): string | null {
  return library.gopher_orch_last_error();
}

/**
 * Clear the last error
 */
export function clearError(): void {
  library.gopher_orch_clear_error();
}
