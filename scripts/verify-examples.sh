#!/usr/bin/env bash

set -euo pipefail

MODE="${VERIFY_EXAMPLES_MODE:-auto}"
ONLY_EXAMPLE=""
ENV_FILE="${VERIFY_EXAMPLES_ENV_FILE:-}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_VERSION=""
PLATFORM=""
NATIVE_PACKAGE=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMP_ROOT=""
PROJECT_DIR=""
VENV_DIR=""
SDK_INSTALL_SPEC="${SDK_INSTALL_SPEC:-}"
NATIVE_INSTALL_SPEC="${NATIVE_INSTALL_SPEC:-}"
SDK_VERSION="${VERIFY_PYPI_VERSION:-latest}"
VERIFY_LIVE_PROMPT="${VERIFY_LIVE_PROMPT:-What tools do we have?}"
VERIFY_EXPECTED_ANSWER="${VERIFY_EXPECTED_ANSWER:-tool}"
VERIFY_EXPECTED_ANSWER_TERMS="${VERIFY_EXPECTED_ANSWER_TERMS:-}"
LIVE_CHECKS_RUN=0
LIVE_CHECKS_SKIPPED=0
LIVE_ANSWER_SUMMARY=""
SELECTED_EXAMPLES=()
EXAMPLES=(
  "create_by_url|examples/api/create_by_url.py|GOPHER_MCP_URL LLM_MODEL|ANTHROPIC_API_KEY"
  "create_by_api_key|examples/api/create_by_api_key.py|GOPHER_API_KEY LLM_MODEL|ANTHROPIC_API_KEY"
  "create_by_json|examples/api/create_by_json.py|LLM_MODEL|ANTHROPIC_API_KEY"
  "create_by_server_id|examples/api/create_by_server_id.py|GOPHER_API_KEY GOPHER_MCP_SERVER_ID LLM_MODEL|ANTHROPIC_API_KEY"
  "create_by_server_name|examples/api/create_by_server_name.py|GOPHER_API_KEY GOPHER_MCP_SERVER_NAME LLM_MODEL|ANTHROPIC_API_KEY"
  "create_by_gateway_id|examples/api/create_by_gateway_id.py|GOPHER_API_KEY GOPHER_MCP_GATEWAY_ID LLM_MODEL|ANTHROPIC_API_KEY"
  "create_by_gateway_name|examples/api/create_by_gateway_name.py|GOPHER_API_KEY GOPHER_MCP_GATEWAY_NAME LLM_MODEL|ANTHROPIC_API_KEY"
)

usage() {
  cat <<'EOF'
Usage: scripts/verify-examples.sh [options]

Options:
  --mode <offline|live|auto>     Verification mode (default: auto)
  --only <example-name>          Run one example by registry name
  --env-file <path>              Load live environment variables from a file
  -h, --help                     Show this help

Environment:
  VERIFY_EXAMPLES_ENV_FILE       Default env file path
  VERIFY_PYPI_VERSION            PyPI version to verify, or latest (default: latest)
  SDK_INSTALL_SPEC               Override SDK pip install spec
  NATIVE_INSTALL_SPEC            Override native package pip install spec
  VERIFY_LIVE_PROMPT             Prompt used for live agent.run() checks
  VERIFY_EXPECTED_ANSWER         Text that must appear in the live answer
  VERIFY_EXPECTED_ANSWER_TERMS   Comma-separated terms that must all appear in the live answer
EOF
}

log() {
  printf '[verify-examples] %s\n' "$*"
}

fail() {
  log "error: $*"
  exit 1
}

log_live_failure_diagnostics() {
  local output="$1"
  local answer_body="$2"
  local output_bytes
  local output_lines
  local answer_bytes
  local answer_lines
  local marker_present="false"

  output_bytes="$(printf '%s' "$output" | wc -c | tr -d '[:space:]')"
  output_lines="$(printf '%s\n' "$output" | wc -l | tr -d '[:space:]')"
  answer_bytes="$(printf '%s' "$answer_body" | wc -c | tr -d '[:space:]')"
  answer_lines="$(printf '%s\n' "$answer_body" | wc -l | tr -d '[:space:]')"
  if grep -q 'Agent Response' <<<"$output"; then
    marker_present="true"
  fi

  log "live output redacted: output_bytes=${output_bytes} output_lines=${output_lines} agent_response_marker=${marker_present} answer_bytes=${answer_bytes} answer_lines=${answer_lines}"
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --mode)
        [ "$#" -ge 2 ] || fail "--mode requires a value"
        MODE="$2"
        shift 2
        ;;
      --only)
        [ "$#" -ge 2 ] || fail "--only requires a value"
        ONLY_EXAMPLE="$2"
        shift 2
        ;;
      --env-file)
        [ "$#" -ge 2 ] || fail "--env-file requires a value"
        ENV_FILE="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "unknown argument: $1"
        ;;
    esac
  done
}

