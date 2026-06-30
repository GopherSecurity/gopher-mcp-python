"""Tests for the main ctypes native library search order."""

import os

from gopher_mcp_python.ffi.library import GopherOrchLibrary


def test_prefers_local_native_lib_before_platform_package(monkeypatch):
    """Local builds from ./build.sh should win over installed native packages."""
    lib = object.__new__(GopherOrchLibrary)
    monkeypatch.setattr(
        lib,
        "_get_platform_package_path",
        lambda: "/tmp/gopher-platform-native/lib",
    )

    paths = lib._get_search_paths()

    assert paths.index(os.path.join(os.getcwd(), "native", "lib")) < paths.index(
        "/tmp/gopher-platform-native/lib"
    )
