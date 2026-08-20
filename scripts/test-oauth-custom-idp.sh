#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

PYTHON_BIN="${PYTHON:-}"
if [ -z "${PYTHON_BIN}" ]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    PYTHON_BIN="python3"
  fi
fi

"${PYTHON_BIN}" -m pytest \
  tests/test_oauth_auto_custom_idp.py \
  tests/test_oauth_auto_custom_idp_failures.py \
  tests/test_custom_oauth_test_idp.py \
  tests/test_custom_protected_mcp_endpoints.py \
  tests/test_oauth_test_token_helper.py \
  "$@"
