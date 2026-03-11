# Python Auth MCP Server Example

OAuth-protected MCP (Model Context Protocol) server implementation in Python using gopher-auth FFI bindings for JWT token validation.

## Overview

This example demonstrates:
- OAuth 2.0 protected MCP server using JSON-RPC 2.0
- JWT token validation via gopher-auth native library (FFI)
- OAuth discovery endpoints (RFC 9728, RFC 8414, OIDC)
- Scope-based access control for MCP tools
- Integration with Keycloak or compatible OAuth providers

## Prerequisites

- Python 3.10+
- pip
- Compiled `libgopher-orch` from gopher-orch (for production use)
- Keycloak or compatible OAuth 2.0 server (optional, for auth testing)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or install with development dependencies
pip install -e ".[dev]"

# Copy libgopher-orch to lib/ (from gopher-orch build)
# macOS:
cp /path/to/gopher-orch/build/lib/libgopher-orch.dylib ./lib/

# Linux:
cp /path/to/gopher-orch/build/lib/libgopher-orch.so ./lib/
```

## Building the Native Library

Build libgopher-orch from gopher-orch:

```bash
cd /path/to/gopher-orch
mkdir -p build && cd build
cmake -DBUILD_SHARED_LIBS=ON ..
make gopher-orch

# Copy to this example
cp lib/libgopher-orch.* /path/to/gopher-mcp-python/examples/auth/lib/
```

## Configuration

Create or modify `server.config`:

### Auth Disabled Mode (Development/Testing)

```ini
# Server settings
host=0.0.0.0
port=3001
server_url=http://localhost:3001

# Disable auth for development
auth_disabled=true
```

### Auth Enabled Mode (Production)

```ini
# Server settings
host=0.0.0.0
port=3001
server_url=http://localhost:3001

# OAuth/IDP settings (Keycloak example)
auth_server_url=https://keycloak.example.com/realms/mcp
client_id=mcp-client
client_secret=your-client-secret

# Optional: Override derived endpoints
# jwks_uri=https://keycloak.example.com/realms/mcp/protocol/openid-connect/certs
# issuer=https://keycloak.example.com/realms/mcp
# oauth_authorize_url=https://keycloak.example.com/realms/mcp/protocol/openid-connect/auth
# oauth_token_url=https://keycloak.example.com/realms/mcp/protocol/openid-connect/token

# Token validation settings
allowed_scopes=openid profile email mcp:read mcp:admin
jwks_cache_duration=3600
jwks_auto_refresh=true
request_timeout=30
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `host` | Server bind address | `0.0.0.0` |
| `port` | Server port | `3001` |
| `server_url` | Public server URL | `http://localhost:{port}` |
| `auth_server_url` | OAuth server base URL | - |
| `jwks_uri` | JWKS endpoint URL | Derived from auth_server_url |
| `issuer` | Expected token issuer | Derived from auth_server_url |
| `client_id` | OAuth client ID | - |
| `client_secret` | OAuth client secret | - |
| `allowed_scopes` | Space-separated allowed scopes | `openid profile email mcp:read mcp:admin` |
| `jwks_cache_duration` | JWKS cache TTL in seconds | `3600` |
| `jwks_auto_refresh` | Auto-refresh JWKS before expiry | `true` |
| `request_timeout` | HTTP request timeout in seconds | `30` |
| `auth_disabled` | Disable authentication entirely | `false` |

## Running the Server

### Development Mode

```bash
# Run directly with Python
python -m py_auth_mcp_server

# Or with custom config
python -m py_auth_mcp_server /path/to/custom.config

# Override options
python -m py_auth_mcp_server --no-auth
python -m py_auth_mcp_server --host 127.0.0.1 --port 8080
```

### Using Flask Development Server

```bash
# Set environment variables
export FLASK_APP=py_auth_mcp_server.app:create_app
export FLASK_ENV=development

# Run with Flask
flask run --port 3001
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=py_auth_mcp_server

# Run specific test file
pytest tests/test_integration.py

# Run with verbose output
pytest -v
```

## API Endpoints

### Health Check

```bash
curl http://localhost:3001/health
```

Response:
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00.000000+00:00",
  "version": "1.0.0",
  "uptime": 123
}
```

### OAuth Discovery

```bash
# Protected Resource Metadata (RFC 9728)
curl http://localhost:3001/.well-known/oauth-protected-resource

