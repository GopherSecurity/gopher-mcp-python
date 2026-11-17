"""Inventory-only validation; local JSON configuration keeps its own semantics."""

import json
import re
from collections import Counter
from urllib.parse import quote, unquote, urlsplit

from .errors import AgentError
from .source_selection import normalize_source_selection

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


def _source_id(source):
    return next(
        (source[key] for key in ("id", "serverId", "server_id") if key in source), ""
    )


def _inventory_route(source):
    source_id = _source_id(source)
    path_id, gateway = None, False
    url = source["config"]["url"]
    try:
        # Do not let urlsplit strip controls that the native URL parser rejects.
        if any(ord(char) < 32 or ord(char) == 127 for char in url):
            return source_id, source["name"], path_id, gateway
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https", "ws", "wss") or not parsed.hostname:
            return source_id, source["name"], path_id, gateway
        # Accessing port validates malformed and out-of-range values.
        _ = parsed.port
        if re.search(r"%(?![0-9a-fA-F]{2})", parsed.path):
            return source_id, source["name"], path_id, gateway
        path = unquote(parsed.path, errors="strict")
        match = re.fullmatch(r"/v1/mcp/(gateways|servers)/([^/]+)/(?:mcp|sse)/?", path)
        if match:
            identifier = match[2]
            if (
                identifier not in (".", "..")
                and "\\" not in identifier
                and not any(ord(char) < 32 or ord(char) == 127 for char in identifier)
            ):
                path_id = identifier
                gateway = match[1] == "gateways"
    except ValueError:
        pass
    return source_id, source["name"], path_id, gateway


def _validate_gateway_selection(sources, selection):
    gateway_ids, gateway_names = set(selection["gatewayId"]), set(
        selection["gatewayName"]
    )
    if not gateway_ids and not gateway_names:
        return
    server_ids, server_names = set(selection["serverId"]), set(selection["serverName"])
    returned_ids, returned_names = set(), set()
    for source in sources:
        source_id, name, path_id, gateway = _inventory_route(source)
        selected_gateway = gateway and (
            source_id in gateway_ids or path_id in gateway_ids or name in gateway_names
        )
        selected_server = (
            source_id in server_ids
            or (not gateway and path_id in server_ids)
            or name in server_names
        )
        if not selected_gateway and not selected_server:
            raise AgentError(
                "Invalid inventory gateway selection: returned source is not a selected "
                "gateway route or explicitly selected server; refusing to bypass gateway policy"
            )
        if gateway:
            returned_ids.update((source_id, path_id))
            returned_names.add(name)
    if not gateway_ids <= returned_ids:
        raise AgentError(
            "Invalid inventory gatewayId selection: every selector must resolve to a gateway route; refusing backing-server substitution"
        )
    if not gateway_names <= returned_names:
        raise AgentError(
            "Invalid inventory gatewayName selection: every selector must resolve to a gateway route; refusing backing-server substitution"
        )


def _alias_runtime_names(sources):
    counts = Counter(source["name"] for source in sources)
    # Reserve original names first, including real sources named like aliases.
    names = set(counts)
    aliases = {}
    for index, source in enumerate(sources):
        name = source["name"]
        if counts[name] <= 1:
            continue
        source_id = _source_id(source)
        key = (name, source_id)
        if not source_id or key in aliases:
            raise AgentError(
                "Inventory sources with the same name require distinct nonempty IDs"
            )
        aliases[key] = index
    # Match native's allocation order; the same sources receive the same
    # aliases regardless of response order. IDs use native percent encoding.
    for (name, source_id), index in sorted(aliases.items()):
        try:
            alias = name + "__" + quote(source_id, safe="-._~")
        except UnicodeError:
            raise AgentError(
                "Invalid inventory source ID for duplicate runtime name"
            ) from None
        while alias in names:
            alias += "_"
        names.add(alias)
        sources[index]["name"] = alias


def normalize_inventory_response(body, selection=None):
    selection = normalize_source_selection(selection)
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
    result, seen = [], set()
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
        seen.add(fingerprint)
        result.append(dict(entry, config=config))
    # Selectors refer to backend names, never generated runtime aliases.
    _validate_gateway_selection(result, selection)
    _alias_runtime_names(result)
    content["servers"] = result
    return json.dumps(data, separators=(",", ":"))
