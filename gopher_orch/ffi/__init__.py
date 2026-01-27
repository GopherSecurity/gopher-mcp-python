"""FFI (Foreign Function Interface) module for gopher-orch native library."""

from gopher_orch.ffi.library import GopherOrchErrorInfo, GopherOrchLibrary

__all__ = [
    "GopherOrchLibrary",
    "GopherOrchErrorInfo",
]
