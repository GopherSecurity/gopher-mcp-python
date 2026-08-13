"""Dynamic OAuth client registration."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

from gopher_mcp_python.oauth_discovery import OAuthAuthorizationServerMetadata
from gopher_mcp_python.runtime_options import GopherAgentOAuthOptions


@dataclass
class OAuthRegisteredClient:
    client_id: str
    client_secret: Optional[str] = None


def register_oauth_client(
    metadata: OAuthAuthorizationServerMetadata,
    redirect_uri: str,
    scopes: List[str],
    oauth: Optional[GopherAgentOAuthOptions] = None,
    timeout: float = 10.0,
) -> OAuthRegisteredClient:
    """Register a public OAuth client with the authorization server."""
    if metadata.registration_endpoint is None:
        raise RuntimeError(
            "oauth_registration_required: Authorization server metadata has "
            "no registration_endpoint and caller-provided client metadata is "
            "not supported yet."
        )

    client_name = oauth.client_name if oauth and oauth.client_name else "gopher-mcp-python"
    body = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
    }
    if scopes:
        body["scope"] = " ".join(scopes)

    request = urllib.request.Request(
        metadata.registration_endpoint,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        detail = _error_from_json(text) or f"HTTP {exc.code}"
        raise RuntimeError(f"oauth_registration_failed: {detail}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"oauth_registration_failed: {exc.reason}")

    try:
        parsed = json.loads(text) if text else {}
    except Exception as exc:
        raise RuntimeError(f"oauth_registration_failed: invalid_registration_response: {exc}")
    if not isinstance(parsed, dict):
        raise RuntimeError("oauth_registration_failed: invalid_registration_response")
    client_id = parsed.get("client_id")
    if not isinstance(client_id, str) or not client_id:
        detail = parsed.get("error") if isinstance(parsed.get("error"), str) else None
        raise RuntimeError(
            f"oauth_registration_failed: {detail or 'Dynamic client registration failed'}"
        )
    if status < 200 or status >= 300:
        raise RuntimeError(f"oauth_registration_failed: HTTP {status}")
    client_secret = parsed.get("client_secret")
    return OAuthRegisteredClient(
        client_id=client_id,
        client_secret=client_secret if isinstance(client_secret, str) else None,
    )


def _error_from_json(text: str) -> Optional[str]:
    try:
        parsed = json.loads(text) if text else {}
    except Exception:
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
        return parsed["error"]
    return None