# Authorization Server Metadata (RFC 8414)
curl http://localhost:3001/.well-known/oauth-authorization-server

# OpenID Configuration
curl http://localhost:3001/.well-known/openid-configuration
```

### MCP Tools

#### Without Authentication (auth_disabled=true)

```bash
# Initialize session
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}'

# List available tools
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}'

# Get weather (no auth required)
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get-weather", "arguments": {"city": "Seattle"}}}'
```

#### With Authentication

```bash
# Get an access token from your OAuth provider first
TOKEN="your-jwt-token"

# Get forecast (requires mcp:read scope)
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get-forecast", "arguments": {"city": "Portland"}}}'

# Get weather alerts (requires mcp:admin scope)
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get-weather-alerts", "arguments": {"region": "Pacific Northwest"}}}'
```

## Available Tools

| Tool | Description | Required Scope |
|------|-------------|----------------|
| `get-weather` | Current weather for a city | None |
| `get-forecast` | 5-day forecast for a city | `mcp:read` |
| `get-weather-alerts` | Weather alerts for a region | `mcp:admin` |

## Authentication Flow

```
+----------+     +--------------+     +-------------+
|  Client  |     |  MCP Server  |     |  Keycloak   |
+----+-----+     +------+-------+     +------+------+
     |                  |                    |
     |  GET /.well-known/oauth-protected-resource
     |----------------->|                    |
     |  { authorization_servers: [...] }     |
     |<-----------------|                    |
     |                  |                    |
     |  GET /.well-known/oauth-authorization-server
     |----------------->|                    |
     |  { authorization_endpoint, ... }      |
     |<-----------------|                    |
     |                  |                    |
     |  Redirect to authorization_endpoint   |
     |-------------------------------------->|
     |                  |   User authenticates
     |  Redirect with auth code              |
     |<--------------------------------------|
     |                  |                    |
     |  POST token_endpoint (exchange code)  |
     |-------------------------------------->|
     |                  |    Access token    |
     |<--------------------------------------|
     |                  |                    |
     |  POST /mcp with Bearer token          |
     |----------------->|                    |
     |                  |  Validate JWT      |
     |                  |------------------->|
     |                  |   Token valid      |
     |                  |<-------------------|
     |  Tool response   |                    |
     |<-----------------|                    |
```

## Troubleshooting

### Library Loading Errors

```
RuntimeError: Auth functions not available
```

**Solution:** Ensure the native library is compiled and accessible:
- Copy `libgopher-orch.dylib` (macOS) or `libgopher-orch.so` (Linux) to `./lib/`
- Or set `GOPHER_ORCH_LIBRARY_PATH` environment variable

### Token Validation Failures

```
401 Unauthorized: Token validation failed
```

**Causes:**
- Token expired - obtain a new token
- Invalid issuer - check `issuer` in config matches token
- JWKS fetch failed - verify `jwks_uri` is accessible
- Invalid audience - ensure token has correct audience claim

### JWKS Fetch Errors

```
Error: JWKS fetch failed
```

**Solutions:**
- Verify `jwks_uri` is correct and accessible
- Check network connectivity to OAuth server
- Increase `request_timeout` if needed

### Scope Access Denied

```json
{"error": "access_denied", "message": "Required scope: mcp:read"}
```

**Solution:** Ensure your token includes the required scope. Request additional scopes during token acquisition.

## Project Structure

```
examples/auth/
├── lib/                         # Native library (libgopher-orch)
├── py_auth_mcp_server/
│   ├── __init__.py             # Package metadata
│   ├── __main__.py             # Entry point
│   ├── app.py                  # Flask application factory
│   ├── config.py               # Configuration loader
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── oauth_auth.py       # OAuth middleware
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── health.py           # Health endpoint
│   │   ├── oauth_endpoints.py  # Discovery endpoints
│   │   └── mcp_handler.py      # JSON-RPC handler
│   └── tools/
│       ├── __init__.py
│       └── weather_tools.py    # Example tools
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_config.py
│   ├── test_oauth_auth.py
│   ├── test_mcp_handler.py
│   ├── test_weather_tools.py
│   └── test_integration.py
├── pyproject.toml              # Project configuration
├── requirements.txt            # Dependencies
├── server.config               # Server configuration
├── server.config.example       # Configuration template
└── README.md
```

## License

See the main gopher-mcp-python repository for license information.
