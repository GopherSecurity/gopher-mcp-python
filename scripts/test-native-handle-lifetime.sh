#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/test-native-handle-lifetime.sh [address|thread|none]
sanitizer="${1:-address}"
case "$sanitizer" in
  address|thread) flags=("-fsanitize=$sanitizer" -fno-omit-frame-pointer) ;;
  none) flags=() ;;
  *) echo "Expected sanitizer: address, thread, or none" >&2; exit 2 ;;
esac
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
native_root="$root/third_party/gopher-orch"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/gopher-handle-lifetime.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT
"${CXX:-c++}" -std=c++14 -g -O1 -pthread "${flags[@]}" \
  -I "$native_root/include" \
  "$native_root/tests/gopher/orch/FFI/ffi_handle_lifetime_standalone_test.cc" \
  -o "$work_dir/ffi-handle-lifetime"
"$work_dir/ffi-handle-lifetime"
