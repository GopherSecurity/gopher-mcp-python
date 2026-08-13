"""Tests for OAuth PKCE helpers."""

from gopher_mcp_python.oauth_pkce import (
    base64_url_encode,
    create_code_challenge,
    create_code_verifier,
)


def test_challenge_is_deterministic_for_verifier() -> None:
    verifier = "fixed-verifier"

    assert create_code_challenge(verifier) == create_code_challenge(verifier)


def test_base64_url_encode_omits_padding() -> None:
    assert base64_url_encode(b"\xfb\xff") == "-_8"


def test_verifier_length_is_valid() -> None:
    verifier = create_code_verifier()

    assert 43 <= len(verifier) <= 128