validate_args() {
  case "$MODE" in
    offline|live|auto) ;;
    *) fail "invalid --mode '${MODE}'; expected offline, live, or auto" ;;
  esac

  if [ -n "$ONLY_EXAMPLE" ] && ! [[ "$ONLY_EXAMPLE" =~ ^[A-Za-z0-9_-]+$ ]]; then
    fail "--only must be an example name containing only letters, numbers, '_' or '-'"
  fi
}

load_env_file() {
  if [ -z "$ENV_FILE" ]; then
    return
  fi

  if [ ! -f "$ENV_FILE" ]; then
    fail "env file not found: ${ENV_FILE}"
  fi

  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
  log "env_file=${ENV_FILE}"
}

require_python() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    fail "Python 3.8 or newer is required, but ${PYTHON_BIN} was not found in PATH"
  fi

  PYTHON_VERSION="$("$PYTHON_BIN" - <<'PY'
import sys
print(".".join(str(part) for part in sys.version_info[:3]))
raise SystemExit(0 if sys.version_info >= (3, 8) else 1)
PY
)" || fail "Python 3.8 or newer is required; current version is ${PYTHON_VERSION:-unknown}"
}

detect_platform() {
  local os
  local arch

  os="$(uname -s 2>/dev/null || true)"
  arch="$(uname -m 2>/dev/null || true)"

  case "${os}:${arch}" in
    Darwin:arm64)
      PLATFORM="darwin-arm64"
      ;;
    Darwin:x86_64|Darwin:amd64)
      PLATFORM="darwin-x64"
      ;;
    Linux:x86_64|Linux:amd64)
      PLATFORM="linux-x64"
      ;;
    Linux:aarch64|Linux:arm64)
      PLATFORM="linux-arm64"
      ;;
    MINGW*:x86_64|MSYS*:x86_64|CYGWIN*:x86_64|Windows_NT:x86_64|Windows_NT:amd64)
      PLATFORM="win32-x64"
      ;;
    *)
      fail "unsupported platform '${os:-unknown}' '${arch:-unknown}'"
      ;;
  esac

  NATIVE_PACKAGE="gopher-mcp-python-native-${PLATFORM}"
}

compute_install_specs() {
  if [ -z "$SDK_INSTALL_SPEC" ]; then
    if [ "$SDK_VERSION" = "latest" ]; then
      SDK_INSTALL_SPEC="gopher-mcp-python"
    else
      SDK_INSTALL_SPEC="gopher-mcp-python==${SDK_VERSION}"
    fi
  fi

  if [ -z "$NATIVE_INSTALL_SPEC" ]; then
    if [ "$SDK_VERSION" = "latest" ]; then
      NATIVE_INSTALL_SPEC="${NATIVE_PACKAGE}"
    else
      NATIVE_INSTALL_SPEC="${NATIVE_PACKAGE}==${SDK_VERSION}"
    fi
  fi
}

example_name() {
  local spec="$1"
  printf '%s\n' "${spec%%|*}"
}

example_path() {
  local spec="$1"
  local rest="${spec#*|}"
  printf '%s\n' "${rest%%|*}"
}

example_required_env() {
  local spec="$1"
  local rest="${spec#*|}"
  rest="${rest#*|}"
  printf '%s\n' "${rest%%|*}"
}

example_provider_env() {
  local spec="$1"
  local rest="${spec#*|}"
  rest="${rest#*|}"
  rest="${rest#*|}"
  printf '%s\n' "$rest"
}

