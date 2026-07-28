#!/usr/bin/env python3
"""Verify that the installed Python SDK can load the native gopher-orch library."""

import sys

from gopher_mcp_python.ffi.library import GopherOrchLibrary


def fail(message: str) -> None:
    print(f"[verify-native] error: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    library = GopherOrchLibrary.get_instance()
    if library is None:
        fail(GopherOrchLibrary.get_load_error_message())

    print("[verify-native] native library loaded")

    required_symbols = (
        "gopher_orch_agent_create_by_json",
        "gopher_orch_agent_create_by_api_key",
        "gopher_orch_agent_run",
        "gopher_orch_agent_release",
        "gopher_orch_api_fetch_servers",
        "gopher_orch_last_error",
        "gopher_orch_clear_error",
        "gopher_orch_free",
    )
    native_library = getattr(library, "_lib", None)
    missing = [
        symbol
        for symbol in required_symbols
        if native_library is None or not hasattr(native_library, symbol)
    ]
    if missing:
        fail(f"native library missing required symbols: {', '.join(missing)}")

    print("[verify-native] required symbols present")


if __name__ == "__main__":
    main()
