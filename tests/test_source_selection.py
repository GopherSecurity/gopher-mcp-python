import pytest
from gopher_mcp_python import GopherAgentConfig, GopherAgentCreateOptions, GopherSourceSelection
from gopher_mcp_python.source_selection import normalize_source_selection, selection_from_options, ServerConfigRoute
from gopher_mcp_python.errors import AgentError


def test_additive_selection_preserves_exact_values_and_input():
    selected = {"serverId": ["s2", "s1"], "gatewayName": [" Prod "]}
    result = normalize_source_selection(selected, ServerConfigRoute("serverId", "s1"))
    assert result == {"serverId": ["s1", "s2"], "serverName": [], "gatewayId": [], "gatewayName": [" Prod "]}
    assert selected["serverId"] == ["s2", "s1"]


@pytest.mark.parametrize("selected", [[], "s1", {"serverId": None}, {"serverId": "s1"}, {"serverId": [1]}, {"serverId": [""]}, {"serverName": [" \t"]}, {"gatewayId": ["x\0y"]}, {"serverIds": ["s"]}])
def test_invalid_selection(selected):
    with pytest.raises(AgentError):
        normalize_source_selection(selected)


def test_builder_setters_preserve_selection_and_copy_arrays():
    options = GopherAgentCreateOptions(source_selection=GopherSourceSelection(server_ids=["s1", "s2"]))
    config = (GopherAgentConfig.builder().provider("p").model("m").api_key("k")
              .runtime_options(options).access_token("token").headers({"X-Test": "1"}).build())
    assert config.runtime_options.source_selection["serverId"] == ["s1", "s2"]
    copy = config.runtime_options.source_selection
    copy["serverId"].clear()
    assert options.source_selection["serverId"] == ["s1", "s2"]
    assert selection_from_options({"server_ids": ["s1"]}) == {"serverId": ["s1"]}
