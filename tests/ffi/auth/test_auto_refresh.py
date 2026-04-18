"""Tests for auto-refresh FFI binding."""

import pytest
from gopher_mcp_python.ffi.auth.loader import is_auth_available

pytestmark = pytest.mark.skipif(
    not is_auth_available(), reason="Native library not available"
)

from gopher_mcp_python.ffi.auth.auth_client import (
    GopherAuthClient,
    gopher_init_auth_library,
)
from gopher_mcp_python.ffi.auth.oauth_client import GopherOAuthClient
from gopher_mcp_python.ffi.auth.session_manager import GopherSessionManager
from gopher_mcp_python.ffi.auth.auto_refresh import gopher_auth_auto_refresh


@pytest.fixture(autouse=True)
def init_lib():
    gopher_init_auth_library()


class TestAutoRefresh:
    def test_unknown_session(self):
        auth = GopherAuthClient("http://kc/certs", "http://kc")
        oauth = GopherOAuthClient("http://192.0.2.1:1/token", "cid", "cs", 1)
        mgr = GopherSessionManager(300)
        result = gopher_auth_auto_refresh(auth, oauth, mgr, "nonexistent")
        assert not result.valid
        assert result.error_code != 0
        auth.destroy()
        oauth.destroy()
        mgr.destroy()

    def test_no_refresh_token(self):
        auth = GopherAuthClient("http://kc/certs", "http://kc")
        oauth = GopherOAuthClient("http://192.0.2.1:1/token", "cid", "cs", 1)
        mgr = GopherSessionManager(300)
        mgr.store_token("s1", "invalid.jwt", "", -10)
        result = gopher_auth_auto_refresh(auth, oauth, mgr, "s1")
        assert not result.valid
        auth.destroy()
        oauth.destroy()
        mgr.destroy()

    def test_session_preserved(self):
        auth = GopherAuthClient("http://kc/certs", "http://kc")
        oauth = GopherOAuthClient("http://192.0.2.1:1/token", "cid", "cs", 1)
        mgr = GopherSessionManager(300)
        mgr.store_token("s1", "my-token", "my-refresh", 3600)
        gopher_auth_auto_refresh(auth, oauth, mgr, "s1")
        assert mgr.get_access_token("s1") == "my-token"
        auth.destroy()
        oauth.destroy()
        mgr.destroy()
