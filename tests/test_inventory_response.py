import json
import pytest
from gopher_mcp_python.inventory_response import normalize_inventory_response
from gopher_mcp_python.errors import AgentError
from gopher_mcp_python.oauth_server_targets import extract_mcp_server_targets

def entry(name="mail", **extra):
    return dict(name=name, transport="http", config={"url":"https://example/mcp"}, **extra)
def envelope(rows): return json.dumps({"succeeded":True,"data":{"servers":rows}})
def test_preserves_routes_and_deduplicates():
    row=entry(id="id",serverId="wrong")
    result=normalize_inventory_response(envelope([row,row,entry("gateway")]))
    assert len(json.loads(result)["data"]["servers"])==2
    assert extract_mcp_server_targets(server_config=result)[0]["server_id"]=="id"
@pytest.mark.parametrize("body", ['{}','[]','{"succeeded":false,"message":"secret"}', envelope([entry(),entry(config2={})]), envelope([{"name":"bad","transport":"http"}])])
def test_invalid_response_is_rejected_without_body(body):
    with pytest.raises(AgentError) as exc: normalize_inventory_response(body)
    assert 'secret' not in str(exc.value)
def test_expands_authoritative_config_before_oauth(monkeypatch):
    monkeypatch.setenv("MCP_URL", "https://correct/mcp")
    row=entry();row["url"]="https://wrong"; row["config"]["url"]="${MCP_URL}"
    result=normalize_inventory_response(envelope([row]))
    assert extract_mcp_server_targets(server_config=result)[0]["url"]=="https://correct/mcp"
