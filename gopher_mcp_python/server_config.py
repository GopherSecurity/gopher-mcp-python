"""Fetch API-key inventory once using the shared multi-select POST contract."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener
from .errors import AgentError, ApiKeyError
from .source_selection import ServerConfigRoute, normalize_source_selection

FETCH_TIMEOUT_SECONDS = 30

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def urlopen(request, timeout):
    return build_opener(_NoRedirect()).open(request, timeout=timeout)

class ServerConfig:
    @staticmethod
    def fetch(api_key, route=None, selection=None):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ApiKeyError("API key is required")
        body = json.dumps(normalize_source_selection(selection, route)).encode("utf-8")
        request = Request(f"{_gopher_api_root()}/v1/mcp-servers", data=body, method="POST", headers={
            "Accept": "application/json", "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        })
        deadline = time.monotonic() + FETCH_TIMEOUT_SECONDS
        try:
            with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                # read1 returns after one buffered/socket read, allowing the
                # overall body-read budget to be updated even for slow streams.
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
                return result.decode("utf-8")
        except HTTPError as error:
            error.close()
            raise AgentError(f"Inventory HTTP request failed with status {error.code}") from None
        except (TimeoutError, URLError, OSError, ValueError):
            raise AgentError("Failed to fetch servers: transport failed or request timed out") from None

def _gopher_api_root():
    value = os.environ.get("GOPHER_SDK_TEST", "")
    return "https://api-test.gopher.security" if value.strip().lower() in {"true", "1", "yes"} else "https://api.gopher.security"
