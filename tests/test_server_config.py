import json
from urllib.error import HTTPError, URLError
import pytest
from gopher_mcp_python.errors import AgentError, ApiKeyError
from gopher_mcp_python.server_config import ServerConfig, ServerConfigRoute
import gopher_mcp_python.server_config as module

class FakeResponse:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return b'{"succeeded":true,"data":{"servers":[]}}'
    def close(self): pass

def test_post_merges_selectors_once(monkeypatch):
    requests = []
    def request(req, timeout):
        requests.append((req, timeout))
        return FakeResponse()
    monkeypatch.setenv("GOPHER_SDK_TEST", "true")
    monkeypatch.setattr(module, "urlopen", request)
    ServerConfig.fetch("secret", ServerConfigRoute("serverName", "Draft Mail"), {"serverId": ["s1"]})
    assert len(requests) == 1
    req, timeout = requests[0]
    assert timeout == 30
    assert req.full_url == "https://api-test.gopher.security/v1/mcp-servers"
    assert req.method == "POST"
    assert req.headers["Authorization"] == "Bearer secret"
    assert json.loads(req.data) == {"serverId": ["s1"], "serverName": ["Draft Mail"], "gatewayId": [], "gatewayName": []}

@pytest.mark.parametrize("key", [None, "", "  "])
def test_missing_key(key):
    with pytest.raises(ApiKeyError): ServerConfig.fetch(key)

@pytest.mark.parametrize("error", [HTTPError("secret-url",403,"secret-body",None,FakeResponse()), URLError("secret-body"), TimeoutError("secret-body")])
def test_errors_do_not_echo_credentials_or_responses(monkeypatch, error):
    def fail(*args, **kwargs): raise error
    monkeypatch.setattr(module, "urlopen", fail)
    with pytest.raises(AgentError) as exc: ServerConfig.fetch("secret")
    assert "secret" not in str(exc.value)

def test_unknown_selector_rejected_before_request(monkeypatch):
    monkeypatch.setattr(module, "urlopen", lambda *a, **k: pytest.fail("request sent"))
    with pytest.raises(AgentError): ServerConfig.fetch("key", ServerConfigRoute("bad", "s"))
