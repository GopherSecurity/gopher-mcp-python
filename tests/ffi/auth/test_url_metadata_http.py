"""Tests for URL Utils, Metadata Builders, and HTTP Parsing FFI bindings."""
import pytest
from gopher_mcp_python.ffi.auth.loader import is_auth_available

pytestmark = pytest.mark.skipif(not is_auth_available(), reason="Native library not available")

from gopher_mcp_python.ffi.auth.loader import (
    gopher_auth_url_encode, gopher_auth_url_decode,
    gopher_auth_build_protected_resource_metadata,
    gopher_auth_build_oauth_server_metadata,
    gopher_auth_build_oidc_discovery_metadata,
    gopher_auth_extract_bearer_token,
    gopher_auth_extract_method, gopher_auth_extract_path,
)
from gopher_mcp_python.ffi.auth.auth_client import gopher_init_auth_library

@pytest.fixture(autouse=True)
def init_lib():
    gopher_init_auth_library()

class TestUrlUtils:
    def test_encode_special(self):
        assert gopher_auth_url_encode("hello world&foo=bar") == "hello%20world%26foo%3Dbar"

    def test_decode(self):
        assert gopher_auth_url_decode("hello%20world%26foo%3Dbar") == "hello world&foo=bar"

    def test_round_trip(self):
        original = "urn:ietf:params:oauth:grant-type:token-exchange"
        assert gopher_auth_url_decode(gopher_auth_url_encode(original)) == original

    def test_preserve_unreserved(self):
        assert gopher_auth_url_encode("a-b_c.d~e") == "a-b_c.d~e"

class TestMetadataBuilders:
    def test_protected_resource(self):
        meta = gopher_auth_build_protected_resource_metadata(
            "https://server/mcp", "https://server", "openid mcp:read")
        assert meta["resource"] == "https://server/mcp"
        assert "https://server" in meta["authorization_servers"]
        assert "openid" in meta["scopes_supported"]
        assert "header" in meta["bearer_methods_supported"]

    def test_oauth_server(self):
        meta = gopher_auth_build_oauth_server_metadata(
            "https://kc/test", "https://kc/auth", "https://kc/token",
            "https://s/register", "https://kc/certs", "openid")
        assert meta["issuer"] == "https://kc/test"
        assert meta["authorization_endpoint"] == "https://kc/auth"
        assert "code" in meta["response_types_supported"]
        assert "S256" in meta["code_challenge_methods_supported"]

    def test_oidc_discovery(self):
        meta = gopher_auth_build_oidc_discovery_metadata(
            "https://kc/test", "https://kc/auth", "https://kc/token",
            "https://kc/certs", None, "openid",
            "https://kc/userinfo", "https://kc/logout")
        assert meta["issuer"] == "https://kc/test"
        assert meta["userinfo_endpoint"] == "https://kc/userinfo"
        assert meta["end_session_endpoint"] == "https://kc/logout"
        assert "public" in meta["subject_types_supported"]

    def test_optional_omitted(self):
        meta = gopher_auth_build_oauth_server_metadata(
            "https://iss", "https://auth", "https://token")
        assert "registration_endpoint" not in meta
        assert "jwks_uri" not in meta

class TestHttpParsing:
    def test_bearer_from_header(self):
        http = "GET /mcp HTTP/1.1\r\nAuthorization: Bearer my-jwt\r\n\r\n"
        assert gopher_auth_extract_bearer_token(http) == "my-jwt"

    def test_bearer_from_query(self):
        http = "GET /mcp?access_token=query-tok HTTP/1.1\r\n\r\n"
        assert gopher_auth_extract_bearer_token(http) == "query-tok"

    def test_bearer_missing(self):
        http = "GET /mcp HTTP/1.1\r\nHost: localhost\r\n\r\n"
        assert gopher_auth_extract_bearer_token(http) is None

    def test_method(self):
        assert gopher_auth_extract_method("POST /mcp HTTP/1.1\r\n") == "POST"

    def test_path(self):
        assert gopher_auth_extract_path("GET /authorize?client_id=x HTTP/1.1\r\n") == "/authorize"
