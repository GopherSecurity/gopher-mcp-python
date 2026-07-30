#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SERVER_BIN="${SCRIPT_DIR}/create_by_url_server"
GATEWAY_BIN="${SCRIPT_DIR}/create_by_url_gateway"
CLIENT_PY="${SCRIPT_DIR}/create_by_url.py"

TOKEN="${GOPHER_ACCESS_TOKEN:-abc123456789xyz}"
QUERY="${1:-What is the weather in Tokyo?}"
SESSION_ID="gopher-mcp-python-header-create-by-url-run"

LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gopher-mcp-python-header-verify.XXXXXX")"
chmod 700 "${LOG_DIR}"
SERVER_LOG="${LOG_DIR}/server.log"
GATEWAY_LOG="${LOG_DIR}/gateway.log"
CLIENT_LOG="${LOG_DIR}/client.log"
CURL_LOG="${LOG_DIR}/curl.log"

SERVER_PID=""
GATEWAY_PID=""

redacted_token() {
  local token="$1"
  local len=${#token}
  if [[ ${len} -eq 0 ]]; then
    printf '<empty>'
  elif [[ ${len} -le 6 ]]; then
    printf '***'
  else
    printf '%s...%s' "${token:0:3}" "${token: -3}"
  fi
}

port_in_use() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

find_available_port() {
  local start="$1"
  local end=$((start + 100))
  local port

  for ((port = start; port <= end; port++)); do
    if ! port_in_use "${port}"; then
      printf '%s\n' "${port}"
      return 0
    fi
  done

  echo "ERROR: no free TCP port found in ${start}-${end}" >&2
  return 1
}

require_available_port() {
  local port="$1"
  local name="$2"

  if port_in_use "${port}"; then
    echo "ERROR: ${name} port ${port} is already in use." >&2
    echo "Set a different port with GOPHER_MCP_SERVER_PORT or GOPHER_GATEWAY_PORT." >&2
    return 1
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local log_file="${3:-}"
  local deadline=$((SECONDS + 20))

  while ((SECONDS < deadline)); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    if [[ -n "${log_file}" ]] && grep -F "Failed to bind socket" "${log_file}" >/dev/null 2>&1; then
      echo "ERROR: ${name} failed to bind at ${url}" >&2
      return 1
    fi
    sleep 0.5
  done

  echo "ERROR: ${name} did not become ready at ${url}" >&2
  return 1
}

stop_pid() {
  local pid="$1"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
  fi
}

start_server() {
  local attempts=1
  if [[ -z "${GOPHER_MCP_SERVER_PORT:-}" ]]; then
    attempts=10
  fi

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    BACKEND_URL="http://127.0.0.1:${SERVER_PORT}/mcp"
    echo "Starting local MCP server on ${BACKEND_URL}..."
    GOPHER_SDK_TEST=1 \
    GOPHER_MCP_LOG_FLOW=1 \
    GOPHER_MCP_SERVER_PORT="${SERVER_PORT}" \
    "${SERVER_BIN}" >"${SERVER_LOG}" 2>&1 &
    SERVER_PID=$!

    if wait_for_url "http://127.0.0.1:${SERVER_PORT}/health" "MCP server" "${SERVER_LOG}"; then
      return 0
    fi

    stop_pid "${SERVER_PID}"
    SERVER_PID=""
    if [[ -n "${GOPHER_MCP_SERVER_PORT:-}" ]]; then
      return 1
    fi
    SERVER_PORT="$(find_available_port $((SERVER_PORT + 1)))"
    : >"${SERVER_LOG}"
  done

  echo "ERROR: MCP server did not start on any auto-selected port" >&2
  return 1
}

start_gateway() {
  local attempts=1
  if [[ -z "${GOPHER_GATEWAY_PORT:-}" ]]; then
    attempts=10
  fi

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if [[ "${GATEWAY_PORT}" = "${SERVER_PORT}" ]]; then
      if [[ -n "${GOPHER_GATEWAY_PORT:-}" ]]; then
        echo "ERROR: MCP server and gateway ports must be different." >&2
        return 1
      fi
      GATEWAY_PORT="$(find_available_port $((GATEWAY_PORT + 1)))"
    fi

    GATEWAY_URL="http://127.0.0.1:${GATEWAY_PORT}/mcp"
    echo "Starting local gateway on ${GATEWAY_URL}..."
    GOPHER_SDK_TEST=1 \
    GOPHER_MCP_LOG_FLOW=1 \
    GOPHER_GATEWAY_PORT="${GATEWAY_PORT}" \
    GOPHER_BACKEND_MCP_URL="${BACKEND_URL}" \
    "${GATEWAY_BIN}" >"${GATEWAY_LOG}" 2>&1 &
    GATEWAY_PID=$!

    if wait_for_url "http://127.0.0.1:${GATEWAY_PORT}/health" "gateway" "${GATEWAY_LOG}"; then
      return 0
    fi

    stop_pid "${GATEWAY_PID}"
    GATEWAY_PID=""
    if [[ -n "${GOPHER_GATEWAY_PORT:-}" ]]; then
      return 1
    fi
    GATEWAY_PORT="$(find_available_port $((GATEWAY_PORT + 1)))"
    : >"${GATEWAY_LOG}"
  done

  echo "ERROR: gateway did not start on any auto-selected port" >&2
  return 1
}

cleanup() {
  local status=$?
  stop_pid "${GATEWAY_PID}"
  stop_pid "${SERVER_PID}"

  if [[ ${status} -ne 0 ]]; then
    echo
    echo "Verification failed. Logs are in: ${LOG_DIR}" >&2
    echo "  server:  ${SERVER_LOG}" >&2
    echo "  gateway: ${GATEWAY_LOG}" >&2
    echo "  client:  ${CLIENT_LOG}" >&2
    echo "  curl:    ${CURL_LOG}" >&2
  else
    echo
    if [[ "${GOPHER_KEEP_LOGS:-}" = "1" ]]; then
      echo "Verification passed. Logs are in: ${LOG_DIR}"
    else
      rm -rf "${LOG_DIR}"
      echo "Verification passed. Logs removed. Set GOPHER_KEEP_LOGS=1 to keep them."
    fi
  fi
  exit "${status}"
}
trap cleanup EXIT

for bin in "${SERVER_BIN}" "${GATEWAY_BIN}"; do
  if [[ ! -x "${bin}" ]]; then
    echo "ERROR: required binary not found or not executable: ${bin}" >&2
    exit 1
  fi
done

if [[ ! -f "${CLIENT_PY}" ]]; then
  echo "ERROR: Python client not found: ${CLIENT_PY}" >&2
  exit 1
fi

if [[ -n "${GOPHER_MCP_SERVER_PORT:-}" ]]; then
  SERVER_PORT="${GOPHER_MCP_SERVER_PORT}"
  require_available_port "${SERVER_PORT}" "MCP server"
else
  SERVER_PORT="$(find_available_port 5100)"
fi

if [[ -n "${GOPHER_GATEWAY_PORT:-}" ]]; then
  GATEWAY_PORT="${GOPHER_GATEWAY_PORT}"
  require_available_port "${GATEWAY_PORT}" "gateway"
else
  GATEWAY_PORT="$(find_available_port $((SERVER_PORT + 1)))"
fi

if [[ "${SERVER_PORT}" = "${GATEWAY_PORT}" ]]; then
  echo "ERROR: MCP server and gateway ports must be different." >&2
  exit 1
fi

start_server
start_gateway

echo "Running deterministic MCP calls through gateway..."
{
  echo "=== initialize ==="
  curl -fsS -X POST "${GATEWAY_URL}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "mcp-session-id: ${SESSION_ID}" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"gopher-mcp-python-header-verify","version":"1.0.0"}}}'
  echo
  echo "=== tools/list ==="
  curl -fsS -X POST "${GATEWAY_URL}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "mcp-session-id: ${SESSION_ID}" \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
  echo
  echo "=== tools/call ==="
  curl -fsS -X POST "${GATEWAY_URL}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "mcp-session-id: ${SESSION_ID}" \
    -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"get-weather","arguments":{"city":"Tokyo"}}}'
  echo
} >"${CURL_LOG}" 2>&1

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Running Python SDK agent client through gateway..."
  ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  GOPHER_SDK_TEST=1 \
  GOPHER_MCP_LOG_FLOW=1 \
  GOPHER_MCP_URL="${GATEWAY_URL}" \
  GOPHER_ACCESS_TOKEN="${TOKEN}" \
  python3 "${CLIENT_PY}" "${QUERY}" >"${CLIENT_LOG}" 2>&1 || {
    echo "SDK client returned non-zero; continuing with transport verification."
  }
else
  echo "Skipping Python SDK agent client because ANTHROPIC_API_KEY is not set."
fi

EXPECTED="Bearer $(redacted_token "${TOKEN}") len=${#TOKEN}"

echo "Checking authorization trace: ${EXPECTED}"
grep -F "mcp auth: local example server received Authorization header present=true" "${SERVER_LOG}" >/dev/null
grep -F "[access-token-server] get-weather" "${SERVER_LOG}" >/dev/null
grep -F "Current weather in Tokyo" "${CURL_LOG}" >/dev/null

echo
echo "Matched token logs:"
if [[ -s "${CLIENT_LOG}" ]]; then
  grep -F "token=${EXPECTED}" "${CLIENT_LOG}" | head -n 3 || true
else
  echo "(Python SDK client skipped; no client log)"
fi
grep -F "token=${EXPECTED}" "${GATEWAY_LOG}" | head -n 5 || true
grep -F "token=${EXPECTED}" "${SERVER_LOG}" | head -n 3 || true
echo
echo "MCP tools/call response:"
grep -F "Current weather in Tokyo" "${CURL_LOG}" | head -n 1
