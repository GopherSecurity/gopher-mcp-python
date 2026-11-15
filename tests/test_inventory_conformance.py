"""Use the exact inventory cases shared by native and JS SDKs."""

import json
from pathlib import Path

import pytest

from gopher_mcp_python import AgentError
from gopher_mcp_python.inventory_response import normalize_inventory_response
from gopher_mcp_python.source_selection import (
    normalize_source_selection,
    ServerConfigRoute,
)

FIXTURE = json.loads(
    (
        Path(__file__).parents[1]
        / "third_party/gopher-orch/tests/fixtures/inventory/conformance.json"
    ).read_text()
)


@pytest.mark.parametrize("case", FIXTURE["request_cases"])
def test_shared_inventory_request(case):
    route = ServerConfigRoute(case["key"], case["value"]) if case["key"] else None
    assert normalize_source_selection(case["options"], route) == case["expected"]


@pytest.mark.parametrize(
    "case", FIXTURE["response_cases"], ids=lambda case: case["name"]
)
def test_shared_inventory_response(case):
    if not case["valid"]:
        with pytest.raises(AgentError) as error:
            normalize_inventory_response(json.dumps(case["response"]))
        assert "fixture-token" not in str(error.value)
    else:
        result = json.loads(normalize_inventory_response(json.dumps(case["response"])))
        assert len(result["data"]["servers"]) == case["count"]
