"""OAuth discovery helpers for protected MCP endpoints."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse


GOPHER_HOSTED_OAUTH_DEFAULT_SCOPES = ["openid", "profile", "email"]
GOPHER_HOSTED_OAUTH_ENDPOINTS = {
    "mcp.gopher.security": {
        "authorization_server": "https://auth.gopher.security/realms/gopher-mcp",
        "registration_endpoint": "https://api.gopher.security/oauth/register",
    },
    "mcp-test.gopher.security": {
        "authorization_server": "https://auth-test.gopher.security/realms/gopher-mcp",
        "registration_endpoint": "https://api-test.gopher.security/oauth/register",
    },
}


MCP_DISCOVERY_BODY = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": "gopher-sdk-oauth-probe",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {
                "name": "gopher-mcp-python-oauth-probe",
                "version": "1.0",
            },
        },
    }
).encode("utf-8")


@dataclass
class McpOAuthChallenge:
    url: str
    requires_oauth: bool
    http_status: int
    www_authenticate: Optional[str] = None
    resource_metadata_url: Optional[str] = None
    authorization_server: Optional[str] = None
    resource: Optional[str] = None
    scopes: Optional[List[str]] = None
    registration_endpoint: Optional[str] = None


@dataclass
class OAuthProtectedResourceMetadata:
    resource: str
    authorization_servers: List[str]
    scopes_supported: List[str]
    raw_json: str


@dataclass
class OAuthAuthorizationServerMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    scopes_supported: List[str]
    raw_json: str
    registration_endpoint: Optional[str] = None


def probe_mcp_oauth_challenge(url: str, timeout: float = 10.0) -> McpOAuthChallenge:
    """Probe an MCP URL and return OAuth challenge metadata if auth is required."""
    request = urllib.request.Request(
        url,
        data=MCP_DISCOVERY_BODY,
        method="POST",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            if 200 <= status < 300:
                return McpOAuthChallenge(
                    url=url,
                    requires_oauth=False,
                    http_status=status,
                )
            raise RuntimeError(
                f"oauth_metadata_fetch_failed: MCP OAuth probe for {url} "
                f"received HTTP {status}"
            )
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            fallback = _gopher_hosted_oauth_challenge(url, exc.code)
            if fallback is not None:
                return fallback
            raise RuntimeError(
                f"oauth_metadata_fetch_failed: MCP OAuth probe for {url} "
                f"received HTTP {exc.code}"
            )
        www_authenticate = exc.headers.get("WWW-Authenticate")
        resource_metadata_url = (
            parse_www_authenticate_param(www_authenticate, "resource_metadata")
            if www_authenticate
            else None
        )
        if not resource_metadata_url:
            raise RuntimeError(
                f"oauth_metadata_missing: MCP OAuth challenge for {url} "
                "is missing resource_metadata"
            )
        return McpOAuthChallenge(
            url=url,
            requires_oauth=True,
            http_status=exc.code,
            www_authenticate=www_authenticate,
            resource_metadata_url=resource_metadata_url,
        )
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"oauth_metadata_fetch_failed: MCP OAuth probe failed for {url}: "
            f"{exc.reason}"
        )


def _gopher_hosted_oauth_challenge(
    url: str,
    http_status: int,
) -> Optional[McpOAuthChallenge]:
    if http_status != 404:
        return None

    hostname = urlparse(url).hostname
    endpoints = GOPHER_HOSTED_OAUTH_ENDPOINTS.get(hostname or "")
    if endpoints is None:
        return None

    return McpOAuthChallenge(
        url=url,
        requires_oauth=True,
        http_status=http_status,
        authorization_server=endpoints["authorization_server"],
        registration_endpoint=endpoints["registration_endpoint"],
        resource=url,
        scopes=list(GOPHER_HOSTED_OAUTH_DEFAULT_SCOPES),
    )


def parse_www_authenticate_param(challenge: str, name: str) -> Optional[str]:
    """Parse a parameter from a Bearer WWW-Authenticate challenge."""
    for part in _split_challenge_params(challenge):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value
    return None


def fetch_oauth_protected_resource_metadata(
    resource_metadata_url: str,
    timeout: float = 10.0,
) -> OAuthProtectedResourceMetadata:
    """Fetch RFC 9728 OAuth protected resource metadata."""
    body = _fetch_json(resource_metadata_url, "protected resource", timeout)
    try:
        parsed = json.loads(body)
    except Exception as exc:
        raise RuntimeError(
            "oauth_metadata_fetch_failed: Invalid protected resource metadata "
            f"JSON: {exc}"
        )
    if not isinstance(parsed, dict):
        raise RuntimeError(
            "oauth_metadata_fetch_failed: Protected resource metadata must be "
            "a JSON object"
        )

    resource = _read_string(parsed.get("resource"))
    if resource is None:
        raise RuntimeError(
            "oauth_metadata_fetch_failed: Protected resource metadata is "
            "missing resource"
        )
    authorization_servers = _read_string_array(parsed.get("authorization_servers"))
    if len(authorization_servers) == 0:
        raise RuntimeError(
            "oauth_metadata_fetch_failed: Protected resource metadata is "
            "missing authorization_servers"
        )
    return OAuthProtectedResourceMetadata(
        resource=resource,
        authorization_servers=authorization_servers,
        scopes_supported=_read_string_array(parsed.get("scopes_supported")),
        raw_json=body,
    )


def fetch_oauth_authorization_server_metadata(
    authorization_server: str,
    timeout: float = 10.0,
) -> OAuthAuthorizationServerMetadata:
    """Fetch RFC 8414/OIDC authorization server metadata."""
    try:
        body = _fetch_json(
            _build_well_known_url(authorization_server, "oauth-authorization-server"),
            "authorization server",
            timeout,
        )
    except Exception:
        body = _fetch_json(
            _build_well_known_url(authorization_server, "openid-configuration"),
            "authorization server",
            timeout,
        )

    try:
        parsed = json.loads(body)
    except Exception as exc:
        raise RuntimeError(
            "oauth_server_metadata_invalid: Invalid authorization server "
            f"metadata JSON: {exc}"
        )
    if not isinstance(parsed, dict):
        raise RuntimeError(
            "oauth_server_metadata_invalid: Authorization server metadata "
            "must be a JSON object"
        )

    issuer = _read_string(parsed.get("issuer"))
    authorization_endpoint = _read_string(parsed.get("authorization_endpoint"))
    token_endpoint = _read_string(parsed.get("token_endpoint"))
    if issuer is None:
        raise RuntimeError(
            "oauth_server_metadata_invalid: Authorization server metadata is "
            "missing issuer"
        )
    if authorization_endpoint is None:
        raise RuntimeError(
            "oauth_server_metadata_invalid: Authorization server metadata is "
            "missing authorization_endpoint"
        )
    if token_endpoint is None:
        raise RuntimeError(
            "oauth_server_metadata_invalid: Authorization server metadata is "
            "missing token_endpoint"
        )
    return OAuthAuthorizationServerMetadata(
        issuer=issuer,
        authorization_endpoint=authorization_endpoint,
        token_endpoint=token_endpoint,
        registration_endpoint=_read_string(parsed.get("registration_endpoint")),
        scopes_supported=_read_string_array(parsed.get("scopes_supported")),
        raw_json=body,
    )


def _split_challenge_params(challenge: str) -> List[str]:
    value = challenge.strip()
    if value.lower().startswith("bearer "):
        value = value[7:]
    parts: List[str] = []
    current = []
    quoted = False
    for char in value:
        if char == '"':
            quoted = not quoted
            current.append(char)
        elif char == "," and not quoted:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def _build_well_known_url(issuer: str, well_known_name: str) -> str:
    parsed = urlparse(issuer)
    path = "" if parsed.path in ("", "/") else parsed.path.rstrip("/")
    if well_known_name == "openid-configuration":
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                f"{path}/.well-known/{well_known_name}",
                "",
                "",
                "",
            )
        )
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            f"/.well-known/{well_known_name}{path}",
            "",
            "",
            "",
        )
    )


def _fetch_json(url: str, label: str, timeout: float) -> str:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            if status < 200 or status >= 300:
                raise RuntimeError(
                    f"oauth_metadata_fetch_failed: OAuth {label} metadata fetch "
                    f"from {url} received HTTP {status}"
                )
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"oauth_metadata_fetch_failed: OAuth {label} metadata fetch from "
            f"{url} received HTTP {exc.code}"
        )
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"oauth_metadata_fetch_failed: Failed to fetch OAuth {label} "
            f"metadata from {url}: {exc.reason}"
        )


def _read_string(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _read_string_array(value: Any) -> List[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []
