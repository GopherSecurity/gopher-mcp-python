"""Tests for GopherAuth reusable auth module."""

import os
import pytest

from gopher_mcp_python.ffi.auth.loader import is_auth_available
from gopher_mcp_python.auth.errors import (
    InsufficientScopesError,
    TokenValidationError,
    ConfigurationError,
    TokenExchangeError,
)

native_available = is_auth_available()


class TestErrorClasses:
    def test_insufficient_scopes(self):
        err = InsufficientScopesError(["mcp:read", "mcp:admin"], ["openid"])
        assert err.required_scopes == ["mcp:read", "mcp:admin"]
        assert err.actual_scopes == ["openid"]
        assert "mcp:read" in str(err)

    def test_token_validation_error(self):
        err = TokenValidationError("expired", -1001)
        assert err.error_code == -1001

    def test_configuration_error(self):
        err = ConfigurationError("bad config")
        assert isinstance(err, Exception)

    def test_token_exchange_error(self):
        err = TokenExchangeError("failed", "invalid_grant", "expired")
        assert err.error_code == "invalid_grant"
        assert err.error_description == "expired"


@pytest.mark.skipif(not native_available, reason="Native library not available")
class TestGopherAuth:
    def test_init_from_file(self, tmp_path):
        from gopher_mcp_python.auth import GopherAuth

        config_file = tmp_path / "test.config"
        config_file.write_text(
            "client_id = cid\nclient_secret = cs\n"
            "auth_server_url = http://kc:8080/realms/test\n"
        )
        auth = GopherAuth(config_path=str(config_file))
        auth.initialize()
        assert not auth.is_disabled
        auth.shutdown()

    def test_init_from_dict(self):
        from gopher_mcp_python.auth import GopherAuth

        auth = GopherAuth(
            config={
                "auth_server_url": "http://kc:8080/realms/test",
                "client_id": "cid",
                "client_secret": "cs",
            }
        )
        auth.initialize()
        assert auth.get_token_endpoint() != ""
        auth.shutdown()

    def test_init_disabled(self):
        from gopher_mcp_python.auth import GopherAuth

        auth = GopherAuth(auth_disabled=True)
        auth.initialize()
        assert auth.is_disabled
        auth.shutdown()

    def test_no_config_raises(self):
        from gopher_mcp_python.auth import GopherAuth

        auth = GopherAuth()
        with pytest.raises(ConfigurationError):
            auth.initialize()

    def test_metadata(self):
        from gopher_mcp_python.auth import GopherAuth

        auth = GopherAuth(
            config={
                "auth_server_url": "http://kc:8080/realms/test",
                "client_id": "cid",
                "client_secret": "cs",
                "server_url": "http://localhost:3001",
                "allowed_scopes": "openid mcp:read",
            }
        )
        auth.initialize()
        meta = auth.get_protected_resource_metadata()
        assert "/mcp" in meta.get("resource", "")
        auth.shutdown()

    def test_context_manager(self, tmp_path):
        from gopher_mcp_python.auth import GopherAuth

        config_file = tmp_path / "test.config"
        config_file.write_text(
            "client_id = cid\nclient_secret = cs\n"
            "auth_server_url = http://kc:8080/realms/test\n"
        )
        with GopherAuth(config_path=str(config_file)) as auth:
            assert auth.get_token_endpoint() != ""

    def test_shutdown_idempotent(self):
        from gopher_mcp_python.auth import GopherAuth

        auth = GopherAuth(
            config={
                "auth_server_url": "http://kc:8080/realms/test",
                "client_id": "cid",
                "client_secret": "cs",
            }
        )
        auth.initialize()
        auth.shutdown()
        auth.shutdown()  # Should not raise


@pytest.mark.skipif(not native_available, reason="Native library not available")
class TestScopeHelpers:
    def test_has_scope(self):
        from gopher_mcp_python.auth import has_scope
        from gopher_mcp_python.ffi.auth.types import GopherAuthContext

        ctx = GopherAuthContext("u", "openid mcp:read", "", 0, True)
        assert has_scope(ctx, "mcp:read") is True
        assert has_scope(ctx, "mcp:admin") is False

    def test_has_scope_none(self):
        from gopher_mcp_python.auth import has_scope

        assert has_scope(None, "mcp:read") is False

    def test_has_all_scopes(self):
        from gopher_mcp_python.auth import has_all_scopes
        from gopher_mcp_python.ffi.auth.types import GopherAuthContext

        ctx = GopherAuthContext("u", "openid mcp:read mcp:admin", "", 0, True)
        assert has_all_scopes(ctx, ["mcp:read", "mcp:admin"]) is True
        assert has_all_scopes(ctx, ["mcp:read", "mcp:write"]) is False

    def test_has_any_scope(self):
        from gopher_mcp_python.auth import has_any_scope
        from gopher_mcp_python.ffi.auth.types import GopherAuthContext

        ctx = GopherAuthContext("u", "openid mcp:read", "", 0, True)
        assert has_any_scope(ctx, ["mcp:read", "mcp:admin"]) is True
        assert has_any_scope(ctx, ["mcp:write", "mcp:admin"]) is False