select_examples() {
  local spec
  local name
  local found=0

  SELECTED_EXAMPLES=()

  for spec in "${EXAMPLES[@]}"; do
    name="$(example_name "$spec")"
    if [ -z "$ONLY_EXAMPLE" ] || [ "$ONLY_EXAMPLE" = "$name" ]; then
      SELECTED_EXAMPLES+=("$spec")
      found=1
    fi
  done

  if [ "$found" -ne 1 ]; then
    fail "unknown example '${ONLY_EXAMPLE}'; supported examples are create_by_url, create_by_api_key, create_by_json, create_by_server_id, create_by_server_name, create_by_gateway_id, and create_by_gateway_name"
  fi
}

log_selected_examples() {
  local names=()
  local spec

  for spec in "${SELECTED_EXAMPLES[@]}"; do
    names+=("$(example_name "$spec")")
  done

  local joined="${names[*]}"
  log "examples=${joined// /,}"
}

create_project() {
  TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/gopher-mcp-python-example-verify.XXXXXX")"
  PROJECT_DIR="${TEMP_ROOT}/project"
  VENV_DIR="${PROJECT_DIR}/venv"
  mkdir -p "$PROJECT_DIR"

  "$PYTHON_BIN" -m venv "$VENV_DIR"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
  "${VENV_DIR}/bin/python" -m pip install "$SDK_INSTALL_SPEC" "$NATIVE_INSTALL_SPEC" >/dev/null

  SDK_VERSION="$("${VENV_DIR}/bin/python" - <<'PY'
from importlib import metadata
print(metadata.version("gopher-mcp-python"))
PY
)"

  log "temp_project=${PROJECT_DIR}"
  log "platform=${PLATFORM} python=${PYTHON_VERSION} mode=${MODE} sdk=${SDK_VERSION}"
}

cleanup() {
  if [ -n "$TEMP_ROOT" ] && [ -d "$TEMP_ROOT" ]; then
    rm -rf "$TEMP_ROOT"
  fi
}

run_native_probe() {
  "${VENV_DIR}/bin/python" "${REPO_ROOT}/scripts/verify-example-native-probe.py"
}

run_offline_example_bootstrap_checks() {
  local spec
  local name
  local source_path
  local target_file
  local output
  local status

  for spec in "${SELECTED_EXAMPLES[@]}"; do
    name="$(example_name "$spec")"
    source_path="${REPO_ROOT}/$(example_path "$spec")"
    target_file="${PROJECT_DIR}/$(basename "$source_path")"

    if [ ! -f "$source_path" ]; then
      fail "${name} offline: source file not found: ${source_path}"
    fi

    cp "$source_path" "$target_file"

    set +e
    output="$(
      cd "$PROJECT_DIR" &&
        env \
          -u GOPHER_MCP_URL \
          -u GOPHER_API_KEY \
          -u GOPHER_MCP_SERVER_ID \
          -u GOPHER_MCP_SERVER_NAME \
          -u GOPHER_MCP_GATEWAY_ID \
          -u GOPHER_MCP_GATEWAY_NAME \
          -u LLM_MODEL \
          -u LLM_PROVIDER \
          -u ANTHROPIC_API_KEY \
          "${VENV_DIR}/bin/python" "$(basename "$target_file")" 2>&1
    )"
    status=$?
    set -e

    if [ "$status" -eq 0 ]; then
      printf '%s\n' "$output"
      fail "${name} offline: expected missing-env validation failure"
    fi

    if ! grep -Eq 'must (both |all )?be set' <<<"$output"; then
      printf '%s\n' "$output"
      fail "${name} offline: did not report expected missing-env validation"
    fi

    log "${name} offline: missing-env validation OK"
  done
}

has_required_env() {
  local required="$1"
  local provider_required="$2"
  local key

  for key in $required; do
    if [ -z "${!key:-}" ]; then
      return 1
    fi
  done

  if [ "${LLM_PROVIDER:-AnthropicProvider}" = "AnthropicProvider" ]; then
    for key in $provider_required; do
      if [ -z "${!key:-}" ]; then
        return 1
      fi
    done
  fi

  return 0
}

validate_expected_answer_terms() {
  local answer_body="$1"
  local terms="$2"
  local term

  terms="${terms},"
  while [ -n "$terms" ]; do
    term="${terms%%,*}"
    terms="${terms#*,}"
    term="$(sed 's/^[[:space:]]*//;s/[[:space:]]*$//' <<<"$term")"
    [ -n "$term" ] || continue

    if ! grep -qi -- "$term" <<<"$answer_body"; then
      return 1
    fi
  done

  return 0
}

