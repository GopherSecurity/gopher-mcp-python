"""Tests for GopherSessionManager FFI binding."""

import time
import pytest
from gopher_mcp_python.ffi.auth.loader import is_auth_available

pytestmark = pytest.mark.skipif(
    not is_auth_available(), reason="Native library not available"
)

from gopher_mcp_python.ffi.auth.session_manager import GopherSessionManager
from gopher_mcp_python.ffi.auth.auth_client import gopher_init_auth_library


@pytest.fixture(autouse=True)
def init_lib():
    gopher_init_auth_library()


class TestSessionManager:
    def test_store_and_retrieve(self):
        mgr = GopherSessionManager(300)
        mgr.store_token("s1", "access", "refresh", 3600)
        assert mgr.get_access_token("s1") == "access"
        assert mgr.get_refresh_token("s1") == "refresh"
        mgr.destroy()

    def test_has_valid_token_true(self):
        mgr = GopherSessionManager(300)
        mgr.store_token("s1", "tok", "ref", 3600)
        assert mgr.has_valid_token("s1") is True
        mgr.destroy()

    def test_has_valid_token_expired(self):
        mgr = GopherSessionManager(300)
        mgr.store_token("s1", "tok", "ref", -10)
        assert mgr.has_valid_token("s1") is False
        mgr.destroy()

    def test_unknown_session(self):
        mgr = GopherSessionManager(300)
        assert mgr.get_access_token("nonexistent") is None
        mgr.destroy()

    def test_generate_id_hex(self):
        sid = GopherSessionManager.generate_session_id()
        assert len(sid) == 32
        assert all(c in "0123456789abcdef" for c in sid)

    def test_generate_id_unique(self):
        ids = {GopherSessionManager.generate_session_id() for _ in range(10)}
        assert len(ids) == 10

    def test_cleanup(self):
        mgr = GopherSessionManager(1)
        mgr.store_token("s1", "t1", "r1", 3600)
        time.sleep(2.1)
        mgr.store_token("s2", "t2", "r2", 3600)
        mgr.cleanup()
        assert mgr.get_access_token("s1") is None
        assert mgr.get_access_token("s2") == "t2"
        mgr.destroy()

    def test_destroy(self):
        mgr = GopherSessionManager(300)
        mgr.destroy()
        assert mgr.is_destroyed()

    def test_double_destroy(self):
        mgr = GopherSessionManager(300)
        mgr.destroy()
        mgr.destroy()
        assert mgr.is_destroyed()
