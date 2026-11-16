#!/usr/bin/env python3
"""Run an API example against this checkout and an explicit local native binary."""

import os
from pathlib import Path
import runpy
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]


def prepare_local_sdk() -> None:
    # Put this checkout ahead of installed SDKs, including editable installs
    # belonging to another checkout.
    sys.path.insert(0, str(REPO_ROOT))
    import gopher_mcp_python
    from gopher_mcp_python.ffi.library import GopherOrchLibrary

    resolver = object.__new__(GopherOrchLibrary)
    override = os.environ.get("GOPHER_MCP_PYTHON_LIBRARY_PATH") or os.environ.get(
        "GOPHER_ORCH_LIBRARY_PATH"
    )
    candidates = (
        [Path(override).expanduser()]
        if override
        else [
            REPO_ROOT / "native" / resolver._get_platform_native_dir_name() / "lib",
            REPO_ROOT / "native/current/lib",
            REPO_ROOT / "native/lib",
            REPO_ROOT / "third_party/gopher-orch/build/lib",
            REPO_ROOT / "third_party/gopher-orch/build/bin",
            REPO_ROOT / "third_party/gopher-orch/cmake-build-debug/lib",
            REPO_ROOT / "third_party/gopher-orch/cmake-build-debug/bin",
        ]
    )
    selected = None
    for candidate in candidates:
        selected = resolver._resolve_library_path(
            str(candidate), resolver._get_library_name()
        )
        if selected is not None:
            break
    if selected is None:
        raise SystemExit(
            "Local gopher-orch native library not found. Run ./build.sh from "
            "the repository root, or set GOPHER_MCP_PYTHON_LIBRARY_PATH to a "
            "built native library file or directory."
        )
    selected = Path(selected).resolve()
    os.environ["GOPHER_MCP_PYTHON_LIBRARY_PATH"] = str(selected)
    os.environ["GOPHER_ORCH_LIBRARY_PATH"] = str(selected)
    library = GopherOrchLibrary.get_instance()
    if library is None:
        raise SystemExit(GopherOrchLibrary.get_load_error_message())
    if Path(library._loaded_library_path).resolve() != selected:
        raise SystemExit(
            f"Failed to load selected native library: {selected}\n"
            + GopherOrchLibrary.get_load_error_message()
        )
    print(f"SDK source: {gopher_mcp_python.__file__}", flush=True)
    print(f"Native library: {selected}", flush=True)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: _run_local.py example.py [query ...]")
    example = Path(__file__).parent / sys.argv[1]
    prepare_local_sdk()
    sys.argv = [str(example), *sys.argv[2:]]
    print("\nRunning example...\n", flush=True)
    runpy.run_path(str(example), run_name="__main__")


if __name__ == "__main__":
    main()
