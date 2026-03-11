"""Tests for auth types module."""

import pytest

from gopher_mcp_python.ffi.auth.types import (
    GopherAuthError,
    ERROR_DESCRIPTIONS,
    ValidationResult,
    TokenPayload,
    AuthContext,
    is_gopher_auth_error,
    get_error_description,
    create_empty_auth_context,
)


class TestGopherAuthError:
    """Tests for GopherAuthError enum."""

    def test_success_value(self):
        """Test SUCCESS has value 0."""
        assert GopherAuthError.SUCCESS == 0

    def test_invalid_token_value(self):
        """Test INVALID_TOKEN has value -1000."""
        assert GopherAuthError.INVALID_TOKEN == -1000

    def test_expired_token_value(self):
        """Test EXPIRED_TOKEN has value -1001."""
        assert GopherAuthError.EXPIRED_TOKEN == -1001

    def test_invalid_idp_alias_value(self):
        """Test INVALID_IDP_ALIAS has value -1016."""
        assert GopherAuthError.INVALID_IDP_ALIAS == -1016

    def test_all_error_codes_negative(self):
        """Test all error codes except SUCCESS are negative."""
        for error in GopherAuthError:
            if error != GopherAuthError.SUCCESS:
                assert error < 0


class TestIsGopherAuthError:
    """Tests for is_gopher_auth_error function."""

    def test_success_is_valid(self):
        """Test SUCCESS (0) is valid."""
        assert is_gopher_auth_error(0) is True

    def test_invalid_token_is_valid(self):
        """Test INVALID_TOKEN (-1000) is valid."""
        assert is_gopher_auth_error(-1000) is True

    def test_invalid_idp_alias_is_valid(self):
        """Test INVALID_IDP_ALIAS (-1016) is valid."""
        assert is_gopher_auth_error(-1016) is True

    def test_positive_number_is_invalid(self):
        """Test positive numbers are invalid."""
        assert is_gopher_auth_error(1) is False
        assert is_gopher_auth_error(100) is False

    def test_out_of_range_negative_is_invalid(self):
        """Test out of range negative numbers are invalid."""
        assert is_gopher_auth_error(-999) is False
        assert is_gopher_auth_error(-1017) is False
        assert is_gopher_auth_error(-2000) is False


class TestGetErrorDescription:
    """Tests for get_error_description function."""

    def test_success_description(self):
        """Test SUCCESS description."""
        assert get_error_description(0) == "Success"

    def test_invalid_token_description(self):
        """Test INVALID_TOKEN description."""
        desc = get_error_description(-1000)
        assert "Invalid token" in desc

    def test_expired_token_description(self):
        """Test EXPIRED_TOKEN description."""
        desc = get_error_description(-1001)
        assert "expired" in desc.lower()

    def test_unknown_error_code(self):
        """Test unknown error code returns generic message."""
        desc = get_error_description(-9999)
        assert "Unknown error code" in desc
        assert "-9999" in desc

    def test_all_errors_have_descriptions(self):
        """Test all error codes have descriptions."""
        for error in GopherAuthError:
            desc = get_error_description(error)
            assert desc is not None
            assert len(desc) > 0


class TestErrorDescriptions:
    """Tests for ERROR_DESCRIPTIONS dict."""

    def test_all_errors_in_dict(self):
        """Test all error codes are in ERROR_DESCRIPTIONS."""
        for error in GopherAuthError:
            assert error in ERROR_DESCRIPTIONS

    def test_descriptions_are_strings(self):
        """Test all descriptions are non-empty strings."""
        for error, desc in ERROR_DESCRIPTIONS.items():
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_create_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult(valid=True, error_code=0)
        assert result.valid is True
        assert result.error_code == 0
        assert result.error_message is None

    def test_create_invalid_result(self):
        """Test creating an invalid result with error."""
        result = ValidationResult(
            valid=False,
            error_code=-1000,
            error_message="Invalid token",
        )
        assert result.valid is False
        assert result.error_code == -1000
        assert result.error_message == "Invalid token"


class TestTokenPayload:
    """Tests for TokenPayload dataclass."""

    def test_create_minimal_payload(self):
        """Test creating payload with required fields only."""
        payload = TokenPayload(subject="user123", scopes="read")
        assert payload.subject == "user123"
        assert payload.scopes == "read"
        assert payload.audience is None
        assert payload.expiration is None
        assert payload.issuer is None

    def test_create_full_payload(self):
        """Test creating payload with all fields."""
        payload = TokenPayload(
            subject="user123",
            scopes="read write",
            audience="my-api",
            expiration=1234567890,
            issuer="https://auth.example.com",
        )
        assert payload.subject == "user123"
        assert payload.scopes == "read write"
        assert payload.audience == "my-api"
        assert payload.expiration == 1234567890
        assert payload.issuer == "https://auth.example.com"


class TestAuthContext:
    """Tests for AuthContext dataclass."""

    def test_create_authenticated_context(self):
        """Test creating an authenticated context."""
        context = AuthContext(
            user_id="user123",
            scopes="read write",
            audience="my-api",
            token_expiry=1234567890,
            authenticated=True,
        )
        assert context.user_id == "user123"
        assert context.scopes == "read write"
        assert context.audience == "my-api"
        assert context.token_expiry == 1234567890
        assert context.authenticated is True

    def test_create_unauthenticated_context(self):
        """Test creating an unauthenticated context."""
        context = AuthContext(
            user_id="",
            scopes="",
            audience="",
            token_expiry=0,
            authenticated=False,
        )
        assert context.authenticated is False


class TestCreateEmptyAuthContext:
    """Tests for create_empty_auth_context function."""

    def test_returns_auth_context(self):
        """Test function returns AuthContext instance."""
        context = create_empty_auth_context()
        assert isinstance(context, AuthContext)

    def test_empty_user_id(self):
        """Test empty auth context has empty user_id."""
        context = create_empty_auth_context()
        assert context.user_id == ""

    def test_empty_scopes(self):
        """Test empty auth context has empty scopes."""
        context = create_empty_auth_context()
        assert context.scopes == ""

    def test_empty_audience(self):
        """Test empty auth context has empty audience."""
        context = create_empty_auth_context()
        assert context.audience == ""

    def test_zero_token_expiry(self):
        """Test empty auth context has zero token_expiry."""
        context = create_empty_auth_context()
        assert context.token_expiry == 0

    def test_not_authenticated(self):
        """Test empty auth context is not authenticated."""
        context = create_empty_auth_context()
        assert context.authenticated is False
