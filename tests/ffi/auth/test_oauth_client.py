"""Tests for GopherOAuthClient FFI binding."""

import pytest
from gopher_mcp_python.ffi.auth.loader import is_auth_available

pytestmark = pytest.mark.skipif(
    not is_auth_available(), reason="Native library not available"
)

from gopher_mcp_python.ffi.auth.oauth_client import GopherOAuthClient
from gopher_mcp_python.ffi.auth.auth_client import gopher_init_auth_library


@pytest.fixture(autouse=True)
def init_lib():
    gopher_init_auth_library()


class TestOAuthClient:
    def test_create_with_all_params(self):
        client = GopherOAuthClient("http://kc:8080/token", "cid", "cs", 30)
        assert not client.is_destroyed()
        client.destroy()

    def test_create_without_secret(self):
        client = GopherOAuthClient("http://kc:8080/token", "cid")
        assert not client.is_destroyed()
        client.destroy()

    def test_error_for_unreachable_server(self):
        client = GopherOAuthClient("http://192.0.2.1:1/token", "cid", "cs", 1)
        resp = client.exchange_code("code", "http://cb")
        assert not resp.success
        client.destroy()

    def test_refresh_unreachable(self):
        client = GopherOAuthClient("http://192.0.2.1:1/token", "cid", "cs", 1)
        resp = client.refresh_token("rt")
        assert not resp.success
        client.destroy()

    def test_token_exchange_unreachable(self):
        client = GopherOAuthClient("http://192.0.2.1:1/token", "cid", "cs", 1)
        resp = client.token_exchange("st", "google")
        assert not resp.success
        client.destroy()

    def test_destroy_lifecycle(self):
        client = GopherOAuthClient("http://kc:8080/token", "cid", "cs", 5)
        client.destroy()
        assert client.is_destroyed()

    def test_call_after_destroy_raises(self):
        client = GopherOAuthClient("http://kc:8080/token", "cid", "cs", 5)
        client.destroy()
        with pytest.raises(RuntimeError, match="destroyed"):
            client.exchange_code("code", "http://cb")

    def test_double_destroy_safe(self):
        client = GopherOAuthClient("http://kc:8080/token", "cid", "cs", 5)
        client.destroy()
        client.destroy()
        assert client.is_destroyed()
