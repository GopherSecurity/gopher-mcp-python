"""Tests for the main ctypes native library search order."""

import os

from gopher_mcp_python.ffi.library import GopherOrchLibrary


def test_prefers_platform_package_before_local_native_lib(monkeypatch):
    """Installed native packages should win unless an env override is set."""
    lib = object.__new__(GopherOrchLibrary)
    monkeypatch.setattr(
        lib,
        "_get_platform_package_path",
        lambda: "/tmp/gopher-platform-native/lib",
    )

    paths = lib._get_search_paths()

    assert paths.index("/tmp/gopher-platform-native/lib") < paths.index(
        os.path.join(os.getcwd(), "native", "lib")
    )


def test_resolves_environment_library_file(tmp_path):
    """Environment override can point directly at the native library file."""
    lib = object.__new__(GopherOrchLibrary)
    lib_file = tmp_path / "libgopher-orch.dylib"
    lib_file.write_bytes(b"")

    assert lib._resolve_library_path(str(lib_file), "libgopher-orch.dylib") == str(
        lib_file
    )


def test_resolves_environment_library_directory(tmp_path):
    """Environment override can point at a directory containing the library."""
    lib = object.__new__(GopherOrchLibrary)
    lib_file = tmp_path / "libgopher-orch.dylib"
    lib_file.write_bytes(b"")

    assert lib._resolve_library_path(str(tmp_path), "libgopher-orch.dylib") == str(
        lib_file
    )


def test_resolves_versioned_library_in_directory(tmp_path):
    """Directory overrides can contain version-suffixed shared libraries."""
    lib = object.__new__(GopherOrchLibrary)
    lib_file = tmp_path / "libgopher-orch.so.0.1.30"
    lib_file.write_bytes(b"")

    assert lib._resolve_library_path(str(tmp_path), "libgopher-orch.so") == str(
        lib_file
    )


def test_records_load_errors():
    lib = object.__new__(GopherOrchLibrary)
    lib._load_errors = []

    lib._record_load_error("failed path")

    assert lib._load_errors == ["failed path"]
