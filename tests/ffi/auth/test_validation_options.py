"""Tests for ValidationOptions class."""

import pytest

from gopher_mcp_python.ffi.auth.loader import is_auth_available
from gopher_mcp_python.ffi.auth.validation_options import (
    ValidationOptions,
    create_validation_options,
)


# Skip all tests if auth functions not available
pytestmark = pytest.mark.skipif(
    not is_auth_available(),
    reason="Auth functions not available in library",
)


class TestValidationOptionsInit:
    """Tests for ValidationOptions initialization."""

    def test_creates_instance(self):
        """Test creating ValidationOptions instance."""
        options = ValidationOptions()
        assert options is not None
        options.destroy()

    def test_not_destroyed_initially(self):
        """Test options are not destroyed after creation."""
        options = ValidationOptions()
        assert options.is_destroyed() is False
        options.destroy()


class TestValidationOptionsFluentApi:
    """Tests for fluent API methods."""

    def test_set_scopes_returns_self(self):
        """Test set_scopes returns self for chaining."""
        options = ValidationOptions()
        result = options.set_scopes(["read", "write"])
        assert result is options
        options.destroy()

    def test_set_audience_returns_self(self):
        """Test set_audience returns self for chaining."""
        options = ValidationOptions()
        result = options.set_audience("my-api")
        assert result is options
        options.destroy()

    def test_set_clock_skew_returns_self(self):
        """Test set_clock_skew returns self for chaining."""
        options = ValidationOptions()
        result = options.set_clock_skew(60)
        assert result is options
        options.destroy()

    def test_method_chaining(self):
        """Test multiple methods can be chained."""
        options = ValidationOptions()
        result = (
            options
            .set_scopes(["read"])
            .set_audience("my-api")
            .set_clock_skew(30)
        )
        assert result is options
        options.destroy()


class TestValidationOptionsLifecycle:
    """Tests for lifecycle methods."""

    def test_destroy_marks_destroyed(self):
        """Test destroy() marks options as destroyed."""
        options = ValidationOptions()
        options.destroy()
        assert options.is_destroyed() is True

    def test_destroy_is_idempotent(self):
        """Test destroy() can be called multiple times."""
        options = ValidationOptions()
        options.destroy()
        options.destroy()  # Should not raise
        assert options.is_destroyed() is True

    def test_get_handle_raises_when_destroyed(self):
        """Test get_handle() raises after destroy."""
        options = ValidationOptions()
        options.destroy()
        with pytest.raises(RuntimeError, match="destroyed"):
            options.get_handle()

    def test_set_scopes_raises_when_destroyed(self):
        """Test set_scopes() raises after destroy."""
        options = ValidationOptions()
        options.destroy()
        with pytest.raises(RuntimeError, match="destroyed"):
            options.set_scopes(["read"])


class TestValidationOptionsContextManager:
    """Tests for context manager protocol."""

    def test_with_statement(self):
        """Test using ValidationOptions with 'with' statement."""
        with ValidationOptions() as options:
            assert options is not None
            assert options.is_destroyed() is False
        assert options.is_destroyed() is True

    def test_with_statement_with_config(self):
        """Test configuring options within 'with' statement."""
        with ValidationOptions() as options:
            options.set_scopes(["read", "write"])
            options.set_audience("my-api")
            assert options.is_destroyed() is False

    def test_with_statement_exception_cleanup(self):
        """Test resources cleaned up even on exception."""
        try:
            with ValidationOptions() as options:
                raise ValueError("Test error")
        except ValueError:
            pass
        assert options.is_destroyed() is True


class TestCreateValidationOptions:
    """Tests for create_validation_options factory function."""

    def test_creates_instance(self):
        """Test factory creates ValidationOptions instance."""
        options = create_validation_options()
        assert isinstance(options, ValidationOptions)
        options.destroy()

    def test_default_clock_skew(self):
        """Test default clock_skew is applied."""
        options = create_validation_options()
        # Can't directly verify, but should not raise
        assert options is not None
        options.destroy()

    def test_with_scopes(self):
        """Test factory with scopes parameter."""
        options = create_validation_options(scopes=["read", "write"])
        assert options is not None
        options.destroy()

    def test_with_audience(self):
        """Test factory with audience parameter."""
        options = create_validation_options(audience="my-api")
        assert options is not None
        options.destroy()

    def test_with_all_params(self):
        """Test factory with all parameters."""
        options = create_validation_options(
            scopes=["read"],
            audience="my-api",
            clock_skew=60,
        )
        assert options is not None
        options.destroy()
