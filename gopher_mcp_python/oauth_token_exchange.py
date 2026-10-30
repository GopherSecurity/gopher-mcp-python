"""OAuth token exchange helpers."""

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

from gopher_mcp_python.runtime_options import GopherAgentTokenRecord


@dataclass
class OAuthCodeExchangeRequest:
    """Token request data for applications providing their own HTTP transport."""

    token_endpoint: str
    data: Dict[str, str]
    headers: Dict[str, str]


def build_oauth_code_exchange_request(
    *,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    token_endpoint: str,
    client_id: str,
    client_secret: Optional[str] = None,
    resource: Optional[str] = None,
    token_endpoint_auth_method: Optional[str] = None,
) -> OAuthCodeExchangeRequest:
    """Prepare a code exchange without sending any network requests.

    The advertised resource is preserved verbatim. Client authentication defaults
    to posting an available secret; client_secret_basic uses an HTTP header.
    """
    params = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
    }
    headers: Dict[str, str] = {}
    if client_secret is not None:
        if token_endpoint_auth_method == "client_secret_basic":
            credentials = base64.b64encode(
                f"{client_id}:{client_secret}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {credentials}"
        else:
            params["client_secret"] = client_secret
    if code_verifier:
        params["code_verifier"] = code_verifier
    if resource is not None:
        params["resource"] = resource
    return OAuthCodeExchangeRequest(token_endpoint, params, headers)


def exchange_oauth_code_for_token(
    code: str,
    redirect_uri: str,
    code_verifier: str,
    token_endpoint: str,
    client_id: str,
    client_secret: Optional[str] = None,
    now_ms: Optional[float] = None,
    timeout: float = 10.0,
    *,
    resource: Optional[str] = None,
    token_endpoint_auth_method: Optional[str] = None,
) -> GopherAgentTokenRecord:
    """Exchange a code for tokens, preserving the advertised OAuth resource."""
    request = build_oauth_code_exchange_request(
        code=code,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
        token_endpoint=token_endpoint,
        client_id=client_id,
        client_secret=client_secret,
        resource=resource,
        token_endpoint_auth_method=token_endpoint_auth_method,
    )
    return _token_request(
        request.token_endpoint, request.data, now_ms, timeout, request.headers
    )


def refresh_oauth_token(
    refresh_token: str,
    token_endpoint: str,
    client_id: str,
    client_secret: Optional[str] = None,
    now_ms: Optional[float] = None,
    timeout: float = 10.0,
    *,
    resource: Optional[str] = None,
) -> GopherAgentTokenRecord:
    """Refresh a token for the same advertised OAuth resource."""
    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if client_secret is not None:
        params["client_secret"] = client_secret
    if resource is not None:
        params["resource"] = resource
    return _token_request(token_endpoint, params, now_ms, timeout)


def _token_request(
    token_endpoint: str,
    params: Dict[str, str],
    now_ms: Optional[float],
    timeout: float,
    headers: Optional[Dict[str, str]] = None,
) -> GopherAgentTokenRecord:
    encoded = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(
        token_endpoint,
        data=encoded,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            ok = 200 <= response.getcode() < 300
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        ok = False
    except urllib.error.URLError as exc:
        raise RuntimeError(f"oauth_token_exchange_failed: {exc.reason}")

    try:
        parsed = json.loads(text) if text else {}
    except Exception as exc:
        raise RuntimeError(f"oauth_token_exchange_failed: invalid_token_response: {exc}")
    if not isinstance(parsed, dict):
        raise RuntimeError("oauth_token_exchange_failed: invalid_token_response")
    if not ok or not isinstance(parsed.get("access_token"), str):
        detail = parsed.get("error_description") or parsed.get("error")
        raise RuntimeError(f"oauth_token_exchange_failed: {detail or 'OAuth token request failed'}")

    expires_in = parsed.get("expires_in")
    expires_at = None
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        expires_at = (now_ms if now_ms is not None else time.time() * 1000) + (
            expires_in * 1000
        )
    refresh = parsed.get("refresh_token")
    scope = parsed.get("scope")
    token_type = parsed.get("token_type")
    return GopherAgentTokenRecord(
        access_token=parsed["access_token"],
        refresh_token=refresh if isinstance(refresh, str) else None,
        token_type=token_type if isinstance(token_type, str) else "Bearer",
        expires_at=expires_at,
        scope=scope if isinstance(scope, str) else None,
    )
