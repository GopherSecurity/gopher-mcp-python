"""Extract MCP HTTP targets from agent inputs for OAuth probing."""

import json
from typing import Any, Dict, List, Optional


def extract_mcp_server_targets(
    url: Optional[str] = None,
    server_config: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Extract URL-backed MCP targets from direct URL or server config JSON."""
    targets: List[Dict[str, str]] = []
    if url:
        targets.append({"url": url})

    if server_config is None:
        return targets

    try:
        parsed = json.loads(server_config)
    except Exception as exc:
        raise ValueError(
            "Failed to parse MCP server config for OAuth URL extraction: "
            f"{exc}"
        )

    for server in _collect_server_entries(parsed):
        target = _target_from_server_entry(server)
        if target is not None:
            targets.append(target)
    return targets


def _collect_server_entries(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    servers = value.get("servers")
    if isinstance(servers, list):
        return [item for item in servers if isinstance(item, dict)]
    data = value.get("data")
    if isinstance(data, dict) and isinstance(data.get("servers"), list):
        return [item for item in data["servers"] if isinstance(item, dict)]
    return []


def _target_from_server_entry(server: Dict[str, Any]) -> Optional[Dict[str, str]]:
    transport = _read_string(server.get("transport"))
    if transport is not None and transport.lower() == "stdio":
        return None

    config = server.get("config")
    url = _read_string(server.get("url"))
    if url is None and isinstance(config, dict):
        url = _read_string(config.get("url"))
    if not url:
        return None

    target = {"url": url}
    _copy_first_string(target, "server_id", server, "serverId", "server_id", "id")
    _copy_first_string(target, "name", server, "name")
    _copy_first_string(target, "server_name", server, "serverName", "server_name")
    return target


def _copy_first_string(
    target: Dict[str, str], out_key: str, source: Dict[str, Any], *keys: str
) -> None:
    for key in keys:
        value = _read_string(source.get(key))
        if value is not None:
            target[out_key] = value
            return


def _read_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None
