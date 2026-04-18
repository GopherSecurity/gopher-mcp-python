"""Tests for IDP and multi-scope validation FFI bindings."""

import pytest
from gopher_mcp_python.ffi.auth.loader import is_auth_available

pytestmark = pytest.mark.skipif(
    not is_auth_available(), reason="Native library not available"
)

from gopher_mcp_python.ffi.auth.loader import (
    gopher_auth_validate_idp,
    gopher_auth_validate_all_scopes,
    gopher_auth_validate_any_scopes,
)
from gopher_mcp_python.ffi.auth.auth_client import gopher_init_auth_library


@pytest.fixture(autouse=True)
def init_lib():
    gopher_init_auth_library()


class TestValidateIdp:
    def test_valid(self):
        assert gopher_auth_validate_idp("google,github,azure", "github") is True

    def test_invalid(self):
        assert gopher_auth_validate_idp("google,github", "azure") is False

    def test_empty(self):
        assert gopher_auth_validate_idp("", "google") is False

    def test_whitespace(self):
        assert gopher_auth_validate_idp(" google , github ", "google") is True


class TestValidateAllScopes:
    def test_all_present(self):
        assert (
            gopher_auth_validate_all_scopes(
                "openid mcp:read mcp:admin", "mcp:read mcp:admin"
            )
            is True
        )

    def test_one_missing(self):
        assert (
            gopher_auth_validate_all_scopes("openid mcp:read", "mcp:read mcp:admin")
            is False
        )

    def test_empty_required(self):
        assert gopher_auth_validate_all_scopes("openid", "") is True

    def test_empty_available(self):
        assert gopher_auth_validate_all_scopes("", "mcp:read") is False


class TestValidateAnyScopes:
    def test_one_present(self):
        assert (
            gopher_auth_validate_any_scopes("openid mcp:read", "mcp:read mcp:admin")
            is True
        )

    def test_none_present(self):
        assert gopher_auth_validate_any_scopes("openid", "mcp:read mcp:admin") is False

    def test_empty_required(self):
        assert gopher_auth_validate_any_scopes("openid", "") is True

    def test_empty_available(self):
        assert gopher_auth_validate_any_scopes("", "mcp:read") is False
