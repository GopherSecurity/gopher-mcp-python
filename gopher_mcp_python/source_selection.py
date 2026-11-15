"""Additive API-key inventory selection, matching the shared native contract."""

import re
from dataclasses import dataclass
from typing import Mapping
from .errors import AgentError

FIELDS = ("serverId", "serverName", "gatewayId", "gatewayName")
ALIASES = dict(
    zip(("server_ids", "server_names", "gateway_ids", "gateway_names"), FIELDS)
)


@dataclass(frozen=True)
class ServerConfigRoute:
    key: str
    value: str


class GopherSourceSelection:
    def __init__(
        self, server_ids=None, server_names=None, gateway_ids=None, gateway_names=None
    ):
        self._selection = normalize_source_selection(
            {
                wire: value
                for wire, value in zip(
                    FIELDS, (server_ids, server_names, gateway_ids, gateway_names)
                )
                if value is not None
            }
        )

    def to_dict(self):
        return {key: list(value) for key, value in self._selection.items()}


def selection_from_options(options):
    if options is None:
        return {}
    if isinstance(options, GopherSourceSelection):
        return options.to_dict()
    if not isinstance(options, Mapping):
        return getattr(options, "source_selection", {})
    nested = options.get("source_selection")
    if nested is not None:
        if any(key in options for key in (*FIELDS, *ALIASES)):
            raise AgentError("Specify source_selection or individual selectors")
        return normalize_source_selection(nested)
    result = {}
    for key, value in options.items():
        wire = ALIASES.get(key, key)
        if wire in FIELDS:
            if wire in result:
                raise AgentError("Duplicate inventory selector aliases")
            result[wire] = value
        elif (
            re.fullmatch(r"(server|gateway)_?(id|name)s?", str(key), re.I)
            or key == "select"
        ):
            raise AgentError("Unknown inventory selector key")
    if result:
        normalize_source_selection(result)
    return result


def normalize_source_selection(selection=None, route=None):
    if selection is None:
        selection = {}
    if isinstance(selection, GopherSourceSelection):
        selection = selection.to_dict()
    if not isinstance(selection, Mapping) or any(
        key not in FIELDS for key in selection
    ):
        raise AgentError("Invalid inventory selection or unknown selector key")
    if route is not None and route.key not in FIELDS:
        raise AgentError("Unknown inventory selector key")
    result = {}
    for key in FIELDS:
        values = selection.get(key, [])
        if not isinstance(values, list):
            raise AgentError(f"Invalid {key}: expected an array of strings")
        values = (
            [route.value] if route is not None and route.key == key else []
        ) + values
        result[key] = []
        for value in values:
            if (
                not isinstance(value, str)
                or "\0" in value
                or not value.strip(" \t\r\n\f\v")
            ):
                raise AgentError(f"Invalid inventory selector in {key}")
            if value not in result[key]:
                result[key].append(value)
    return result


def assert_no_source_selection(options):
    if selection_from_options(options):
        raise AgentError("Inventory selectors require API-key creation")
