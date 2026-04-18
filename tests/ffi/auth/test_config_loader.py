"""Tests for GopherAuthConfig (ConfigLoader FFI binding)."""

import os
import tempfile

import pytest

from gopher_mcp_python.ffi.auth.loader import is_auth_available

# Skip all tests if native library not available
pytestmark = pytest.mark.skipif(
    not is_auth_available(), reason="Native library not available"
)

from gopher_mcp_python.ffi.auth.config_loader import GopherAuthConfig


class TestLoadFile:
    def test_load_and_read_client_id(self, tmp_path):
        config_file = tmp_path / "test.config"
        config_file.write_text(
            "client_id = my-test-client\n"
            "client_secret = my-secret\n"
            "auth_server_url = http://kc:8080/realms/test\n"
        )
        config = GopherAuthConfig.load_file(str(config_file))
        assert config.get_string("client_id") == "my-test-client"
        config.destroy()

    def test_derived_jwks_uri(self, tmp_path):
        config_file = tmp_path / "test.config"
        config_file.write_text(
            "client_id = cid\n"
            "client_secret = cs\n"
            "auth_server_url = http://kc:8080/realms/myrealm\n"
        )
        config = GopherAuthConfig.load_file(str(config_file))
        assert config.get_string("jwks_uri") == (
            "http://kc:8080/realms/myrealm/protocol/openid-connect/certs"
        )
        config.destroy()

    def test_read_port_as_int(self, tmp_path):
        config_file = tmp_path / "test.config"
        config_file.write_text(
            "client_id = cid\nclient_secret = cs\n"
            "auth_server_url = http://kc:8080/realms/test\n"
            "port = 9090\n"
        )
        config = GopherAuthConfig.load_file(str(config_file))
        assert config.get_int("port") == 9090
        config.destroy()

    def test_read_auth_disabled_as_bool(self, tmp_path):
        config_file = tmp_path / "test.config"
        config_file.write_text("auth_disabled = true\n")
        config = GopherAuthConfig.load_file(str(config_file))
        assert config.get_bool("auth_disabled") is True
        config.destroy()

    def test_missing_file_raises(self):
        with pytest.raises(RuntimeError, match="Failed to load"):
            GopherAuthConfig.load_file("/nonexistent/path.config")


class TestLoadFromPairs:
    def test_basic(self):
        config = GopherAuthConfig.load_from_pairs(
            {
                "client_id": "pair-client",
                "client_secret": "pair-secret",
                "auth_server_url": "http://kc:8080/realms/test",
            }
        )
        assert config.get_string("client_id") == "pair-client"
        assert "protocol/openid-connect/certs" in config.get_string("jwks_uri")
        config.destroy()

    def test_auth_disabled(self):
        config = GopherAuthConfig.load_from_pairs({"auth_disabled": "true"})
        assert config.get_bool("auth_disabled") is True
        config.destroy()


class TestExchangeIdps:
    def test_empty(self):
        config = GopherAuthConfig.load_from_pairs({"auth_disabled": "true"})
        assert config.get_exchange_idps() == []
        config.destroy()

    def test_csv_parsing(self, tmp_path):
        config_file = tmp_path / "test.config"
        config_file.write_text(
            "auth_disabled = true\n" "exchange_idps = google,github,azure\n"
        )
        config = GopherAuthConfig.load_file(str(config_file))
        assert config.get_exchange_idps() == ["google", "github", "azure"]
        config.destroy()


class TestDestroy:
    def test_frees_handle(self):
        config = GopherAuthConfig.load_from_pairs({"auth_disabled": "true"})
        config.destroy()
        assert config.is_destroyed()

    def test_double_destroy_safe(self):
        config = GopherAuthConfig.load_from_pairs({"auth_disabled": "true"})
        config.destroy()
        config.destroy()
        assert config.is_destroyed()

    def test_get_string_after_destroy_raises(self):
        config = GopherAuthConfig.load_from_pairs({"auth_disabled": "true"})
        config.destroy()
        with pytest.raises(RuntimeError, match="destroyed"):
            config.get_string("client_id")

    def test_context_manager(self):
        with GopherAuthConfig.load_from_pairs({"auth_disabled": "true"}) as cfg:
            assert cfg.get_bool("auth_disabled") is True
        assert cfg.is_destroyed()


class TestDefaults:
    def test_default_port(self):
        config = GopherAuthConfig.load_from_pairs({"auth_disabled": "true"})
        assert config.get_int("port") == 3001
        config.destroy()

    def test_default_host(self):
        config = GopherAuthConfig.load_from_pairs({"auth_disabled": "true"})
        assert config.get_string("host") == "0.0.0.0"
        config.destroy()
