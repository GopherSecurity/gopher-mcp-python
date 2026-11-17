"""Inventory-only validation; local JSON configuration keeps its own semantics."""

import json
import re
from .errors import AgentError

HTTP = {
    "http_sse",
    "http-sse",
    "sse",
    "streamable_http",
    "streamable-http",
    "http_stream",
    "http",
}
WS = {"websocket", "ws"}


def _reject_environment_reference(value):
    # Native ConfigLoader substitutes these references too. Reject them before
    # handing remote inventory to either OAuth discovery or native creation.
    if isinstance(value, str) and re.search(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", value):
        raise AgentError(
            "Remote inventory configuration must not contain environment variable references"
        )


def normalize_inventory_response(body):
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        raise AgentError("Invalid inventory response: expected JSON envelope") from None
    if not isinstance(data, dict) or type(data.get("succeeded")) is not bool:
        raise AgentError(
            "Invalid inventory response: expected succeeded/data.servers envelope"
        )
    if not data["succeeded"] or data.get("message", "success") != "success":
        raise AgentError(
            "Inventory backend rejected request; check selectors and API-key access"
        )
    content = data.get("data")
    if not isinstance(content, dict) or not isinstance(content.get("servers"), list):
        raise AgentError("Invalid inventory response: expected data.servers array")
    _reject_environment_reference(content.get("base_url"))
    # ConfigLoader also consumes registry tools, default_headers and
    # auth_presets. Only data.servers has been validated as remote inventory.
    for container, allowed in ((data, {"data"}), (content, {"servers"})):
        for key, value in container.items():
            if key not in allowed and isinstance(value, (dict, list)) and value:
                raise AgentError("Unsupported non-empty inventory collection")
    result, seen, names = [], set(), set()
    for index, entry in enumerate(content["servers"]):

        def fail():
            raise AgentError(
                f"Invalid inventory source at index {index}; expected a named explicit "
                "network transport with its endpoint configuration"
            )

        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("name"), str)
            or not entry["name"]
        ):
            fail()
        transport = entry.get("transport")
        if not isinstance(transport, str) or transport not in HTTP | WS:
            fail()
        fallback = (
            entry.get("websocket")
            if transport in WS
            else entry.get("http_sse", entry.get("streamable_http"))
        )
        config = entry.get("config", fallback)
        if (
            not isinstance(config, dict)
            or not isinstance(config.get("url"), str)
            or not config["url"]
        ):
            fail()
        config = dict(config)
        _reject_environment_reference(config["url"])
        if "headers" in config:
            if not isinstance(config["headers"], dict) or any(
                not isinstance(v, str) for v in config["headers"].values()
            ):
                fail()
            for value in config["headers"].values():
                _reject_environment_reference(value)
        if "verify_ssl" in config and type(config["verify_ssl"]) is not bool:
            fail()
        for key in ("connectTimeout", "requestTimeout", "max_retries"):
            if key in entry and (
                type(entry[key]) is not int or abs(entry[key]) > 2**53 - 1
            ):
                fail()
        for key in ("id", "serverId", "server_id"):
            if key in entry:
                if not isinstance(entry[key], str):
                    fail()
                break
        fingerprint = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        if fingerprint in seen:
            continue
        if entry["name"] in names:
            raise AgentError(
                "Inventory contains conflicting runtime names; select unique routes"
            )
        seen.add(fingerprint)
        names.add(entry["name"])
        result.append(dict(entry, config=config))
    content["servers"] = result
    return json.dumps(data, separators=(",", ":"))
