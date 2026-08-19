"""Generic OAuth token helpers for tests."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class TestOAuthToken:
    access_token: str
    token_type: str
    expires_in: Optional[int] = None
    scope: Optional[str] = None


def refresh_test_oauth_token(
    *,
    token_endpoint: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    timeout: float = 5.0,
) -> TestOAuthToken:
    """Refresh a test OAuth token without leaking fixture secrets."""

    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        token_endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            payload = response.read()
    except urllib.error.HTTPError as exc:
        detail = _oauth_error_from_body(exc.read())
        suffix = f" ({detail})" if detail else ""
        raise RuntimeError(
            f"oauth_test_token_refresh_failed: token endpoint returned HTTP "
            f"{exc.code}{suffix}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"oauth_test_token_refresh_failed: {exc.reason}"
        ) from exc

    if status < 200 or status >= 300:
        raise RuntimeError(
            f"oauth_test_token_refresh_failed: token endpoint returned HTTP {status}"
        )

    token_response = _parse_json_object(payload)
    access_token = token_response.get("access_token")
    token_type = token_response.get("token_type")

    if not isinstance(access_token, str) or not access_token:
        raise RuntimeError(
            "oauth_test_token_refresh_failed: missing access_token in token response"
        )
    if not isinstance(token_type, str) or not token_type:
        raise RuntimeError(
            "oauth_test_token_refresh_failed: missing token_type in token response"
        )

    expires_in = token_response.get("expires_in")
    if not isinstance(expires_in, int):
        expires_in = None

    scope = token_response.get("scope")
    if not isinstance(scope, str):
        scope = None

    return TestOAuthToken(
        access_token=access_token,
        token_type=token_type,
        expires_in=expires_in,
        scope=scope,
    )


def _parse_json_object(payload: bytes) -> Dict[str, object]:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "oauth_test_token_refresh_failed: invalid JSON token response"
        ) from exc

    if not isinstance(decoded, dict):
        raise RuntimeError(
            "oauth_test_token_refresh_failed: invalid JSON token response"
        )
    return decoded


def _oauth_error_from_body(payload: bytes) -> Optional[str]:
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(decoded, dict):
        return None

    error = decoded.get("error")
    return error if isinstance(error, str) and error else None
