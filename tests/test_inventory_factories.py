import json
import pytest
import gopher_mcp_python.agent as module
from gopher_mcp_python import GopherAgent, GopherAgentConfig, AgentError
from gopher_mcp_python.source_selection import normalize_source_selection

@pytest.mark.parametrize('method,value,field', [('create_with_api_key',None,None),('create_with_server_id','s1','serverId'),('create_with_server_name','mail','serverName'),('create_with_gateway_id','g1','gatewayId'),('create_with_gateway_name','prod','gatewayName')])
@pytest.mark.parametrize('options',[{'oauth':{'mode':'disabled'}},{'access_token':'runtime'}])
def test_all_factories_fetch_once_then_create_json(monkeypatch,method,value,field,options):
    calls=[]
    class Library:
        def agent_create_by_json(self,*args):calls.append(('json',args));return 123
        def agent_release(self,handle):pass
    monkeypatch.setattr(module.GopherOrchLibrary,'get_instance',lambda:Library())
    def fetch(key,route=None,selection=None):
        calls.append(('fetch',normalize_source_selection(selection,route)))
        return json.dumps({
            "succeeded": True,
            "data": {"servers": [{
                "name": "mail",
                "transport": "http",
                "config": {"url": "https://example/mcp"},
            }]},
        })
    monkeypatch.setattr(module.ServerConfig,'fetch',fetch)
    options=dict(options,server_ids=['s2'])
    args=['provider','model','key']+([value] if value else [])
    agent=getattr(GopherAgent,method)(*args, runtime_options=options)
    assert [c[0] for c in calls]==['fetch','json']
    assert calls[0][1]['serverId']==(['s1','s2'] if field=='serverId' else ['s2'])
    if field: assert calls[0][1][field][0]==value
    agent.dispose()

def test_url_and_inline_reject_selectors_before_io():
    with pytest.raises(AgentError):GopherAgent.create_with_url('p','m','https://example',{'server_ids':['s']})
    with pytest.raises(AgentError):GopherAgentConfig('p','m',server_config='{}',runtime_options={'gateway_ids':[]})


@pytest.mark.parametrize(
    "method,value",
    [
        ("create_with_api_key", None),
        ("create_with_server_id", "s1"),
        ("create_with_server_name", "mail"),
        ("create_with_gateway_id", "g1"),
        ("create_with_gateway_name", "prod"),
    ],
)
@pytest.mark.parametrize(
    "options",
    [None, {"oauth": {"mode": "disabled"}}, {"access_token": "runtime"}],
)
def test_empty_inventory_fails_before_oauth_or_native(monkeypatch, method, value, options):
    monkeypatch.setattr(
        module.ServerConfig,
        "fetch",
        lambda *args, **kwargs: '{"succeeded":true,"data":{"servers":[]}}',
    )

    def native_access():
        pytest.fail("Empty inventory reached native initialization")

    async def oauth_access(*args, **kwargs):
        pytest.fail("Empty inventory reached OAuth resolution")

    monkeypatch.setattr(module.GopherOrchLibrary, "get_instance", native_access)
    monkeypatch.setattr(
        module.oauth_resolver, "resolve_runtime_options_with_oauth", oauth_access
    )
    args = ["provider", "model", "private-key"] + ([value] if value else [])
    with pytest.raises(AgentError, match="no MCP servers") as error:
        getattr(GopherAgent, method)(*args, runtime_options=options)
    assert "GOPHER_SDK_TEST=true" in str(error.value)
    assert "private-key" not in str(error.value)
