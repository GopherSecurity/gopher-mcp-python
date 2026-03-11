"""Tests for GopherAuthClient class and module functions."""

import pytest

from gopher_mcp_python.ffi.auth.loader import is_auth_available, load_library
from gopher_mcp_python.ffi.auth.auth_client import (
    GopherAuthClient,
    gopher_init_auth_library,
    gopher_shutdown_auth_library,
    gopher_get_auth_library_version,
    gopher_is_auth_library_initialized,
    gopher_generate_www_authenticate_header,
    gopher_generate_www_authenticate_header_v2,
)


class TestLibraryLifecycle:
    """Tests for library lifecycle functions."""

    def test_init_returns_bool(self):
        """Test gopher_init_auth_library returns boolean."""
        result = gopher_init_auth_library()
        assert isinstance(result, bool)

    def test_is_initialized_returns_bool(self):
        """Test gopher_is_auth_library_initialized returns boolean."""
        result = gopher_is_auth_library_initialized()
        assert isinstance(result, bool)

    def test_shutdown_returns_bool(self):
        """Test gopher_shutdown_auth_library returns boolean."""
        result = gopher_shutdown_auth_library()
        assert isinstance(result, bool)


class TestGetAuthLibraryVersion:
    """Tests for gopher_get_auth_library_version function."""

    def test_returns_string_or_none(self):
        """Test function returns string or None."""
        version = gopher_get_auth_library_version()
        assert version is None or isinstance(version, str)


class TestGenerateWwwAuthenticateHeader:
    """Tests for gopher_generate_www_authenticate_header function."""

    @pytest.mark.skipif(
        not is_auth_available(),
        reason="Auth functions not available",
    )
    def test_returns_string_or_none(self):
        """Test function returns string or None."""
        header = gopher_generate_www_authenticate_header("test-realm")
        assert header is None or isinstance(header, str)

    def test_without_auth_returns_none(self):
        """Test returns None when auth not available."""
        if not is_auth_available():
            header = gopher_generate_www_authenticate_header("test-realm")
            assert header is None


class TestGenerateWwwAuthenticateHeaderV2:
    """Tests for gopher_generate_www_authenticate_header_v2 function."""

    @pytest.mark.skipif(
        not is_auth_available(),
        reason="Auth functions not available",
    )
    def test_returns_string_or_none(self):
        """Test function returns string or None."""
        header = gopher_generate_www_authenticate_header_v2(
            realm="test-realm",
            resource_metadata_url="https://example.com/.well-known/oauth-protected-resource",
            scopes=["read", "write"],
        )
        assert header is None or isinstance(header, str)


class TestGopherAuthClientWhenNotAvailable:
    """Tests for GopherAuthClient when auth not available."""

    @pytest.mark.skipif(
        is_auth_available(),
        reason="Auth functions are available",
    )
    def test_raises_when_auth_not_available(self):
        """Test GopherAuthClient raises when auth functions not available."""
        with pytest.raises(RuntimeError, match="not available"):
            GopherAuthClient(
                "https://example.com/.well-known/jwks.json",
                "https://example.com",
            )


# Skip remaining tests if auth functions not available
pytestmark_auth = pytest.mark.skipif(
    not is_auth_available(),
    reason="Auth functions not available in library",
)


@pytestmark_auth
class TestGopherAuthClientInit:
    """Tests for GopherAuthClient initialization."""

    def test_creates_instance(self):
        """Test creating GopherAuthClient instance."""
        client = GopherAuthClient(
            "https://example.com/.well-known/jwks.json",
            "https://example.com",
        )
        assert client is not None
        client.destroy()

    def test_not_destroyed_initially(self):
        """Test client is not destroyed after creation."""
        client = GopherAuthClient(
            "https://example.com/.well-known/jwks.json",
            "https://example.com",
        )
        assert client.is_destroyed() is False
        client.destroy()


@pytestmark_auth
class TestGopherAuthClientSetOption:
    """Tests for set_option method."""

    def test_set_option_returns_bool(self):
        """Test set_option returns boolean."""
        client = GopherAuthClient(
            "https://example.com/.well-known/jwks.json",
            "https://example.com",
        )
        result = client.set_option("cache_duration", "3600")
        assert isinstance(result, bool)
        client.destroy()


@pytestmark_auth
class TestGopherAuthClientLifecycle:
    """Tests for lifecycle methods."""

    def test_destroy_marks_destroyed(self):
        """Test destroy() marks client as destroyed."""
        client = GopherAuthClient(
            "https://example.com/.well-known/jwks.json",
            "https://example.com",
        )
        client.destroy()
        assert client.is_destroyed() is True

    def test_destroy_is_idempotent(self):
        """Test destroy() can be called multiple times."""
        client = GopherAuthClient(
            "https://example.com/.well-known/jwks.json",
            "https://example.com",
        )
        client.destroy()
        client.destroy()  # Should not raise
        assert client.is_destroyed() is True

    def test_validate_token_raises_when_destroyed(self):
        """Test validate_token() raises after destroy."""
        client = GopherAuthClient(
            "https://example.com/.well-known/jwks.json",
            "https://example.com",
        )
        client.destroy()
        with pytest.raises(RuntimeError, match="destroyed"):
            client.validate_token("some-token")


@pytestmark_auth
class TestGopherAuthClientContextManager:
    """Tests for context manager protocol."""

    def test_with_statement(self):
        """Test using GopherAuthClient with 'with' statement."""
        with GopherAuthClient(
            "https://example.com/.well-known/jwks.json",
            "https://example.com",
        ) as client:
            assert client is not None
            assert client.is_destroyed() is False
        assert client.is_destroyed() is True

    def test_with_statement_exception_cleanup(self):
        """Test resources cleaned up even on exception."""
        try:
            with GopherAuthClient(
                "https://example.com/.well-known/jwks.json",
                "https://example.com",
            ) as client:
                raise ValueError("Test error")
        except ValueError:
            pass
        assert client.is_destroyed() is True
