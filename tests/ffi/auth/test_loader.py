"""Tests for auth loader module."""

import platform
import pytest
from unittest.mock import patch

from gopher_mcp_python.ffi.auth.loader import (
    _get_library_name,
    _get_search_paths,
    load_library,
    is_library_loaded,
    get_library,
    is_auth_available,
    get_auth_functions,
    GopherAuthClientPtr,
    GopherAuthPayloadPtr,
    GopherAuthOptionsPtr,
    GopherAuthValidationResult,
)


class TestGetLibraryName:
    """Tests for _get_library_name function."""

    def test_returns_string(self):
        """Test function returns a string."""
        name = _get_library_name()
        assert isinstance(name, str)
        assert len(name) > 0

    @patch("platform.system")
    def test_darwin_library_name(self, mock_system):
        """Test macOS library name."""
        mock_system.return_value = "Darwin"
        name = _get_library_name()
        assert name == "libgopher-orch.dylib"

    @patch("platform.system")
    def test_windows_library_name(self, mock_system):
        """Test Windows library name."""
        mock_system.return_value = "Windows"
        name = _get_library_name()
        assert name == "gopher-orch.dll"

    @patch("platform.system")
    def test_linux_library_name(self, mock_system):
        """Test Linux library name."""
        mock_system.return_value = "Linux"
        name = _get_library_name()
        assert name == "libgopher-orch.so"


class TestGetSearchPaths:
    """Tests for _get_search_paths function."""

    def test_returns_list(self):
        """Test function returns a list."""
        paths = _get_search_paths()
        assert isinstance(paths, list)

    def test_paths_are_strings(self):
        """Test all paths are strings."""
        paths = _get_search_paths()
        for path in paths:
            assert isinstance(path, str)

    def test_includes_native_lib(self):
        """Test includes native/lib path."""
        paths = _get_search_paths()
        native_lib_found = any("native" in p and "lib" in p for p in paths)
        assert native_lib_found

    @patch("platform.system")
    def test_darwin_includes_homebrew(self, mock_system):
        """Test macOS includes homebrew paths."""
        mock_system.return_value = "Darwin"
        paths = _get_search_paths()
        homebrew_found = any("/opt/homebrew/lib" in p for p in paths)
        assert homebrew_found

    def test_includes_usr_lib(self):
        """Test includes /usr/lib path."""
        paths = _get_search_paths()
        usr_lib_found = any("/usr/lib" in p for p in paths)
        assert usr_lib_found


class TestPointerTypes:
    """Tests for opaque pointer types."""

    def test_client_ptr_is_void_p(self):
        """Test GopherAuthClientPtr is c_void_p."""
        from ctypes import c_void_p
        assert GopherAuthClientPtr == c_void_p

    def test_payload_ptr_is_void_p(self):
        """Test GopherAuthPayloadPtr is c_void_p."""
        from ctypes import c_void_p
        assert GopherAuthPayloadPtr == c_void_p

    def test_options_ptr_is_void_p(self):
        """Test GopherAuthOptionsPtr is c_void_p."""
        from ctypes import c_void_p
        assert GopherAuthOptionsPtr == c_void_p


class TestValidationResultStructure:
    """Tests for GopherAuthValidationResult structure."""

    def test_has_valid_field(self):
        """Test structure has valid field."""
        result = GopherAuthValidationResult()
        assert hasattr(result, "valid")

    def test_has_error_code_field(self):
        """Test structure has error_code field."""
        result = GopherAuthValidationResult()
        assert hasattr(result, "error_code")

    def test_has_error_message_field(self):
        """Test structure has error_message field."""
        result = GopherAuthValidationResult()
        assert hasattr(result, "error_message")

    def test_default_values(self):
        """Test default field values."""
        result = GopherAuthValidationResult()
        assert result.valid is False
        assert result.error_code == 0


class TestLoadLibrary:
    """Tests for load_library function."""

    def test_returns_bool(self):
        """Test function returns boolean."""
        result = load_library()
        assert isinstance(result, bool)

    def test_idempotent(self):
        """Test multiple calls return same result."""
        result1 = load_library()
        result2 = load_library()
        assert result1 == result2


class TestIsLibraryLoaded:
    """Tests for is_library_loaded function."""

    def test_returns_bool(self):
        """Test function returns boolean."""
        result = is_library_loaded()
        assert isinstance(result, bool)

    def test_consistent_with_load(self):
        """Test consistency with load_library."""
        load_result = load_library()
        is_loaded = is_library_loaded()
        assert load_result == is_loaded


class TestGetLibrary:
    """Tests for get_library function."""

    def test_returns_none_or_cdll(self):
        """Test function returns None or CDLL instance."""
        lib = get_library()
        if lib is not None:
            import ctypes
            assert isinstance(lib, ctypes.CDLL)


class TestIsAuthAvailable:
    """Tests for is_auth_available function."""

    def test_returns_bool(self):
        """Test function returns boolean."""
        result = is_auth_available()
        assert isinstance(result, bool)


class TestGetAuthFunctions:
    """Tests for get_auth_functions function."""

    def test_returns_dict(self):
        """Test function returns dictionary."""
        funcs = get_auth_functions()
        assert isinstance(funcs, dict)

    def test_expected_keys(self):
        """Test dictionary has expected keys."""
        funcs = get_auth_functions()
        expected_keys = [
            "auth_init",
            "auth_shutdown",
            "auth_version",
            "client_create",
            "client_destroy",
            "validate_token",
            "extract_payload",
        ]
        for key in expected_keys:
            assert key in funcs

    def test_values_none_or_callable(self):
        """Test values are None or callable."""
        funcs = get_auth_functions()
        for name, func in funcs.items():
            if func is not None:
                assert callable(func), f"{name} is not callable"