run_live_example_checks() {
  local spec
  local name
  local required
  local provider_required
  local source_path
  local target_file
  local output
  local status
  local answer_body

  for spec in "${SELECTED_EXAMPLES[@]}"; do
    name="$(example_name "$spec")"
    required="$(example_required_env "$spec")"
    provider_required="$(example_provider_env "$spec")"

    if ! has_required_env "$required" "$provider_required"; then
      if [ "$MODE" = "live" ]; then
        fail "${name} live: missing required environment (${required} ${provider_required})"
      fi
      LIVE_CHECKS_SKIPPED=$((LIVE_CHECKS_SKIPPED + 1))
      log "${name} live: skipped because required environment is missing"
      continue
    fi

    source_path="${REPO_ROOT}/$(example_path "$spec")"
    target_file="${PROJECT_DIR}/$(basename "$source_path")"
    cp "$source_path" "$target_file"

    set +e
    output="$(
      cd "$PROJECT_DIR" &&
        "${VENV_DIR}/bin/python" "$(basename "$target_file")" "$VERIFY_LIVE_PROMPT" 2>&1
    )"
    status=$?
    set -e

    if [ "$status" -ne 0 ]; then
      log_live_failure_diagnostics "$output" ""
      fail "${name} live: example exited with status ${status}"
    fi

    answer_body="$(awk '/Agent Response/{capture=1; next} capture {print}' <<<"$output")"

    if [ -z "$(tr -d '[:space:]' <<<"$answer_body")" ]; then
      log_live_failure_diagnostics "$output" "$answer_body"
      fail "${name} live: missing agent response body"
    fi

    if grep -Eqi '(^|[[:space:]])(Error:|Traceback|isError)' <<<"$answer_body"; then
      log_live_failure_diagnostics "$output" "$answer_body"
      fail "${name} live: agent response contains an error"
    fi

    if [ -n "$VERIFY_EXPECTED_ANSWER" ] &&
      ! grep -qi -- "$VERIFY_EXPECTED_ANSWER" <<<"$answer_body"; then
      log_live_failure_diagnostics "$output" "$answer_body"
      fail "${name} live: expected answer text '${VERIFY_EXPECTED_ANSWER}' not found"
    fi

    if [ -n "$VERIFY_EXPECTED_ANSWER_TERMS" ] &&
      ! validate_expected_answer_terms "$answer_body" "$VERIFY_EXPECTED_ANSWER_TERMS"; then
      log_live_failure_diagnostics "$output" "$answer_body"
      fail "${name} live: expected answer terms '${VERIFY_EXPECTED_ANSWER_TERMS}' not found"
    fi

    LIVE_CHECKS_RUN=$((LIVE_CHECKS_RUN + 1))
    LIVE_ANSWER_SUMMARY="${LIVE_ANSWER_SUMMARY}"$'\n'"${name}: answer_bytes=$(printf '%s' "$answer_body" | wc -c | tr -d '[:space:]')"
    log "${name} live: OK (answer redacted)"
  done
}

main() {
  parse_args "$@"
  validate_args
  load_env_file
  require_python
  detect_platform
  compute_install_specs
  select_examples

  log "only=${ONLY_EXAMPLE:-<all>}"
  log_selected_examples
  log "sdk_install=${SDK_INSTALL_SPEC}"
  log "native_install=${NATIVE_INSTALL_SPEC}"

  create_project
  trap cleanup EXIT

  run_native_probe

  case "$MODE" in
    offline)
      run_offline_example_bootstrap_checks
      ;;
    live)
      run_live_example_checks
      ;;
    auto)
      run_offline_example_bootstrap_checks
      run_live_example_checks
      ;;
  esac

  if [ "$LIVE_CHECKS_RUN" -gt 0 ]; then
    log "live_checks=${LIVE_CHECKS_RUN}"
    printf '%s\n' "$LIVE_ANSWER_SUMMARY" | sed '/^$/d'
  fi

  if [ "$MODE" = "auto" ] && [ "$LIVE_CHECKS_SKIPPED" -gt 0 ]; then
    log "live_skipped=${LIVE_CHECKS_SKIPPED}"
  fi

  log "verification passed"
}

main "$@"
