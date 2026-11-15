"""Inventory-only validation; local JSON configuration keeps its own semantics."""
import json
import os
import re
from .errors import AgentError

HTTP = {"http_sse", "http-sse", "sse", "streamable_http", "streamable-http", "http_stream", "http"}
WS = {"websocket", "ws"}

def _expand(value):
    pattern = r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}"
    for _ in range(100):
        if not re.search(pattern, value): return value
        value = re.sub(pattern, lambda match: os.environ.get(match[1], ""), value, count=1)
    raise AgentError("Invalid inventory configuration: recursive environment substitution")

def normalize_inventory_response(body):
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        raise AgentError("Invalid inventory response: expected JSON envelope") from None
    if not isinstance(data, dict) or type(data.get("succeeded")) is not bool:
        raise AgentError("Invalid inventory response: expected succeeded/data.servers envelope")
    if not data["succeeded"] or data.get("message", "success") != "success":
        raise AgentError("Inventory backend rejected request; check selectors and API-key access")
    content = data.get("data")
    if not isinstance(content, dict) or not isinstance(content.get("servers"), list):
        raise AgentError("Invalid inventory response: expected data.servers array")
    result, seen, names = [], set(), set()
    for index, entry in enumerate(content["servers"]):
        def fail(): raise AgentError(f"Invalid inventory source at index {index}")
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"]: fail()
        transport = entry.get("transport", "stdio")
        if not isinstance(transport, str) or transport not in HTTP | WS | {"stdio"}: fail()
        fallback = entry.get("stdio") if transport == "stdio" else entry.get("websocket") if transport in WS else entry.get("http_sse", entry.get("streamable_http"))
        config = entry.get("config", fallback)
        endpoint = "command" if transport == "stdio" else "url"
        if not isinstance(config, dict) or not isinstance(config.get(endpoint), str): fail()
        config = dict(config)
        config[endpoint] = _expand(config[endpoint])
        if not config[endpoint]: fail()
        if "headers" in config:
            if not isinstance(config["headers"], dict) or any(not isinstance(v, str) for v in config["headers"].values()): fail()
            config["headers"] = {k: _expand(v) for k, v in config["headers"].items()}
        if "verify_ssl" in config and type(config["verify_ssl"]) is not bool: fail()
        if transport == "stdio":
            if "args" in config and (not isinstance(config["args"], list) or any(not isinstance(x,str) for x in config["args"])): fail()
            if "env" in config and (not isinstance(config["env"], dict) or any(not isinstance(x,str) for x in config["env"].values())): fail()
            if "working_directory" in config and not isinstance(config["working_directory"],str): fail()
        for key in ("connectTimeout", "requestTimeout", "max_retries"):
            if key in entry and (type(entry[key]) is not int or abs(entry[key]) > 2**53-1): fail()
        for key in ("id", "serverId", "server_id"):
            if key in entry:
                if not isinstance(entry[key], str): fail()
                break
        fingerprint = json.dumps(entry, sort_keys=True, separators=(",",":"))
        if fingerprint in seen: continue
        if entry["name"] in names: raise AgentError("Inventory contains conflicting runtime names; select unique routes")
        seen.add(fingerprint); names.add(entry["name"])
        result.append(dict(entry, config=config))
    content["servers"] = result
    return json.dumps(data, separators=(",",":"))
