"""Fetch API-key inventory using native-compatible GET/POST negotiation."""

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener
from .errors import AgentError, ApiKeyError
from .inventory_response import normalize_inventory_response
from .source_selection import ServerConfigRoute, normalize_source_selection

FETCH_TIMEOUT_SECONDS = 30


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urlopen(request, timeout):
    return build_opener(_NoRedirect()).open(request, timeout=timeout)


def _fetch_body(request, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    with urlopen(request, timeout=remaining) as response:
        # read1 yields after one socket/buffer read so a slow stream cannot
        # restart the total budget. The same deadline also covers a 405 retry.
        if hasattr(response, "read1"):
            chunks = []
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                raw = getattr(getattr(response, "fp", None), "raw", None)
                sock = getattr(raw, "_sock", None)
                if sock is not None:
                    sock.settimeout(remaining)
                chunk = response.read1(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            result = b"".join(chunks)
        else:
            result = response.read()
        if time.monotonic() >= deadline:
            raise TimeoutError()
        return result.decode("utf-8")


class ServerConfig:
    @staticmethod
    def fetch(api_key, route=None, selection=None):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ApiKeyError("API key is required")
        selected = normalize_source_selection(selection, route)
        selectors = [
            (key, value) for key, values in selected.items() for value in values
        ]
        legacy = len(selectors) <= 1
        url = f"{_gopher_api_root()}/v1/mcp-servers"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
        body = json.dumps(selected).encode("utf-8")
        post_request = Request(
            url,
            data=body,
            method="POST",
            headers={**headers, "Content-Type": "application/json"},
        )
        if legacy:
            query = urlencode(selectors, quote_via=quote, safe="")
            request = Request(
                url + ("?" + query if query else ""), method="GET", headers=headers
            )
        else:
            request = post_request
        deadline = time.monotonic() + FETCH_TIMEOUT_SECONDS
        try:
            try:
                result = _fetch_body(request, deadline)
            except HTTPError as error:
                if not legacy or error.code != 405:
                    raise
                # Only an explicit GET 405 permits a same-host method switch.
                # Close the failed response without reading/echoing its body.
                error.close()
                result = _fetch_body(post_request, deadline)
            return normalize_inventory_response(result, selected)
        except HTTPError as error:
            error.close()
            if not legacy and error.code == 405:
                raise AgentError(
                    "Inventory HTTP request failed with status 405: multiple selectors "
                    "require backend POST /v1/mcp-servers support; legacy GET cannot "
                    "preserve this selection"
                ) from None
            raise AgentError(
                f"Inventory HTTP request failed with status {error.code}"
            ) from None
        except (TimeoutError, URLError, OSError, ValueError):
            raise AgentError(
                "Failed to fetch servers: transport failed or request timed out"
            ) from None


def _gopher_api_root():
    value = os.environ.get("GOPHER_SDK_TEST", "")
    return (
        "https://api-test.gopher.security"
        if value.strip().lower() in {"true", "1", "yes"}
        else "https://api.gopher.security"
    )
