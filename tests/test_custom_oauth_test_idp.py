"""Tests for custom OAuth test IdP harness."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict

import pytest

from tests.helpers.custom_oauth_test_idp import (
    OAUTH_TEST_ACCESS_TOKEN,
    OAUTH_TEST_CLIENT_ID,
    OAUTH_TEST_CLIENT_SECRET,
    OAUTH_TEST_REFRESH_TOKEN,
    start_custom_oauth_test_idp,
)
from tests.helpers.oauth_test_token import refresh_test_oauth_token


def test_custom_oauth_test_idp_serves_metadata() -> None:
    idp = start_custom_oauth_test_idp()
    try:
        openid_metadata = _fetch_json(idp.open_id_configuration_url)
        oauth_metadata = _fetch_json(idp.authorization_server_metadata_url)
        jwks = _fetch_json(idp.jwks_url)

        assert openid_metadata["issuer"] == idp.issuer
        assert openid_metadata["authorization_endpoint"] == idp.authorization_endpoint
        assert openid_metadata["token_endpoint"] == idp.token_endpoint
        assert openid_metadata["jwks_uri"] == idp.jwks_url
        assert openid_metadata["grant_types_supported"] == ["refresh_token"]
        assert oauth_metadata["issuer"] == idp.issuer
        assert oauth_metadata["token_endpoint"] == idp.token_endpoint
        assert jwks == {"keys": []}
    finally:
        idp.close()


def test_custom_oauth_test_idp_exchanges_fixed_refresh_token() -> None:
    idp = start_custom_oauth_test_idp()
    try:
        token = refresh_test_oauth_token(
            token_endpoint=idp.token_endpoint,
            client_id=OAUTH_TEST_CLIENT_ID,
            client_secret=OAUTH_TEST_CLIENT_SECRET,
            refresh_token=OAUTH_TEST_REFRESH_TOKEN,
        )
    finally:
        idp.close()

    assert token.access_token == OAUTH_TEST_ACCESS_TOKEN
    assert token.token_type == "Bearer"
    assert token.expires_in == 3600
    assert token.scope == "openid profile email"


@pytest.mark.parametrize(
    ("client_id", "client_secret", "refresh_token", "expected_error"),
    [
        (
            "wrong-client",
            OAUTH_TEST_CLIENT_SECRET,
            OAUTH_TEST_REFRESH_TOKEN,
            "invalid_client",
        ),
        (
            OAUTH_TEST_CLIENT_ID,
            "wrong-secret",
            OAUTH_TEST_REFRESH_TOKEN,
            "invalid_client",
        ),
        (
            OAUTH_TEST_CLIENT_ID,
            OAUTH_TEST_CLIENT_SECRET,
            "wrong-refresh-token",
            "invalid_grant",
        ),
    ],
)
def test_custom_oauth_test_idp_returns_oauth_errors_deterministically(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    expected_error: str,
) -> None:
    idp = start_custom_oauth_test_idp()
    try:
        with pytest.raises(RuntimeError, match=expected_error):
            refresh_test_oauth_token(
                token_endpoint=idp.token_endpoint,
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
            )
    finally:
        idp.close()


def test_custom_oauth_test_idp_rejects_unsupported_grant() -> None:
    idp = start_custom_oauth_test_idp()
    try:
        response = _post_form(
            idp.token_endpoint,
            {
                "grant_type": "client_credentials",
                "client_id": OAUTH_TEST_CLIENT_ID,
                "client_secret": OAUTH_TEST_CLIENT_SECRET,
            },
        )
    finally:
        idp.close()

    assert response.status == 400
    assert response.body == {"error": "unsupported_grant_type"}


def test_custom_oauth_test_idp_rejects_missing_fields() -> None:
    idp = start_custom_oauth_test_idp()
    try:
        response = _post_form(
            idp.token_endpoint,
            {
                "grant_type": "refresh_token",
                "client_id": OAUTH_TEST_CLIENT_ID,
            },
        )
    finally:
        idp.close()

    assert response.status == 400
    assert response.body == {"error": "invalid_request"}


def test_custom_oauth_test_idp_authorize_endpoint_is_deterministic() -> None:
    idp = start_custom_oauth_test_idp()
    try:
        body = _fetch_json(idp.authorization_endpoint)
    finally:
        idp.close()

    assert body == {
        "issuer": idp.issuer,
        "message": "custom OAuth test IdP authorization endpoint",
    }


def test_custom_oauth_test_idp_close_stops_server() -> None:
    idp = start_custom_oauth_test_idp()
    idp.close()

    with pytest.raises(urllib.error.URLError):
        _fetch_json(idp.open_id_configuration_url)


class _FormResponse:
    def __init__(self, status: int, body: object) -> None:
        self.status = status
        self.body = body


def _fetch_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_form(url: str, params: Dict[str, str]) -> _FormResponse:
    data = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            status = response.status
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = json.loads(exc.read().decode("utf-8"))

    return _FormResponse(status, body)
